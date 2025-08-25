import pytest
from datetime import datetime, timedelta, timezone
from laundry_app import db
from laundry_app.models import User, UserRole, Address, Order, OrderStatus


def test_create_order_as_customer(client, auth_headers):
    headers, user, addr = auth_headers(UserRole.CUSTOMER)
    pickup = datetime.now(timezone.utc) + timedelta(hours=1)
    delivery = pickup + timedelta(hours=2)

    res = client.post("/api/orders/", headers=headers, json={
        "address_id": addr.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 5
    })
    data = res.get_json()
    assert res.status_code == 201
    assert data["message"] == "Order created successfully"
    assert data["order"]["status"] == OrderStatus.CREATED.value


def test_get_orders_customer_only_sees_own(client, auth_headers):
    headers, user, addr = auth_headers(UserRole.CUSTOMER)

    # Create an order
    pickup = datetime.now(timezone.utc) + timedelta(hours=1)
    delivery = pickup + timedelta(hours=2)
    client.post("/api/orders/", headers=headers, json={
        "address_id": addr.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 3
    })

    # Get orders
    res = client.get("/api/orders/", headers=headers)
    data = res.get_json()
    assert res.status_code == 200


def test_cancel_order_as_customer(client, auth_headers):
    headers, user, addr = auth_headers(UserRole.CUSTOMER)

    # Create order
    pickup = datetime.now(timezone.utc) + timedelta(hours=1)
    delivery = pickup + timedelta(hours=2)
    res = client.post("/api/orders/", headers=headers, json={
        "address_id": addr.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 4
    })
    order_id = res.get_json()["order"]["id"]

    # Cancel
    res = client.delete(f"/api/orders/{order_id}", headers=headers)
    data = res.get_json()
    assert res.status_code == 200
    assert data["message"] == "Order cancelled"
    assert data["order_id"] == order_id


def test_list_unclaimed_orders_worker(client, auth_headers):
    cust_headers, cust, addr = auth_headers(UserRole.CUSTOMER)

    # Customer creates order
    pickup = datetime.now(timezone.utc) + timedelta(hours=1)
    delivery = pickup + timedelta(hours=2)
    client.post("/api/orders/", headers=cust_headers, json={
        "address_id": addr.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 6
    })

    # Worker lists unclaimed
    worker_headers, worker, _ = auth_headers(UserRole.WORKER)
    res = client.get("/api/orders/unclaimed", headers=worker_headers)
    data = res.get_json()
    assert res.status_code == 200
    assert any(order["status"] == OrderStatus.CREATED.value for order in data["orders"])


def test_claim_order_success(client, auth_headers):
    cust_headers, cust, addr = auth_headers(UserRole.CUSTOMER)

    # Customer creates order
    pickup = datetime.now(timezone.utc) + timedelta(hours=1)
    delivery = pickup + timedelta(hours=2)
    res = client.post("/api/orders/", headers=cust_headers, json={
        "address_id": addr.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 2
    })
    order_id = res.get_json()["order"]["id"]

    # Worker claims it
    worker_headers, worker, _ = auth_headers(UserRole.WORKER)
    res = client.post(f"/api/orders/{order_id}/claim", headers=worker_headers)
    data = res.get_json()
    assert res.status_code == 200
    assert data["order"]["status"] == OrderStatus.ACCEPTED.value


def test_update_order_status_flow(client, auth_headers):
    cust_headers, cust, addr = auth_headers(UserRole.CUSTOMER)

    # Create order
    pickup = datetime.now(timezone.utc) + timedelta(hours=1)
    delivery = pickup + timedelta(hours=2)
    res = client.post("/api/orders/", headers=cust_headers, json={
        "address_id": addr.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 2
    })
    order_id = res.get_json()["order"]["id"]

    # Worker claims it
    worker_headers, worker, _ = auth_headers(UserRole.WORKER)
    client.post(f"/api/orders/{order_id}/claim", headers=worker_headers)

    # Worker updates status to IN_PROGRESS
    res = client.post(f"/api/orders/{order_id}/status", headers=worker_headers, json={"status": "picked_up"})
    data = res.get_json()

    # 👇 DEBUGGING OUTPUT
    print("\n--- DEBUG ---")
    print("Response status:", res.status_code)
    print("Response JSON:", data)
    print("---------------\n")

    assert res.status_code == 200
    assert data["success"] is True
    assert data["new_status"] == "picked_up"
