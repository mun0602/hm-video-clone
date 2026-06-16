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

router = APIRouter(prefix="/api/videos", tags=["videos"])

# Giới hạn upload — 100MB. Đổi tùy infra.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/webm", "application/octet-stream"}


def _build_video_response(video: models.Video, current_user: Optional[models.User], db: Session, request: Optional[Request] = None) -> dict:
    """Serialize video + denormalized counts + user state flags."""
    is_liked = False
    is_followed = False
    if current_user:
        is_liked = db.query(models.Like).filter(
            models.Like.video_id == video.id,
            models.Like.user_id == current_user.id,
        ).first() is not None
        is_followed = db.query(models.Follow).filter(
            models.Follow.follower_id == current_user.id,
            models.Follow.following_id == video.user_id,
        ).first() is not None

    def _abs(url: Optional[str]) -> Optional[str]:
        if not url or not request:
            return url
        if url.startswith(("http://", "https://")):
            return url
        return str(request.base_url).rstrip("/") + url

    return {
        "id": video.id,
        "description": video.title,
        "file_url": _abs(video.video_url),
        "thumb_url": _abs(video.cover_url),
        "tags": [t.strip() for t in (video.tags or "").split(",") if t.strip()],
        "duration_seconds": video.duration_seconds,
        "created_at": video.created_at.isoformat() if video.created_at else None,
        "view_count": video.view_count or 0,
        "like_count": video.like_count or 0,
        "comment_count": len(video.comments),
        "share_count": video.share_count or 0,
        "is_liked": is_liked,
        "is_followed": is_followed,
        "user": {
            "id": video.creator.id,
            "nickname": video.creator.username,
            "fullName": video.creator.display_name,
            "avatar_url": video.creator.avatar_url,
            "bio": video.creator.bio,
            "tick": True,
        },
    }


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
    return _build_video_response(video, current_user, db, request)


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
    return [_build_video_response(v, None, db, request) for v in videos]
