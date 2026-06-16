"""Online re-rank: lấy candidates từ cache, áp dụng context-based re-ranking.

Stage 2 của hybrid approach. Mục tiêu:
- Inject freshness boost cho video chưa được user thấy
- Đảm bảo diversity (tránh 5 video cùng creator liên tiếp)
- Exploration: chèn 1-2 random video để tránh filter bubble
"""
import logging
import random
from collections import Counter
from datetime import datetime, timezone
from typing import List, Tuple

import models

logger = logging.getLogger(__name__)


def rerank_candidates(
    candidates: List[models.FeedCache],
    videos_by_id: dict,
    user_id: int,
    limit: int = 20,
    exploration_ratio: float = 0.1,
    diversity_window: int = 3,
) -> List[int]:
    """
    Re-rank candidates từ feed_cache, return list of video_id đã được rerank.

    Args:
        candidates: list FeedCache rows (đã sort theo rank)
        videos_by_id: dict mapping video_id → Video
        user_id: target user
        limit: số video trả về
        exploration_ratio: tỷ lệ random inject (0.1 = 10%)
        diversity_window: không cho 2 video cùng creator trong window này
    """
    if not candidates:
        return []

    # 1) Lấy top pool rộng hơn limit (gấp 2-3 lần) để có lựa chọn
    pool_size = min(len(candidates), limit * 3)
    pool = candidates[:pool_size]

    # 2) Boost freshness cho video mới (<24h)
    now = datetime.now(timezone.utc)
    scored: List[Tuple[int, float, int]] = []  # (video_id, adjusted_score, creator_id)
    for fc in pool:
        video = videos_by_id.get(fc.video_id)
        if not video:
            continue
        base = fc.score

        # Freshness boost: video <6h → +0.3, 6-24h → +0.1, >24h → 0
        if video.created_at:
            if video.created_at.tzinfo is None:
                created = video.created_at.replace(tzinfo=timezone.utc)
            else:
                created = video.created_at
            hours = max(0, (now - created).total_seconds() / 3600)
            if hours < 6:
                base += 0.3
            elif hours < 24:
                base += 0.1

        scored.append((fc.video_id, base, video.user_id))

    # 3) Sort theo score
    scored.sort(key=lambda x: -x[1])

    # 4) Apply diversity: không cho cùng creator lặp lại trong window
    result: List[int] = []
    creator_counts: Counter = Counter()
    for video_id, _score, creator_id in scored:
        if creator_counts[creator_id] >= 2 and len(result) >= diversity_window:
            # Đã có 2 video của creator này rồi → skip
            continue
        result.append(video_id)
        creator_counts[creator_id] += 1
        if len(result) >= limit:
            break

    # 5) Exploration: inject 1-2 random video từ toàn bộ DB
    # (Lấy từ candidates chưa được chọn)
    n_explore = max(1, int(limit * exploration_ratio))
    chosen_set = set(result)
    pool_ids = [fc.video_id for fc in pool if fc.video_id not in chosen_set]
    if pool_ids:
        random.shuffle(pool_ids)
        explore_ids = pool_ids[:n_explore]
        # Chèn explore ở các vị trí ngẫu nhiên trong feed
        for i, vid in enumerate(explore_ids):
            insert_pos = min(len(result), (i + 1) * (limit // (n_explore + 1)))
            result.insert(insert_pos, vid)

    # Trim về limit
    return result[:limit]
