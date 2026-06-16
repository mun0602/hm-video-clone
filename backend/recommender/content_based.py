"""Content-based scoring: dựa trên tags của video so với tag preferences của user.

Pure Python implementation (no sklearn) — đủ cho 10K videos.
Algorithm: cosine similarity giữa user profile vector và video tags vector.
"""
import hashlib
import math
import pickle
from collections import Counter
from typing import Dict, List

import models
from database import SessionLocal


def _tokenize_tags(tags_string: str) -> List[str]:
    """Tách tags string thành list. Empty/None → []."""
    if not tags_string:
        return []
    return [t.strip().lower() for t in tags_string.split(",") if t.strip()]


def _hash_tags(tags_string: str) -> str:
    """Hash để detect khi tags đổi (invalidate cache)."""
    return hashlib.md5((tags_string or "").encode()).hexdigest()


def build_video_embedding(tags_string: str) -> Dict[str, float]:
    """
    Build TF-IDF-style embedding cho 1 video.
    Với 1 video chỉ có tags, "TF" = 1, "IDF" được tính global (tính sau ở build_corpus_idf).
    Ở đây return raw term-frequency dict {tag: count}.
    """
    tokens = _tokenize_tags(tags_string)
    if not tokens:
        return {}
    counter = Counter(tokens)
    # Normalize bằng max count → giảm ảnh hưởng của video có quá nhiều cùng tag
    max_count = max(counter.values())
    return {tag: count / max_count for tag, count in counter.items()}


def build_corpus_idf(video_embeddings: List[Dict[str, float]]) -> Dict[str, float]:
    """Tính IDF weights từ corpus. Input: list of all video embeddings."""
    n = len(video_embeddings)
    if n == 0:
        return {}
    df: Counter = Counter()
    for emb in video_embeddings:
        for tag in emb.keys():
            df[tag] += 1
    # Smoothed IDF
    return {tag: math.log((n + 1) / (count + 1)) + 1 for tag, count in df.items()}


def apply_idf(embedding: Dict[str, float], idf: Dict[str, float]) -> Dict[str, float]:
    """Nhân TF với IDF để ra TF-IDF vector."""
    return {tag: tf * idf.get(tag, 1.0) for tag, tf in embedding.items()}


def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Cosine similarity giữa 2 sparse vectors (dicts)."""
    if not v1 or not v2:
        return 0.0
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    norm1 = math.sqrt(sum(x * x for x in v1.values()))
    norm2 = math.sqrt(sum(x * x for x in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


# ============================================================
# DB-backed helpers
# ============================================================

def get_or_compute_video_embedding(db, video: models.Video) -> Dict[str, float]:
    """
    Lấy embedding từ cache (video_embeddings) hoặc compute + lưu cache.
    Returns raw TF vector (chưa nhân IDF) — IDF áp dụng ở similarity step.
    """
    tags_str = video.tags or ""
    tags_hash = _hash_tags(tags_str)

    cached = db.query(models.VideoEmbedding).filter(models.VideoEmbedding.video_id == video.id).first()
    if cached and cached.tag_hash == tags_hash:
        return pickle.loads(cached.embedding)

    # Compute fresh
    embedding = build_video_embedding(tags_str)
    embedding_bytes = pickle.dumps(embedding)

    if cached:
        cached.embedding = embedding_bytes
        cached.tag_hash = tags_hash
        cached.updated_at = models.func.now()
    else:
        new_emb = models.VideoEmbedding(
            video_id=video.id,
            embedding=embedding_bytes,
            tag_hash=tags_hash,
        )
        db.add(new_emb)

    return embedding


def get_user_tag_vector(db, user_id: int) -> Dict[str, float]:
    """Lấy tag preferences của user từ UserProfile, parse JSON thành vector."""
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    if not profile or not profile.tag_preferences:
        return {}
    import json
    try:
        return json.loads(profile.tag_preferences)
    except json.JSONDecodeError:
        return {}


def content_score(
    user_tag_vector: Dict[str, float],
    video_embedding: Dict[str, float],
) -> float:
    """
    Score 0..1: cosine sim giữa user tag vector và video embedding.
    """
    return cosine_similarity(user_tag_vector, video_embedding)
