from datetime import datetime, timedelta, timezone
from laundry_app.models import Order, OrderStatus
import os


# Define valid state transitions
VALID_TRANSITIONS = {
    OrderStatus.CREATED: {OrderStatus.ACCEPTED, OrderStatus.CANCELLED},
    OrderStatus.ACCEPTED: {OrderStatus.PICKED_UP, OrderStatus.CANCELLED},
    OrderStatus.PICKED_UP: {OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED},
    OrderStatus.IN_PROGRESS: {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.DELIVERED: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.COMPLETED: set(),   # Final state
    OrderStatus.CANCELLED: set(),   # Final state
}

CANCELLATION_FEE_PERCENT = 0.20  # 20%


def calculate_cancellation_fee(order: Order, cancelled_by: str) -> float:
    """Calculate cancellation fee based on rules."""
    # Use timezone-aware datetime for comparison
    now = datetime.now(timezone.utc)
    print(f"DEBUG: Current UTC time: {now}")

    # Ensure both datetimes are timezone-aware
    if order.pickup_time.tzinfo is None:
        # If pickup_time is naive, it's in local time (from database), convert to UTC
        local_tz_offset = int(os.environ.get('TZ_OFFSET', 5))  # Default to UTC+5
        local_tz = timezone(timedelta(hours=local_tz_offset))
        pickup_time = order.pickup_time.replace(tzinfo=local_tz)
        # Convert to UTC
        pickup_time = pickup_time.astimezone(timezone.utc)
    else:
        pickup_time = order.pickup_time

    print(f"DEBUG: Pickup UTC time: {pickup_time}")

    time_diff = (pickup_time - now).total_seconds() / 3600  # in hours
    print(f"DEBUG: Time difference: {time_diff} hours")
    print(f"DEBUG: Order price: {order.total_price}")
    print(f"DEBUG: Cancelled by: {cancelled_by}")

    if cancelled_by == "customer":
        if time_diff > 1:
            print("DEBUG: Free cancellation (more than 1 hour)")
            return 0.0
        else:
            fee = float(order.total_price) * CANCELLATION_FEE_PERCENT
            print(f"DEBUG: Charging fee: {fee}")
            return fee

    elif cancelled_by in ["worker", "admin"]:
        if time_diff <= 1:
            return float(order.total_price) * CANCELLATION_FEE_PERCENT
        return 0.0
