"""Collaborative filtering: tìm users tương tự (đã like cùng videos) → recommend videos họ thích.

Approach: User-User cosine similarity trên like vector (sparse).
Đơn giản, không cần ML. Scale 1K users OK.
"""
import math
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import models
from database import SessionLocal


def build_user_like_matrix(db) -> Tuple[Dict[int, Set[int]], Dict[int, Set[int]]]:
    """
    Build 2 dicts:
    - user_likes[user_id] = set of video_ids user đã like
    - video_likers[video_id] = set of user_ids đã like video
    Returns: (user_likes, video_likers)
    """
    user_likes: Dict[int, Set[int]] = defaultdict(set)
    video_likers: Dict[int, Set[int]] = defaultdict(set)

    likes = db.query(models.Like.user_id, models.Like.video_id).all()
    for user_id, video_id in likes:
        user_likes[user_id].add(video_id)
        video_likers[video_id].add(user_id)

    return dict(user_likes), dict(video_likers)


def find_similar_users(
    target_user_id: int,
    user_likes: Dict[int, Set[int]],
    top_k: int = 20,
) -> List[Tuple[int, float]]:
    """
    Tìm top K users tương tự target_user theo Jaccard similarity trên like set.
    Returns list of (user_id, similarity_score).
    """
    target_set = user_likes.get(target_user_id, set())
    if not target_set:
        return []

    scores: List[Tuple[int, float]] = []
    for other_id, other_set in user_likes.items():
        if other_id == target_user_id or not other_set:
            continue
        intersection = len(target_set & other_set)
        if intersection == 0:
            continue
        union = len(target_set | other_set)
        similarity = intersection / union if union > 0 else 0
        if similarity > 0:
            scores.append((other_id, similarity))

    scores.sort(key=lambda x: -x[1])
    return scores[:top_k]


def collaborative_score(
    target_user_id: int,
    video_id: int,
    user_likes: Dict[int, Set[int]],
    similar_users: List[Tuple[int, float]] = None,
) -> float:
    """
    Score 0..1: weighted sum of similar users' likes cho video này.
    Weight = similarity. Normalize bằng tổng weight của top users.
    """
    if not user_likes:
        return 0.0

    if similar_users is None:
        similar_users = find_similar_users(target_user_id, user_likes, top_k=20)
    if not similar_users:
        return 0.0

    total_weight = 0.0
    matched_weight = 0.0
    for other_id, similarity in similar_users:
        total_weight += similarity
        if video_id in user_likes.get(other_id, set()):
            matched_weight += similarity

    if total_weight == 0:
        return 0.0
    return matched_weight / total_weight


def recommend_videos_for_user(
    target_user_id: int,
    user_likes: Dict[int, Set[int]],
    video_likers: Dict[int, Set[int]],
    top_k: int = 50,
    exclude_videos: Set[int] = None,
) -> List[Tuple[int, float]]:
    """
    Recommend top K videos mà target_user CHƯA like, dựa trên similar users' likes.
    Returns list of (video_id, score) sorted desc.
    """
    if exclude_videos is None:
        exclude_videos = set()
    exclude_videos |= user_likes.get(target_user_id, set())  # loại video user đã like

    similar_users = find_similar_users(target_user_id, user_likes, top_k=20)
    if not similar_users:
        return []

    # Aggregate: video → tổng weighted score
    video_scores: Dict[int, float] = defaultdict(float)
    for other_id, similarity in similar_users:
        for video_id in user_likes.get(other_id, set()):
            if video_id in exclude_videos:
                continue
            video_scores[video_id] += similarity

    # Normalize bằng số similar users đã like video (giảm thiên vị video viral)
    ranked = []
    for video_id, raw_score in video_scores.items():
        normalized = raw_score / max(1, len(similar_users))
        ranked.append((video_id, normalized))

    ranked.sort(key=lambda x: -x[1])
    return ranked[:top_k]
