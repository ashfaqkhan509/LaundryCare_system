from laundry_app.models import UserRole


def test_signup_success(client):
    """Test successful signup."""
    res = client.post("/auth/signup", json={
        "name": "Test User",
        "email": "test@example.com",
        "phone": "1234567890",
        "password": "test123",
        "role": "customer"
    })
    data = res.get_json()
    assert res.status_code == 201
    assert data["message"] == "User signup successfully"
    assert data["user"]["email"] == "test@example.com"


def test_signup_duplicate_email(client, create_user):
    """Signup should fail if email already exists."""
    create_user("Test1", "test1@example.com", "password123")
    res = client.post("/auth/signup", json={
        "name": "Test1",
        "email": "test1@example.com",
        "phone": "1112223333",
        "password": "password123",
        "role": "customer"
    })
    assert res.status_code == 409
    assert res.get_json()["message"] == "Email already exists"


def test_customer_login_success(client, create_user):
    """Customer login with valid credentials."""
    create_user("Cust", "cust@example.com", "custpass", UserRole.CUSTOMER)
    res = client.post("/auth/customer/login", json={
        "email": "cust@example.com",
        "password": "custpass"
    })
    data = res.get_json()
    assert res.status_code == 200
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["role"] == "customer"


def test_customer_login_invalid_password(client, create_user):
    """Login should fail with wrong password."""
    create_user("Cust", "cust2@example.com", "rightpass", UserRole.CUSTOMER)
    res = client.post("/auth/customer/login", json={
        "email": "cust2@example.com",
        "password": "wrongpass"
    })
    assert res.status_code == 401
    assert res.get_json()["message"] == "Invalid email or password"


def test_worker_login_success(client, create_user):
    """Worker login works correctly."""
    create_user("Worker1", "worker@example.com", "workerpass", UserRole.WORKER)
    res = client.post("/auth/worker/login", json={
        "email": "worker@example.com",
        "password": "workerpass"
    })
    data = res.get_json()
    assert res.status_code == 200
    assert "access_token" in data
    assert data["user"]["role"] == "worker"


def test_admin_login_success(client, create_user):
    """Admin login works correctly."""
    create_user("Admin1", "admin@example.com", "adminpass", UserRole.ADMIN)
    res = client.post("/auth/admin/login", json={
        "email": "admin@example.com",
        "password": "adminpass"
    })
    data = res.get_json()
    assert res.status_code == 200
    assert data["user"]["role"] == "admin"


def test_admin_login_not_admin(client, create_user):
    """Login as non-admin should fail with 403."""
    create_user("NotAdmin", "notadmin@example.com", "pass123", UserRole.CUSTOMER)
    res = client.post("/auth/admin/login", json={
        "email": "notadmin@example.com",
        "password": "pass123"
    })
    assert res.status_code == 403
    assert "User is not admin" in res.get_json()["error"]


def test_profile_get_and_update(client, create_user):
    """Test fetching and updating user profile."""
    user = create_user("user", "user@example.com", "password123", UserRole.CUSTOMER)

    # Login to get token
    res = client.post("/auth/customer/login", json={
        "email": "user@example.com",
        "password": "password123"
    })
    token = res.get_json()["access_token"]

    # Get profile
    res = client.get("/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.get_json()["email"] == "user@example.com"

    # Update profile
    res = client.put("/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "New Name", "phone": "9876543210"}
    )
    assert res.status_code == 200
    assert res.get_json()["message"] == "Profile updated successfully"


def test_logout(client, create_user):
    """Test JWT logout (token added to blocklist)."""
    create_user("LogoutUser", "logout@example.com", "logoutpass", UserRole.CUSTOMER)

    res = client.post("/auth/customer/login", json={
        "email": "logout@example.com",
        "password": "logoutpass"
    })
    token = res.get_json()["access_token"]

    # Logout
    res = client.post("/auth/api/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.get_json()["message"] == "Successfully logged out"
