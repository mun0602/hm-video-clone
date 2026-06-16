"""User profile endpoints: get user, follow list, follow status."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
from auth_utils import get_current_user, get_optional_current_user
from database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_summary(user: models.User, is_followed: bool = False) -> dict:
    """Build compact user representation cho profile + follow lists."""
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "is_followed": is_followed,
    }


@router.get("/{username}")
def get_user_by_username(
    username: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
):
    """
    Lấy profile user theo username. Trả về kèm:
    - follower/following counts
    - is_followed: true nếu current_user đang follow user này
    """
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User không tồn tại")

    follower_count = db.query(models.Follow).filter(
        models.Follow.following_id == user.id
    ).count()
    following_count = db.query(models.Follow).filter(
        models.Follow.follower_id == user.id
    ).count()
    like_count = db.query(models.Like).join(models.Video).filter(
        models.Video.user_id == user.id
    ).count()

    is_followed = False
    if current_user and current_user.id != user.id:
        is_followed = db.query(models.Follow).filter(
            models.Follow.follower_id == current_user.id,
            models.Follow.following_id == user.id,
        ).first() is not None

    return {
        **_user_summary(user, is_followed),
        "follower_count": follower_count,
        "following_count": following_count,
        "like_count": like_count,
    }


@router.get("/me/following-ids")
def get_my_following_ids(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Trả về list user IDs mà current_user đang follow."""
    rows = db.query(models.Follow.following_id).filter(
        models.Follow.follower_id == current_user.id
    ).all()
    return [r[0] for r in rows]


@router.get("/me/followers-ids")
def get_my_followers_ids(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Trả về list user IDs đang follow current_user."""
    rows = db.query(models.Follow.follower_id).filter(
        models.Follow.following_id == current_user.id
    ).all()
    return [r[0] for r in rows]


@router.get("/me/following")
def get_my_following_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Trả về list users mà current_user đang follow (full info)."""
    follows = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id
    ).all()
    target_ids = [f.following_id for f in follows]
    if not target_ids:
        return []
    users = db.query(models.User).filter(models.User.id.in_(target_ids)).all()
    return [_user_summary(u) for u in users]


@router.get("/me/followers")
def get_my_followers_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Trả về list users đang follow current_user (full info)."""
    follows = db.query(models.Follow).filter(
        models.Follow.following_id == current_user.id
    ).all()
    target_ids = [f.follower_id for f in follows]
    if not target_ids:
        return []
    users = db.query(models.User).filter(models.User.id.in_(target_ids)).all()
    return [_user_summary(u) for u in users]


@router.get("/{user_id}/videos")
def get_user_videos(
    user_id: int,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
):
    """
    Lấy videos của 1 creator. Trả về list videos serialized giống feed API.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User không tồn tại")

    videos = (
        db.query(models.Video)
        .filter(models.Video.user_id == user_id)
        .order_by(models.Video.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Reuse helper từ api/feed.py
    from api.feed import _build_video_response
    return [_build_video_response(v, current_user, db) for v in videos]
