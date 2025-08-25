from datetime import datetime
import pytest
from laundry_app.models import Address, User, UserRole
from laundry_app import create_app, db
from laundry_app.config import TestConfig


@pytest.fixture(scope="session")
def app():
    """
    Create a Flask app configured for testing.
    """
    app = create_app()
    app.config.from_object(TestConfig)

    with app.app_context():
        db.create_all()
        yield app

        # Don’t use db.drop_all() because of FK dependencies
        # Instead just leave the schema intact after tests
        db.session.remove()


@pytest.fixture(scope="session")
def client(app):
    """
    Flask test client for sending requests.
    """
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """
    Automatically clean the database before each test.
    """
    with app.app_context():
        # First, rollback any pending transactions
        db.session.rollback()
        
        # Delete all data from tables in proper order
        meta = db.metadata
        for table in reversed(meta.sorted_tables):
            db.session.execute(table.delete())
        
        db.session.commit()
        db.session.remove()


@pytest.fixture
def create_user():
    """Helper factory to create users easily."""
    def _create_user(name, email, password, role=UserRole.CUSTOMER, phone="1234567890"):
        user = User(name=name, email=email, phone=phone, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user
    return _create_user


@pytest.fixture
def create_user_with_address(create_user):
    """Factory to create a user with at least one address."""
    def _create_user_with_address(name, email, password, role=UserRole.CUSTOMER, phone=None):
        if phone is None:
            # Generate a more unique phone number
            import time
            import random
            phone = f"12345{role.value[-3:]}{int(time.time() * 1000000)}{random.randint(1000, 9999)}"  # more unique
        user = create_user(name, email, password, role=role, phone=phone)
        addr = Address(
            user_id=user.id,
            street="123 Main St",
            area="DHA",
            city="Lahore",
            postal_code="54000"
        )
        db.session.add(addr)
        db.session.commit()
        return user, addr
    return _create_user_with_address



@pytest.fixture
def auth_headers(client, create_user_with_address):
    """Helper: create a user & login for given role, returns (headers, user, addr)."""
    def _auth_headers(role=UserRole.CUSTOMER):
        # Generate unique email for each test to avoid conflicts
        import time
        email = f"{role.value}_{int(time.time() * 1000000)}@example.com"
        user, addr = create_user_with_address(role.value, email, "pass123", role=role)
        
        # Map roles to login endpoints
        login_endpoints = {
            UserRole.CUSTOMER: "/auth/customer/login",
            UserRole.WORKER: "/auth/worker/login",
            UserRole.ADMIN: "/auth/admin/login",
        }
        
        login_url = login_endpoints[role]
        
        res = client.post(login_url, json={"email": email, "password": "pass123"})
        
        data = res.get_json()
        assert data is not None, "Login did not return JSON"
        assert "access_token" in data, f"Login failed: {data}"
        
        token = data["access_token"]
        return {"Authorization": f"Bearer {token}"}, user, addr
    return _auth_headers