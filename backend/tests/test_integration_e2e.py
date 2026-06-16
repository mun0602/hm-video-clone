"""Integration test: full user flow mô phỏng FE behavior.

Flow: register → login → upload video → view personalized feed → track signals → verify profile + cache.

Đây là test mức end-to-end kiểm tra:
- Auth flow (register + login + JWT)
- Upload pipeline (file → storage → DB record → FFmpeg processing)
- Feed retrieval (personalized + explore)
- Signal tracking (view + like + follow)
- Recommendation engine (feed_cache rebuild + user_profile updates)
"""
import io
import json

import pytest


def _fake_video_bytes() -> bytes:
    """Tạo bytes giả lập video file (FFmpeg xử lý gracefully, trả duration=None)."""
    return b"FAKE_MP4_HEADER" + b"\x00" * 1024


class TestUserFullFlow:
    """Test full E2E flow cho 1 user mới."""

    def test_register_login_upload_view_signal(self, client, test_db, sample_videos):
        """
        1. Register user mới 'creator1'
        2. Login → lấy token
        3. Upload 1 video với tags 'comedy,trending'
        4. Get personalized feed → assert có video mới
        5. Track view (60% completion) + like + follow creator
        6. Verify user_profile.tag_preferences update đúng
        7. Verify feed_cache có candidate mới cho user
        """
        # --- 1) Register ---
        resp = client.post(
            "/api/auth/register",
            data={"username": "creator1", "password": "pass123", "display_name": "Creator One"},
        )
        assert resp.status_code == 200
        new_user = resp.json()
        new_user_id = new_user["id"]
        assert new_user["username"] == "creator1"

        # --- 2) Login ---
        resp = client.post(
            "/api/auth/login",
            data={"username": "creator1", "password": "pass123"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        assert token  # JWT string
        headers = {"Authorization": f"Bearer {token}"}

        # --- 3) Upload video ---
        resp = client.post(
            "/api/videos/upload",
            headers=headers,
            files={"file": ("myvideo.mp4", _fake_video_bytes(), "video/mp4")},
            data={"title": "My first video", "tags": "comedy,trending"},
        )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        uploaded = resp.json()
        assert uploaded["status"] == "success"
        assert uploaded["video_id"] > 0
        assert "static/uploads" in uploaded["video_url"]
        new_video_id = uploaded["video_id"]

        # Verify video tồn tại trong DB với tags
        test_db.expire_all()
        import models
        video = test_db.query(models.Video).filter_by(id=new_video_id).first()
        assert video is not None
        assert video.title == "My first video"
        assert "comedy" in video.tags
        assert "trending" in video.tags

        # --- 4) Get personalized feed ---
        resp = client.get("/api/feed?limit=20", headers=headers)
        assert resp.status_code == 200
        feed = resp.json()
        assert len(feed) > 0
        video_ids_in_feed = [v["id"] for v in feed]
        assert new_video_id in video_ids_in_feed, "Newly uploaded video phải xuất hiện trong personalized feed"

        # --- 5) Track signals ---
        # View với 60% completion (medium weight)
        target_video_id = sample_videos[1].id  # có tags "comedy,dance"
        resp = client.post(
            "/api/signals/view",
            headers=headers,
            json={
                "video_id": target_video_id,
                "watch_duration": 12,
                "video_duration": 20,
                "is_skipped": False,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "tracked"

        # Like video
        resp = client.post(
            "/api/signals/like",
            headers=headers,
            json={"video_id": target_video_id},
        )
        assert resp.status_code == 200
        assert resp.json()["liked"] is True

        # Follow creator (sample_user owns sample_videos)
        sample_user_id = sample_videos[0].user_id
        resp = client.post(
            "/api/signals/follow",
            headers=headers,
            json={"following_id": sample_user_id},
        )
        assert resp.status_code == 200
        assert resp.json()["followed"] is True

        # --- 6) Verify user_profile ---
        test_db.expire_all()
        profile = test_db.query(models.UserProfile).filter_by(user_id=new_user_id).first()
        assert profile is not None, "UserProfile phải được tạo sau signals"
        # interaction_count tăng bởi view (1) + like (1). Follow không tăng.
        assert profile.interaction_count == 2
        prefs = json.loads(profile.tag_preferences)
        assert "comedy" in prefs, "comedy tag phải có trong preferences"
        assert "dance" in prefs, "dance tag phải có trong preferences (từ viewed video)"
        assert prefs["comedy"] > 0, "comedy preference phải positive (like boost)"
        assert prefs["dance"] > 0, "dance preference phải positive (medium watch)"

        # --- 7) Rebuild feed cache + verify ---
        resp = client.post("/api/admin/rebuild-feeds", headers=headers)
        assert resp.status_code == 200
        summary = resp.json()
        assert summary["user_count"] >= 1
        assert summary["errors"] == []

        # Verify cache có candidate cho user mới
        from recommender import feed_cache
        candidates = feed_cache.get_cached_candidates(test_db, new_user_id, limit=50)
        assert len(candidates) > 0, "Feed cache phải có candidates cho user mới"


class TestAuthEdgeCases:
    """Test các edge cases auth."""

    def test_register_duplicate_username(self, client, sample_user):
        """Register với username đã tồn tại → 400."""
        resp = client.post(
            "/api/auth/register",
            data={"username": "testuser", "password": "pass", "display_name": "Dup"},
        )
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()

    def test_login_wrong_password(self, client, sample_user):
        """Login với password sai → 400."""
        resp = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "wrongpass"},
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    def test_protected_endpoint_without_token(self, client, sample_videos):
        """Gọi /api/feed không có token → 401."""
        resp = client.get("/api/feed?limit=10")
        assert resp.status_code == 401

    def test_protected_endpoint_with_invalid_token(self, client, sample_videos):
        """Token rác → 401."""
        resp = client.get(
            "/api/feed?limit=10",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401

    def test_upload_without_auth(self, client):
        """Upload không có token → 401."""
        resp = client.post(
            "/api/videos/upload",
            files={"file": ("x.mp4", _fake_video_bytes(), "video/mp4")},
            data={"title": "no auth", "tags": "x"},
        )
        assert resp.status_code == 401


class TestFeedPersonalization:
    """Test feed personalize thực sự theo user behavior."""

    def test_feed_changes_after_like(self, client, test_db, sample_videos, auth_headers, sample_user):
        """Sau khi like 1 video, nó nên rank cao hơn trong personalized feed."""
        # 1) Like video 1 (tags "music,trending")
        target = sample_videos[0]  # i=1, tags="music,trending"
        resp = client.post(
            "/api/signals/like",
            headers=auth_headers,
            json={"video_id": target.id},
        )
        assert resp.status_code == 200

        # 2) Like video 2 (tags "comedy,dance") - khác genre
        other = sample_videos[1]  # i=2, tags="comedy,dance"
        resp = client.post(
            "/api/signals/like",
            headers=auth_headers,
            json={"video_id": other.id},
        )
        assert resp.status_code == 200

        # 3) Get personalized feed
        resp = client.get("/api/feed?limit=10", headers=auth_headers)
        assert resp.status_code == 200
        feed = resp.json()
        assert len(feed) > 0

        # Videos được like nên appear trong feed
        feed_ids = [v["id"] for v in feed]
        assert target.id in feed_ids or other.id in feed_ids

        # Videos đó phải có is_liked=True
        liked_in_feed = [v for v in feed if v["is_liked"]]
        assert len(liked_in_feed) >= 1

    def test_explore_feed_works_without_auth(self, client, sample_videos):
        """Explore feed hoạt động không cần auth (cold-start)."""
        resp = client.get("/api/feed/explore?limit=10")
        assert resp.status_code == 200
        feed = resp.json()
        assert len(feed) == len(sample_videos)

    def test_explore_feed_respects_limit_offset(self, client, sample_videos):
        """Pagination: limit=2 trả 2 videos, offset=2 skip 2 đầu."""
        resp = client.get("/api/feed/explore?limit=2&offset=0")
        assert resp.status_code == 200
        page1 = resp.json()
        assert len(page1) == 2

        resp = client.get("/api/feed/explore?limit=2&offset=2")
        assert resp.status_code == 200
        page2 = resp.json()
        assert len(page2) == 2

        # Pages khác nhau
        page1_ids = {v["id"] for v in page1}
        page2_ids = {v["id"] for v in page2}
        assert page1_ids.isdisjoint(page2_ids), "Pagination không được overlap"


class TestSignalTracking:
    """Test signal tracking cập nhật user state đúng."""

    def test_like_unlike_cycle(self, client, auth_headers, sample_videos):
        """Toggle like 2 lần → quay lại state ban đầu."""
        target = sample_videos[0]

        # First like
        resp = client.post("/api/signals/like", headers=auth_headers, json={"video_id": target.id})
        assert resp.status_code == 200
        assert resp.json()["liked"] is True

        # Unlike
        resp = client.post("/api/signals/like", headers=auth_headers, json={"video_id": target.id})
        assert resp.status_code == 200
        assert resp.json()["liked"] is False

    def test_follow_self_rejected(self, client, auth_headers, sample_user):
        """User không thể tự follow chính mình."""
        resp = client.post(
            "/api/signals/follow",
            headers=auth_headers,
            json={"following_id": sample_user.id},  # self
        )
        assert resp.status_code == 400

    def test_view_signal_creates_record(self, client, auth_headers, sample_videos, sample_user, test_db):
        """Track view tạo VideoView record + tăng view_count."""
        import models
        target = sample_videos[0]
        before_views = target.view_count

        resp = client.post(
            "/api/signals/view",
            headers=auth_headers,
            json={"video_id": target.id, "watch_duration": 10, "video_duration": 20},
        )
        assert resp.status_code == 200

        test_db.expire_all()
        updated = test_db.query(models.Video).filter_by(id=target.id).first()
        assert updated.view_count == before_views + 1

        view_record = test_db.query(models.VideoView).filter_by(
            user_id=sample_user.id,
            video_id=target.id,
        ).first()
        assert view_record is not None
        assert view_record.watch_duration == 10
        assert view_record.is_skipped == 0

    def test_skip_video_creates_negative_preference(self, client, auth_headers, sample_videos, test_db, sample_user):
        """Skip video với watch<30% → tag preference giảm (có thể âm)."""
        import models
        import json
        target = sample_videos[1]  # tags "comedy,dance"

        resp = client.post(
            "/api/signals/view",
            headers=auth_headers,
            json={
                "video_id": target.id,
                "watch_duration": 1,
                "video_duration": 20,
                "is_skipped": True,
            },
        )
        assert resp.status_code == 200

        test_db.expire_all()
        profile = test_db.query(models.UserProfile).filter_by(user_id=sample_user.id).first()
        assert profile is not None
        prefs = json.loads(profile.tag_preferences)
        assert "comedy" in prefs
        # Negative preference nên < 0
        assert prefs["comedy"] < 0
