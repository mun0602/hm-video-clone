"""Pytest fixtures: in-memory SQLite, test client, sample data."""
import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend root to sys.path để import được modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env trước khi import config
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")

from database import Base, get_db
import models
from auth_utils import get_password_hash


@pytest.fixture
def test_db_engine():
    """In-memory SQLite engine cho tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db(test_db_engine):
    """Session bound to test engine."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(test_db_engine, monkeypatch):
    """FastAPI TestClient với dependency override."""
    from main import app
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Tắt scheduler cho tests
    import scheduler
    monkeypatch.setattr(scheduler, "start_scheduler", lambda: None)
    monkeypatch.setattr(scheduler, "stop_scheduler", lambda: None)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user(test_db):
    """Tạo 1 user mẫu, return User object."""
    user = models.User(
        username="testuser",
        hashed_password=get_password_hash("testpass123"),
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
        bio="Test bio",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_videos(test_db, sample_user):
    """Tạo 5 videos mẫu với tags khác nhau."""
    videos = [
        models.Video(
            title=f"Test video {i}",
            video_url=f"https://example.com/v{i}.mp4",
            cover_url=f"https://example.com/v{i}.jpg",
            tags="comedy,dance" if i % 2 == 0 else "music,trending",
            user_id=sample_user.id,
            view_count=10 * i,
            like_count=2 * i,
        )
        for i in range(1, 6)
    ]
    for v in videos:
        test_db.add(v)
    test_db.commit()
    for v in videos:
        test_db.refresh(v)
    return videos


@pytest.fixture
def auth_token(client, sample_user):
    """Login và lấy JWT token."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
