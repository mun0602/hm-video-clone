"""Recommender unit tests: content-based, collaborative, popularity, hybrid."""
import json
import pytest

from recommender import content_based, collaborative, popularity, hybrid


# ============================================================
# Content-based
# ============================================================

def test_build_video_embedding_normalizes():
    """TF normalize bằng max count."""
    emb = content_based.build_video_embedding("comedy,comedy,dance")
    # comedy=2, dance=1, max=2 → comedy: 2/2=1.0, dance: 1/2=0.5
    assert emb["comedy"] == 1.0
    assert emb["dance"] == 0.5  # normalize → thấp hơn max

    emb2 = content_based.build_video_embedding("comedy,comedy,dance,dance,dance")
    # comedy=2, dance=3, max=3 → comedy: 2/3≈0.67, dance: 3/3=1.0
    assert emb2["comedy"] < emb2["dance"]


def test_build_video_embedding_empty():
    """Empty/None tags → empty embedding."""
    assert content_based.build_video_embedding("") == {}
    assert content_based.build_video_embedding(None) == {}


def test_cosine_similarity_identical():
    v = {"comedy": 0.5, "dance": 0.3}
    assert content_based.cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    v1 = {"comedy": 1.0}
    v2 = {"music": 1.0}
    assert content_based.cosine_similarity(v1, v2) == 0.0


def test_cosine_similarity_partial_overlap():
    v1 = {"comedy": 0.5, "dance": 0.5}
    v2 = {"comedy": 0.5, "music": 0.5}
    sim = content_based.cosine_similarity(v1, v2)
    assert 0 < sim < 1


def test_cosine_similarity_empty():
    assert content_based.cosine_similarity({}, {"a": 1}) == 0.0
    assert content_based.cosine_similarity({"a": 1}, {}) == 0.0


# ============================================================
# Collaborative
# ============================================================

def test_find_similar_users_no_data():
    """User không có likes → return []."""
    user_likes = {1: {10, 20}, 2: {10, 20}}
    similar = collaborative.find_similar_users(999, user_likes)
    assert similar == []


def test_find_similar_users_jaccard():
    """Users với overlap cao → similarity cao."""
    user_likes = {
        1: {10, 20, 30},
        2: {10, 20, 40},  # 2/4 = 0.5 jaccard
        3: {50, 60},      # 0/5 = 0
    }
    similar = collaborative.find_similar_users(1, user_likes, top_k=5)
    assert len(similar) == 1
    user_id, score = similar[0]
    assert user_id == 2
    assert score == pytest.approx(0.5)


def test_collaborative_score_no_likes():
    """User chưa like gì → score = 0."""
    user_likes = {1: set(), 2: {10, 20}}
    score = collaborative.collaborative_score(1, 10, user_likes)
    assert score == 0.0


def test_recommend_videos_excludes_seen():
    """Videos user đã like bị loại khỏi recommend."""
    user_likes = {
        1: {10, 20},  # user 1 đã like 10, 20
        2: {10, 30},
        3: {20, 30, 40},
    }
    recs = collaborative.recommend_videos_for_user(1, user_likes, {}, top_k=10)
    rec_ids = [v[0] for v in recs]
    assert 10 not in rec_ids  # đã like
    assert 20 not in rec_ids  # đã like
    assert 30 in rec_ids or 40 in rec_ids  # recommend


# ============================================================
# Popularity
# ============================================================

def test_popularity_score_engagement_log_scale():
    """Engagement tăng theo log scale."""
    import models
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    v_low = models.Video(id=1, view_count=10, like_count=1, created_at=now)
    v_high = models.Video(id=2, view_count=10000, like_count=1000, created_at=now)

    s_low = popularity.popularity_score(v_low, now)
    s_high = popularity.popularity_score(v_high, now)
    # log(1+10000) + 2*log(1+1000) >> log(11) + 2*log(2)
    assert s_high > s_low * 2


def test_popularity_freshness_decay():
    """Video cũ → score thấp hơn video mới cùng engagement."""
    import models
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    last_week = now - timedelta(days=7)

    v_new = models.Video(id=1, view_count=100, like_count=10, created_at=now)
    v_yesterday = models.Video(id=2, view_count=100, like_count=10, created_at=yesterday)
    v_old = models.Video(id=3, view_count=100, like_count=10, created_at=last_week)

    s_new = popularity.popularity_score(v_new, now)
    s_old = popularity.popularity_score(v_old, now)
    assert s_new > s_old


def test_normalized_popularity_zero_max():
    """Max score = 0 → normalized = 0 (no division by zero)."""
    import models
    from datetime import datetime, timezone
    v = models.Video(id=1, view_count=0, like_count=0, created_at=datetime.now(timezone.utc))
    score = popularity.normalized_popularity_score(v, max_score=0)
    assert score == 0.0


# ============================================================
# Hybrid + cold-start
# ============================================================

def test_is_cold_start_no_profile(test_db, sample_user):
    """User chưa có UserProfile → cold-start."""
    assert hybrid.is_cold_start_user(test_db, sample_user.id) is True


def test_is_cold_start_low_interactions(test_db, sample_user):
    """User có profile nhưng <3 interactions → cold-start."""
    import models
    profile = models.UserProfile(user_id=sample_user.id, interaction_count=2)
    test_db.add(profile)
    test_db.commit()
    assert hybrid.is_cold_start_user(test_db, sample_user.id) is True


def test_is_not_cold_start_high_interactions(test_db, sample_user):
    """User có ≥3 interactions → warm."""
    import models
    profile = models.UserProfile(user_id=sample_user.id, interaction_count=10)
    test_db.add(profile)
    test_db.commit()
    assert hybrid.is_cold_start_user(test_db, sample_user.id) is False


def test_build_candidates_cold_start_returns_popularity_sorted(test_db, sample_videos):
    """Cold-start user → candidates sorted theo popularity."""
    candidates = hybrid.build_candidates_for_user(test_db, user_id=1, limit=10)
    assert len(candidates) > 0
    # Sorted desc by score
    scores = [s for _, s in candidates]
    assert scores == sorted(scores, reverse=True)


def test_build_candidates_excludes_skip_history(test_db, sample_user, sample_videos):
    """Video user đã skip gần đây bị loại."""
    import models
    from datetime import datetime, timezone

    # Mark first video as skipped by user
    skip_view = models.VideoView(
        user_id=sample_user.id,
        video_id=sample_videos[0].id,
        watch_duration=0,
        is_skipped=1,
    )
    test_db.add(skip_view)
    test_db.commit()

    candidates = hybrid.build_candidates_for_user(test_db, user_id=sample_user.id, limit=20)
    candidate_ids = [v_id for v_id, _ in candidates]
    assert sample_videos[0].id not in candidate_ids
