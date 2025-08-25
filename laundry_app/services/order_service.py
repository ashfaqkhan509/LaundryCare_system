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

    # Ensure both datetimes are timezone-aware
    if order.pickup_time.tzinfo is None:
        # If pickup_time is naive, it's in local time (from database), convert to UTC

        # Get the local timezone offset from the environment or default to UTC+5
        local_tz_offset = int(os.environ.get('TZ_OFFSET', 5))  # Default to UTC+5
        local_tz = timezone(timedelta(hours=local_tz_offset))
        pickup_time = order.pickup_time.replace(tzinfo=local_tz)
        # Convert to UTC
        pickup_time = pickup_time.astimezone(timezone.utc)
    else:
        pickup_time = order.pickup_time

    time_diff = (pickup_time - now).total_seconds() / 3600  # in hours

    if cancelled_by == "customer":
        if time_diff > 1:
            return 0.0
        else:
            return float(order.total_price) * CANCELLATION_FEE_PERCENT

    elif cancelled_by in ["worker", "admin"]:
        if time_diff <= 1:
            return float(order.total_price) * CANCELLATION_FEE_PERCENT
        return 0.0
