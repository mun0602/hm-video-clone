"""Signal tracking tests: view, like, follow + user profile updates."""


def test_view_tracking_creates_record(client, auth_headers, sample_videos, test_db):
    """POST /api/signals/view tạo VideoView + tăng view_count."""
    import models
    video = sample_videos[0]
    initial_views = video.view_count or 0

    response = client.post(
        "/api/signals/view",
        headers=auth_headers,
        json={
            "video_id": video.id,
            "watch_duration": 10,
            "video_duration": 20,
            "is_skipped": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "tracked"
    assert data["completion"] == 0.5  # 10/20

    # Verify DB: view_count tăng 1
    test_db.expire_all()
    video_after = test_db.query(models.Video).filter_by(id=video.id).first()
    assert video_after.view_count == initial_views + 1


def test_view_with_skip_increments_user_preferences_negatively(client, auth_headers, sample_videos, test_db):
    """Skip video → user profile có negative weight cho tags."""
    import models
    import json
    # sample_videos[1] có tags "comedy,dance" (i=2, even)
    video = sample_videos[1]
    assert "comedy" in (video.tags or "")

    client.post(
        "/api/signals/view",
        headers=auth_headers,
        json={
            "video_id": video.id,
            "watch_duration": 1,
            "video_duration": 20,
            "is_skipped": True,
        },
    )
    test_db.expire_all()
    profile = test_db.query(models.UserProfile).filter_by(user_id=1).first()
    assert profile is not None
    prefs = json.loads(profile.tag_preferences)
    assert "comedy" in prefs
    assert prefs["comedy"] < 0  # negative


def test_view_with_high_completion_boosts_preferences(client, auth_headers, sample_videos, test_db):
    """Watch >70% → +0.3 mỗi tag."""
    import models
    import json
    # sample_videos[1] có tags "comedy,dance" (i=2, even)
    video = sample_videos[1]

    client.post(
        "/api/signals/view",
        headers=auth_headers,
        json={
            "video_id": video.id,
            "watch_duration": 18,
            "video_duration": 20,
            "is_skipped": False,
        },
    )
    test_db.expire_all()
    profile = test_db.query(models.UserProfile).filter_by(user_id=1).first()
    prefs = json.loads(profile.tag_preferences)
    assert prefs["comedy"] == pytest.approx(0.3, abs=0.01)


def test_like_toggle_creates_and_removes(client, auth_headers, sample_videos, test_db):
    """Toggle like: like → unlike → like state changes correctly."""
    video = sample_videos[0]

    # First like
    r1 = client.post("/api/signals/like", headers=auth_headers, json={"video_id": video.id})
    assert r1.status_code == 200
    assert r1.json()["liked"] is True

    # Second toggle = unlike
    r2 = client.post("/api/signals/like", headers=auth_headers, json={"video_id": video.id})
    assert r2.json()["liked"] is False


def test_like_increments_video_count(client, auth_headers, sample_videos, test_db):
    """Like tăng like_count trên video."""
    import models
    video = sample_videos[0]
    initial = video.like_count or 0

    client.post("/api/signals/like", headers=auth_headers, json={"video_id": video.id})

    test_db.expire_all()
    v = test_db.query(models.Video).filter_by(id=video.id).first()
    assert v.like_count == initial + 1


def test_follow_self_fails(client, auth_headers, sample_user):
    """Follow chính mình → 400."""
    response = client.post(
        "/api/signals/follow",
        headers=auth_headers,
        json={"following_id": sample_user.id},
    )
    assert response.status_code == 400


def test_follow_creates_relationship(client, auth_headers, test_db):
    """Follow user khác → tạo Follow row."""
    import models
    from auth_utils import get_password_hash
    other = models.User(
        username="otheruser",
        hashed_password=get_password_hash("pass"),
        display_name="Other",
    )
    test_db.add(other)
    test_db.commit()
    test_db.refresh(other)

    response = client.post(
        "/api/signals/follow",
        headers=auth_headers,
        json={"following_id": other.id},
    )
    assert response.status_code == 200
    assert response.json()["followed"] is True

    # Verify
    test_db.expire_all()
    follow = test_db.query(models.Follow).filter_by(follower_id=1, following_id=other.id).first()
    assert follow is not None


# Cần import pytest ở top-level để dùng pytest.approx
import pytest
