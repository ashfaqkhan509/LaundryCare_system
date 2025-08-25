import pytest
from datetime import datetime, timedelta, timezone

from laundry_app.models import Order, OrderStatus, UserRole
from laundry_app.services.order_service import CANCELLATION_FEE_PERCENT


def create_order(client, cust_headers, addr, pickup_delta_hours=2, price=100):
    """Helper to create a test order."""
    pickup = datetime.now(timezone.utc) + timedelta(hours=pickup_delta_hours)
    delivery = pickup + timedelta(hours=2)

    res = client.post("/api/orders/", headers=cust_headers, json={
        "address_id": addr.id,
        "pickup_time": pickup.isoformat(),
        "delivery_time": delivery.isoformat(),
        "weight_kg": 2,
        "price": price
    })
    return res.get_json()["order"]


def test_customer_can_cancel_own_order_free_if_more_than_1h(client, auth_headers):
    customer_headers, cust, addr = auth_headers(UserRole.CUSTOMER)
    order = create_order(client, customer_headers, addr, pickup_delta_hours=2, price=200)

    res = client.delete(f"/api/orders/{order['id']}", headers=customer_headers)
    data = res.get_json()

    assert res.status_code == 200
    assert data["message"] == "Order cancelled"
    assert data["cancellation_fee"] == 0.0


def test_customer_cancels_within_1h_pays_fee(client, auth_headers):
    customer_headers, cust, addr = auth_headers(UserRole.CUSTOMER)
    order = create_order(client, customer_headers, addr, pickup_delta_hours=0.5, price=200)

    res = client.delete(f"/api/orders/{order['id']}", headers=customer_headers)
    data = res.get_json()

    assert res.status_code == 200
    expected_fee = order["total_price"] * CANCELLATION_FEE_PERCENT
    assert data["cancellation_fee"] == pytest.approx(expected_fee)


def test_customer_cannot_cancel_someone_elses_order(client, auth_headers):
    customer_headers1, cust1, addr1 = auth_headers(UserRole.CUSTOMER)
    order = create_order(client, customer_headers1, addr1, pickup_delta_hours=2, price=150)

    # Another customer tries to cancel
    customer_headers2, cust2, addr2 = auth_headers(UserRole.CUSTOMER)
    res = client.delete(f"/api/orders/{order['id']}", headers=customer_headers2)
    data = res.get_json()

    assert res.status_code == 403
    assert "only cancel your own orders" in data["error"].lower()


def test_worker_can_cancel_assigned_order_within_1h_fee_applies(client, auth_headers):
    customer_headers, cust, addr = auth_headers(UserRole.CUSTOMER)
    order = create_order(client, customer_headers, addr, pickup_delta_hours=0.5, price=300)

    # Worker claims it
    worker_headers, worker, _ = auth_headers(UserRole.WORKER)
    client.post(f"/api/orders/{order['id']}/claim", headers=worker_headers)

    # Worker cancels
    res = client.delete(f"/api/orders/{order['id']}", headers=worker_headers)
    data = res.get_json()

    assert res.status_code == 200
    expected_fee = order["total_price"] * CANCELLATION_FEE_PERCENT
    assert data["cancellation_fee"] == pytest.approx(expected_fee)


def test_worker_cannot_cancel_unassigned_order(client, auth_headers):
    customer_headers1, cust, addr = auth_headers(UserRole.CUSTOMER)
    order = create_order(client, customer_headers1, addr)

    worker_headers, worker, _ = auth_headers(UserRole.WORKER)
    res = client.delete(f"/api/orders/{order['id']}", headers=worker_headers)
    data = res.get_json()

    assert res.status_code == 403
    assert "only cancel orders assigned" in data["error"].lower()
