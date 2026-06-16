"""Popularity scoring: kết hợp view/like count + freshness decay.

TikTok-style: video mới được boost trong 24-48h đầu để khuyến khích upload mới.
"""
import math
from datetime import datetime, timezone
from typing import Optional

import models


# Half-life (giờ) cho freshness decay. Sau 48h, video mất ~50% boost.
FRESHNESS_HALF_LIFE_HOURS = 48


def popularity_score(video: models.Video, now: Optional[datetime] = None) -> float:
    """
    Score 0..1 kết hợp:
    - Engagement: log(1 + view_count) + 2 * log(1 + like_count)
    - Freshness: exp decay với half-life 48h
    Returns 0..1 (sau normalize).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Engagement: log scale để giảm thiên vị video viral cực đoan
    views = video.view_count or 0
    likes = video.like_count or 0
    raw_engagement = math.log1p(views) + 2 * math.log1p(likes)

    # Freshness: 1.0 cho video mới (<1h), decay theo exp
    hours_old = _hours_since(video.created_at, now)
    freshness = math.pow(0.5, hours_old / FRESHNESS_HALF_LIFE_HOURS) if hours_old else 1.0

    # Combine
    return raw_engagement * freshness


def normalized_popularity_score(video: models.Video, max_score: float, now: Optional[datetime] = None) -> float:
    """Normalize popularity score về 0..1 dựa trên max_score trong batch."""
    if max_score <= 0:
        return 0.0
    return min(1.0, popularity_score(video, now) / max_score)


def _hours_since(dt: Optional[datetime], now: datetime) -> float:
    if not dt:
        return 9999.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return max(0.0, delta.total_seconds() / 3600.0)
