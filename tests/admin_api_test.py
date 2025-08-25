import pytest
from datetime import datetime, timedelta, timezone
from laundry_app.models import User, UserRole, Order, OrderStatus
from laundry_app import db


@pytest.fixture
def worker_user():
    worker = User(
        name="Worker",
        email="worker@test.com",
        phone="3333333333",
        role=UserRole.WORKER
    )
    worker.set_password("pass123")
    db.session.add(worker)
    db.session.commit()
    return worker


def test_get_orders_as_admin(client, auth_headers):
    headers, _, _ = auth_headers(UserRole.ADMIN)
    res = client.get("/api/admin/orders", headers=headers)
    assert res.status_code == 200
    assert "orders" in res.get_json()


def test_get_orders_as_non_admin(client, auth_headers):
    headers, _, _ = auth_headers(UserRole.CUSTOMER)
    res = client.get("/api/admin/orders", headers=headers)
    assert res.status_code == 403


def test_create_order_as_admin(client, auth_headers, worker_user):
    headers, _, _ = auth_headers(UserRole.ADMIN)
    customer_headear, user, address = auth_headers(UserRole.CUSTOMER)
    worker = worker_user

    pickup = datetime.now(timezone.utc) + timedelta(hours=2)
    delivery = pickup + timedelta(hours=2)

    res = client.post("/api/admin/orders", headers=headers, json={
        "customer_id": user.id,
        "worker_id": worker.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 3,
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["order"]["id"] is not None
    assert data["order"]["status"] == "created"


def test_create_order_with_invalid_customer(client, auth_headers, worker_user):
    headers, _, _ = auth_headers(UserRole.ADMIN)
    worker = worker_user
    pickup = datetime.now(timezone.utc) + timedelta(hours=2)
    delivery = pickup + timedelta(hours=2)

    res = client.post("/api/admin/orders", headers=headers, json={
        "customer_id": 9999,
        "worker_id": worker.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 3,
    })
    assert res.status_code == 404


def test_admin_cancel_order(client, auth_headers, worker_user):
    headers, admin, _ = auth_headers(UserRole.ADMIN)
    customer_headear, user, address = auth_headers(UserRole.CUSTOMER)
    worker = worker_user

    pickup = datetime.now(timezone.utc) + timedelta(hours=2)
    delivery = pickup + timedelta(hours=4)

    order = Order(
        customer_id=user.id,
        address_id=address.id,
        worker_id=worker.id,
        created_by=admin.id,
        pickup_time=pickup,
        delivery_time=delivery,
        total_price=200,
        status=OrderStatus.ACCEPTED,
    )
    db.session.add(order)
    db.session.commit()

    res = client.delete(f"/api/admin/{order.id}", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["order_id"] == order.id
    assert "cancellation_fee" in data


def test_add_worker_as_admin(client, auth_headers):
    headers, _, _ = auth_headers(UserRole.ADMIN)
    res = client.post("/api/admin/workers", headers=headers, json={
        "name": "New Worker",
        "email": "newworker@test.com",
        "phone": "4444444444",
        "password": "pass123"
    })
    assert res.status_code == 201
    assert res.get_json()["worker"]["role"] == "worker"


def test_edit_worker_as_admin(client, auth_headers, worker_user):
    headers, _, _ = auth_headers(UserRole.ADMIN)
    res = client.put(f"/api/admin/workers/{worker_user.id}", headers=headers, json={
        "name": "Updated Worker"
    })
    assert res.status_code == 200
    assert res.get_json()["worker"]["name"] == "Updated Worker"


def test_assign_customer_to_worker(client, auth_headers, worker_user):
    headers, _, _ = auth_headers(UserRole.ADMIN)
    customer_headers, user, _ = auth_headers(UserRole.CUSTOMER)
    res = client.post(f"/api/admin/{worker_user.id}/assign_customer", headers=headers, json={
        "customer_id": user.id
    })
    assert res.status_code == 200
    assert f"Customer {user.id}" in res.get_json()["message"]
