from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import Request

import models

def build_video_responses(
    videos: List[models.Video],
    current_user: Optional[models.User],
    db: Session,
    request: Optional[Request] = None,
) -> List[dict]:
    if not videos:
        return []

    video_ids = [v.id for v in videos]
    creator_ids = list(set(v.user_id for v in videos))

    liked_video_ids = set()
    followed_user_ids = set()

    if current_user:
        # Batch query for likes
        likes = db.query(models.Like.video_id).filter(
            models.Like.user_id == current_user.id,
            models.Like.video_id.in_(video_ids)
        ).all()
        liked_video_ids = {like.video_id for like in likes}

        # Batch query for follows
        follows = db.query(models.Follow.following_id).filter(
            models.Follow.follower_id == current_user.id,
            models.Follow.following_id.in_(creator_ids)
        ).all()
        followed_user_ids = {f.following_id for f in follows}

    # Batch query for comment counts
    comment_counts = dict(
        db.query(models.Comment.video_id, func.count(models.Comment.id))
        .filter(models.Comment.video_id.in_(video_ids))
        .group_by(models.Comment.video_id)
        .all()
    )

    def _abs(url: Optional[str]) -> Optional[str]:
        if not url or not request:
            return url
        if url.startswith(("http://", "https://")):
            return url
        # Bỏ trailing slash ở base_url, thêm vào nếu path chưa có slash
        base_url = str(request.base_url).rstrip("/")
        if not url.startswith("/"):
            url = "/" + url
        return base_url + url

    responses = []
    for video in videos:
        is_liked = video.id in liked_video_ids
        is_followed = video.user_id in followed_user_ids
        comment_count = comment_counts.get(video.id, 0)

        responses.append({
            "id": video.id,
            "description": video.title,
            "file_url": _abs(video.video_url),
            "thumb_url": _abs(video.cover_url),
            "tags": [t.strip() for t in (video.tags or "").split(",") if t.strip()],
            "duration_seconds": video.duration_seconds,
            "created_at": video.created_at.isoformat() if video.created_at else None,
            "view_count": video.view_count or 0,
            "like_count": video.like_count or 0,
            "comment_count": comment_count,
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
        })
    return responses

def build_single_video_response(
    video: models.Video,
    current_user: Optional[models.User],
    db: Session,
    request: Optional[Request] = None,
) -> dict:
    return build_video_responses([video], current_user, db, request)[0]
