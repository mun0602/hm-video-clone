"""Auth tests: register, login, JWT decode, current user dependency."""


def test_register_success(client):
    """Register user mới với username + password + display_name."""
    response = client.post(
        "/api/auth/register",
        data={
            "username": "newuser",
            "password": "newpass123",
            "display_name": "New User",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["display_name"] == "New User"
    assert "id" in data
    # Không leak password
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_username(client, sample_user):
    """Register với username đã tồn tại → 400."""
    response = client.post(
        "/api/auth/register",
        data={
            "username": sample_user.username,
            "password": "whatever",
            "display_name": "Dup",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_login_success(client, sample_user):
    """Login với credentials đúng → trả token."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["id"] == sample_user.id
    assert data["username"] == "testuser"


def test_login_wrong_password(client, sample_user):
    """Login sai password → 400."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "wrongpassword"},
    )
    assert response.status_code == 400


def test_login_nonexistent_user(client):
    """Login với user không tồn tại → 400."""
    response = client.post(
        "/api/auth/login",
        data={"username": "ghost", "password": "whatever"},
    )
    assert response.status_code == 400


def test_protected_endpoint_no_token(client):
    """GET /api/feed không có token → 401."""
    response = client.get("/api/feed")
    assert response.status_code == 401


def test_protected_endpoint_invalid_token(client):
    """GET /api/feed với token rác → 401."""
    response = client.get("/api/feed", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_protected_endpoint_valid_token(client, auth_headers, sample_videos):
    """GET /api/feed với token hợp lệ → 200."""
    response = client.get("/api/feed", headers=auth_headers)
    assert response.status_code == 200
    # Có thể empty hoặc có items, chỉ cần không lỗi
    assert isinstance(response.json(), list)
