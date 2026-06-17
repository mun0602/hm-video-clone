"""Feed API: personalized video feed với online re-rank.

GET /api/feed         - personalized (cần auth, dùng recommender)
GET /api/feed/explore - cold-start / public (popularity + fresh only)
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

import models
from auth_utils import get_current_user, get_optional_current_user
from database import get_db
from recommender import feed_cache, online_re_rank, popularity
from api.utils import build_video_responses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feed", tags=["feed"])

# ============================================================
# Endpoints
# ============================================================

@router.get("")
def get_personalized_feed(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Personalized feed cho user đã login.
    - Stage 1: lấy candidates từ feed_cache (offline-computed)
    - Stage 2: online re-rank với freshness + diversity + exploration
    - Fallback: nếu cache miss/expire → build on-demand (chậm hơn lần đầu)
    """
    # 1) Lấy candidates từ cache
    candidates = feed_cache.get_cached_candidates(db, current_user.id, limit=200)

    if not candidates:
        # Cache miss → build on-demand
        logger.info(f"Cache miss for user {current_user.id}, building on-demand")
        feed_cache.build_feed_for_user(db, current_user.id)
        candidates = feed_cache.get_cached_candidates(db, current_user.id, limit=200)

    if not candidates:
        # Vẫn không có (DB rỗng) → fallback explore
        return _explore_fallback(db, current_user, limit, offset)

    # 2) Hydrate videos
    video_ids = [fc.video_id for fc in candidates]
    videos = db.query(models.Video).filter(models.Video.id.in_(video_ids)).all()
    videos_by_id = {v.id: v for v in videos}

    # 3) Online re-rank
    ranked_ids = online_re_rank.rerank_candidates(
        candidates=candidates,
        videos_by_id=videos_by_id,
        user_id=current_user.id,
        limit=limit,
    )

    # 4) Apply offset (nếu user swipe xa)
    if offset > 0:
        ranked_ids = ranked_ids[offset:]
        ranked_ids = ranked_ids[:limit]

    # 5) Build response
    videos_ranked = [videos_by_id[vid] for vid in ranked_ids if vid in videos_by_id]
    return build_video_responses(videos_ranked, current_user, db, request)


@router.get("/explore")
def get_explore_feed(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
):
    """
    Public explore feed: popularity + freshness, không cần auth.
    Dùng cho: cold-start user, public landing page, /explore tab.
    """
    return _explore_fallback(db, current_user, limit, offset, request)


def _explore_fallback(
    db: Session,
    current_user: Optional[models.User],
    limit: int,
    offset: int,
    request: Optional[Request] = None,
) -> List[dict]:
    """Fallback: sort toàn bộ video theo popularity score (engagement + freshness)."""
    videos = db.query(models.Video).all()
    if not videos:
        return []

    pop_max = max(popularity.popularity_score(v) for v in videos) or 1.0
    scored = [
        (v, popularity.normalized_popularity_score(v, pop_max))
        for v in videos
    ]
    scored.sort(key=lambda x: -x[1])

    # Apply offset + limit
    paginated = scored[offset:offset + limit]
    videos_paginated = [v for v, _ in paginated]
    return build_video_responses(videos_paginated, current_user, db, request)
