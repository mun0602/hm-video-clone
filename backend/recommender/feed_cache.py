"""Feed cache: build, store, fetch. Offline job sẽ gọi build_all_users()."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import models
from database import SessionLocal

from . import hybrid

logger = logging.getLogger(__name__)

# Cache TTL (giờ). Sau khi expire, user phải chờ offline refresh hoặc rơi vào fallback.
FEED_CACHE_TTL_HOURS = 3


def build_feed_for_user(db, user_id: int) -> int:
    """
    Build feed_cache cho 1 user. Returns số candidates đã lưu.
    Xoá cache cũ trước khi insert mới.
    """
    candidates = hybrid.build_candidates_for_user(db, user_id, limit=hybrid.FEED_CACHE_SIZE)
    if not candidates:
        logger.info(f"No candidates for user {user_id}")
        return 0

    # Xoá cache cũ
    db.query(models.FeedCache).filter(models.FeedCache.user_id == user_id).delete()

    expires_at = datetime.now(timezone.utc) + timedelta(hours=FEED_CACHE_TTL_HOURS)
    now = datetime.now(timezone.utc)

    rows = []
    for rank, (video_id, score) in enumerate(candidates):
        rows.append(models.FeedCache(
            user_id=user_id,
            video_id=video_id,
            score=score,
            rank=rank,
            computed_at=now,
            expires_at=expires_at,
        ))
    db.bulk_save_objects(rows)
    db.commit()
    logger.info(f"Built {len(rows)} candidates for user {user_id}")
    return len(rows)


def build_feed_for_all_users() -> dict:
    """
    Build feed cache cho tất cả users. Dùng cho offline scheduler job.
    Returns summary {user_count, total_candidates, duration_seconds, errors}.
    """
    import time
    start = time.time()
    db = SessionLocal()
    summary = {"user_count": 0, "total_candidates": 0, "errors": []}
    try:
        user_ids = [u.id for u in db.query(models.User.id).all()]
        summary["user_count"] = len(user_ids)
        for uid in user_ids:
            try:
                n = build_feed_for_user(db, uid)
                summary["total_candidates"] += n
            except Exception as e:
                logger.exception(f"Failed to build feed for user {uid}")
                summary["errors"].append({"user_id": uid, "error": str(e)})
    finally:
        db.close()
    summary["duration_seconds"] = round(time.time() - start, 2)
    logger.info(f"Feed cache build summary: {summary}")
    return summary


def get_cached_candidates(db, user_id: int, limit: int = 200) -> List[models.FeedCache]:
    """
    Lấy candidates từ cache (sort theo rank asc).
    Nếu cache expire hoặc không có → return [].
    Caller (feed API) sẽ trigger fallback build on-demand.
    """
    now = datetime.now(timezone.utc)
    rows = (
        db.query(models.FeedCache)
        .filter(
            models.FeedCache.user_id == user_id,
            models.FeedCache.expires_at > now,
        )
        .order_by(models.FeedCache.rank.asc())
        .limit(limit)
        .all()
    )
    return rows


def is_cache_fresh(db, user_id: int) -> bool:
    """Check xem user có cache còn fresh không."""
    now = datetime.now(timezone.utc)
    return (
        db.query(models.FeedCache)
        .filter(
            models.FeedCache.user_id == user_id,
            models.FeedCache.expires_at > now,
        )
        .first()
        is not None
    )
