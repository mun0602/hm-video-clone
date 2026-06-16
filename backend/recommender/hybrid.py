"""Hybrid scoring: kết hợp content + collaborative + popularity thành 1 final score.

Mỗi signal được weighted:
- content: 0.4 (ưu tiên cá nhân hoá theo tag)
- collaborative: 0.4 (ưu tiên cộng đồng)
- popularity: 0.2 (boost cho video hot, tránh filter bubble)

Cold-start: user mới (no interactions) → dùng popularity-only.
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

import models
from database import SessionLocal

from . import collaborative, content_based, popularity

logger = logging.getLogger(__name__)

# Trọng số các signals (tổng = 1.0)
W_CONTENT = 0.4
W_COLLABORATIVE = 0.4
W_POPULARITY = 0.2

# Số candidates mỗi user lưu trong feed_cache
FEED_CACHE_SIZE = 200

# Ngưỡng coi user là cold-start
COLD_START_INTERACTION_THRESHOLD = 3


def is_cold_start_user(db, user_id: int) -> bool:
    """User mới = no UserProfile hoặc < N interactions."""
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    if not profile:
        return True
    return (profile.interaction_count or 0) < COLD_START_INTERACTION_THRESHOLD


def score_video_for_user(
    db,
    user_id: int,
    video: models.Video,
    user_likes: Dict[int, Set[int]],
    similar_users: List[Tuple[int, float]],
    pop_max_score: float,
) -> float:
    """
    Tính hybrid score cho 1 video theo 1 user.
    """
    if is_cold_start_user(db, user_id):
        # Cold-start: chỉ dùng popularity
        return popularity.normalized_popularity_score(video, pop_max_score)

    user_tag_vector = content_based.get_user_tag_vector(db, user_id)
    video_embedding = content_based.get_or_compute_video_embedding(db, video)

    c_score = content_based.content_score(user_tag_vector, video_embedding)
    cf_score = collaborative.collaborative_score(user_id, video.id, user_likes, similar_users)
    p_score = popularity.normalized_popularity_score(video, pop_max_score)

    return W_CONTENT * c_score + W_COLLABORATIVE * cf_score + W_POPULARITY * p_score


def build_candidates_for_user(
    db,
    user_id: int,
    limit: int = FEED_CACHE_SIZE,
) -> List[Tuple[int, float]]:
    """
    Build top N candidates cho 1 user (cho feed_cache).
    Trả về list of (video_id, score) sorted desc.
    """
    is_cold = is_cold_start_user(db, user_id)

    # 1) Pre-compute popularity max cho normalize
    videos = db.query(models.Video).all()
    if not videos:
        return []
    pop_max = max(popularity.popularity_score(v) for v in videos) or 1.0

    # 2) Build user-user similarity (chỉ dùng khi không cold)
    user_likes, video_likers = collaborative.build_user_like_matrix(db)
    if is_cold:
        similar_users = []
    else:
        similar_users = collaborative.find_similar_users(user_id, user_likes, top_k=20)

    # 3) Lấy candidate pool
    # - Nếu user follow creators → ưu tiên videos của following
    # - Nếu không → toàn bộ video catalog
    # Tránh videos user đã xem quá nhiều / đã skip gần đây
    excluded_ids = _get_excluded_videos(db, user_id)

    if is_cold:
        # Cold: chỉ sort theo popularity
        scored = [
            (v.id, popularity.normalized_popularity_score(v, pop_max))
            for v in videos if v.id not in excluded_ids
        ]
    else:
        # Warm: hybrid score
        scored = []
        for v in videos:
            if v.id in excluded_ids:
                continue
            s = score_video_for_user(db, user_id, v, user_likes, similar_users, pop_max)
            scored.append((v.id, s))

    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


def _get_excluded_videos(db, user_id: int, lookback_days: int = 7) -> Set[int]:
    """
    Videos cần loại khỏi feed:
    - User đã like (optional — có thể giữ để re-watch)
    - User đã skip gần đây
    - User đã xem full gần đây
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    excluded: Set[int] = set()

    # Skip trong lookback window
    skipped = (
        db.query(models.VideoView.video_id)
        .filter(
            models.VideoView.user_id == user_id,
            models.VideoView.is_skipped == 1,
            models.VideoView.created_at >= cutoff,
        )
        .all()
    )
    excluded.update(v[0] for v in skipped)

    return excluded
