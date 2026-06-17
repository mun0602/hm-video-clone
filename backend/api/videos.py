"""Video endpoints: upload, get detail, list by creator."""
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

import models
import r2_storage
import video_processing
from auth_utils import get_current_user, get_optional_current_user
from database import get_db

from api.utils import build_single_video_response, build_video_responses

router = APIRouter(prefix="/api/videos", tags=["videos"])

# Giới hạn upload — 100MB. Đổi tùy infra.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/webm", "application/octet-stream"}


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    title: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Upload video: lưu R2 (hoặc local), auto-gen thumbnail + extract duration.
    Tags là comma-separated string (vd: "comedy,dance,trending").
    """
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Content-Type {file.content_type} không được hỗ trợ. Chỉ chấp nhận video.",
        )

    # Đọc file với size check
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn ({len(file_bytes)} bytes). Tối đa {MAX_UPLOAD_BYTES} bytes.",
        )

    if not file_bytes:
        raise HTTPException(status_code=400, detail="File rỗng")

    # UUID-based filename tránh conflict
    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    video_filename = f"videos/{uuid.uuid4().hex}{ext}"

    # Upload video lên storage
    video_url = r2_storage.upload_file_to_r2(file_bytes, video_filename, file.content_type or "video/mp4")

    # Auto-process: duration + thumbnail (nếu FFmpeg có sẵn)
    duration, thumb_bytes = video_processing.process_uploaded_video(file_bytes, video_filename)

    cover_url = None
    if thumb_bytes:
        thumb_filename = f"thumbnails/{uuid.uuid4().hex}.jpg"
        cover_url = r2_storage.upload_file_to_r2(thumb_bytes, thumb_filename, "image/jpeg")

    # Lưu DB
    new_video = models.Video(
        title=title or None,
        video_url=video_url,
        cover_url=cover_url,
        tags=tags or None,
        user_id=current_user.id,
        duration_seconds=duration,
    )
    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    return {
        "status": "success",
        "video_id": new_video.id,
        "video_url": video_url,
        "cover_url": cover_url,
        "duration_seconds": duration,
        "ffmpeg_available": video_processing.is_ffmpeg_available(),
    }


@router.get("/{video_id}")
def get_video(
    video_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
):
    """Chi tiết 1 video. Auth optional để populate is_liked/is_followed."""
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video không tồn tại")
    return build_single_video_response(video, current_user, db, request)


@router.get("/by-creator/{user_id}")
def list_videos_by_creator(
    user_id: int,
    request: Request,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List videos của 1 creator, sort mới nhất trước."""
    videos = (
        db.query(models.Video)
        .filter(models.Video.user_id == user_id)
        .order_by(desc(models.Video.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )
    return build_video_responses(videos, None, db, request)
