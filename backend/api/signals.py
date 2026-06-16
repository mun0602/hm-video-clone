"""Signal tracking endpoints: view, like, follow, skip.

Đây là data layer cho recommendation engine:
- view + watch_duration + is_skipped → collaborative + content signal
- like → strong content signal
- follow creator → boost tất cả video của creator trong feed
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from auth_utils import get_current_user
from database import get_db

router = APIRouter(prefix="/api/signals", tags=["signals"])


# ============================================================
# Pydantic schemas (request bodies)
# ============================================================

class ViewSignal(BaseModel):
    video_id: int
    watch_duration: int = Field(0, ge=0, description="Giây user đã xem")
    video_duration: Optional[int] = Field(None, ge=0, description="Tổng giây của video (để tính %)")
    is_skipped: bool = False
    is_rewatched: bool = False


class LikeSignal(BaseModel):
    video_id: int


class FollowSignal(BaseModel):
    following_id: int


# ============================================================
# User profile helpers
# ============================================================

def _get_or_create_user_profile(db: Session, user_id: int) -> models.UserProfile:
    """Lấy hoặc tạo mới UserProfile row cho user."""
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    if not profile:
        profile = models.UserProfile(
            user_id=user_id,
            tag_preferences="{}",
            interaction_count=0,
        )
        db.add(profile)
        db.flush()
    return profile


def _update_tag_preference(db: Session, profile: models.UserProfile, tag: str, delta: float) -> None:
    """Tăng/giảm weight cho 1 tag trong user profile."""
    if not tag:
        return
    try:
        prefs = json.loads(profile.tag_preferences or "{}")
    except json.JSONDecodeError:
        prefs = {}

    prefs[tag] = max(-1.0, min(1.0, prefs.get(tag, 0.0) + delta))
    # Chỉ giữ top 50 tags để tránh profile phình
    if len(prefs) > 50:
        sorted_tags = sorted(prefs.items(), key=lambda x: -x[1])[:50]
        prefs = dict(sorted_tags)
    profile.tag_preferences = json.dumps(prefs)


def _get_video_tags(db: Session, video_id: int) -> list[str]:
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video or not video.tags:
        return []
    return [t.strip() for t in video.tags.split(",") if t.strip()]


# ============================================================
# Endpoints
# ============================================================

@router.post("/view")
def track_view(
    signal: ViewSignal,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Track view event. Dùng cho watch-time-based signals.
    watch_duration / video_duration = completion rate (dùng cho popularity).
    """
    video = db.query(models.Video).filter(models.Video.id == signal.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video không tồn tại")

    # 1) Tạo VideoView record
    view = models.VideoView(
        user_id=current_user.id,
        video_id=signal.video_id,
        watch_duration=signal.watch_duration,
        is_skipped=1 if signal.is_skipped else 0,
        is_rewatched=1 if signal.is_rewatched else 0,
    )
    db.add(view)

    # 2) Tăng view_count (denormalized counter)
    video.view_count = (video.view_count or 0) + 1

    # 3) Update user profile tag preferences
    profile = _get_or_create_user_profile(db, current_user.id)
    profile.interaction_count = (profile.interaction_count or 0) + 1
    profile.last_active_at = datetime.now(timezone.utc)

    # Watch-based signal strength:
    # - Watch >= 70% video → mạnh (+0.3 mỗi tag)
    # - Watch 30-70% → trung bình (+0.15)
    # - Watch < 30% hoặc skip → yếu hoặc tiêu cực (+0.05 / -0.1)
    completion = 0.0
    if signal.video_duration and signal.video_duration > 0:
        completion = min(1.0, signal.watch_duration / signal.video_duration)

    if signal.is_skipped or completion < 0.3:
        weight = -0.1
    elif completion < 0.7:
        weight = 0.15
    else:
        weight = 0.3

    for tag in _get_video_tags(db, signal.video_id):
        _update_tag_preference(db, profile, tag, weight)

    db.commit()
    return {"status": "tracked", "completion": round(completion, 2)}


@router.post("/like")
def toggle_like(
    signal: LikeSignal,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Toggle like: nếu đã like thì unlike, ngược lại thì like. Return state mới."""
    video = db.query(models.Video).filter(models.Video.id == signal.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video không tồn tại")

    existing = db.query(models.Like).filter(
        models.Like.user_id == current_user.id,
        models.Like.video_id == signal.video_id,
    ).first()

    profile = _get_or_create_user_profile(db, current_user.id)

    if existing:
        db.delete(existing)
        video.like_count = max(0, (video.like_count or 1) - 1)
        # Unlike → giảm weight
        for tag in _get_video_tags(db, signal.video_id):
            _update_tag_preference(db, profile, tag, -0.2)
        liked = False
    else:
        new_like = models.Like(user_id=current_user.id, video_id=signal.video_id)
        db.add(new_like)
        video.like_count = (video.like_count or 0) + 1
        # Like → mạnh (+0.5 mỗi tag)
        for tag in _get_video_tags(db, signal.video_id):
            _update_tag_preference(db, profile, tag, 0.5)
        profile.interaction_count = (profile.interaction_count or 0) + 1
        profile.last_active_at = datetime.now(timezone.utc)
        liked = True

    db.commit()
    return {"liked": liked, "like_count": video.like_count}


@router.post("/follow")
def toggle_follow(
    signal: FollowSignal,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Toggle follow creator. Return state mới."""
    if signal.following_id == current_user.id:
        raise HTTPException(status_code=400, detail="Không thể tự follow mình")

    target = db.query(models.User).filter(models.User.id == signal.following_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User không tồn tại")

    existing = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.following_id == signal.following_id,
    ).first()

    if existing:
        db.delete(existing)
        followed = False
    else:
        new_follow = models.Follow(
            follower_id=current_user.id,
            following_id=signal.following_id,
        )
        db.add(new_follow)
        followed = True

    db.commit()
    return {"followed": followed}
