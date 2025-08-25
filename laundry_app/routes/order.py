from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from laundry_app import db
from laundry_app.models import User, UserRole, Order, Address, OrderStatus
from laundry_app.services.auth_service import AuthService
from laundry_app.services.order_service import VALID_TRANSITIONS, calculate_cancellation_fee


orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@orders_bp.route("/", methods=["POST"])
@jwt_required()
def create_order():
    """
    Create a new laundry order.

    - Customers can create their own orders. Default status = CREATED.
    - Workers can create an order on behalf of an assigned customer. Default status = ACCEPTED.
    - Admins are not allowed to create orders from this endpoint.

    Validations:
      - Customer must exist and have at least one address.
      - `address_id` must belong to the customer.
      - Required fields: pickup_time, delivery_time, weight_kg.
      - pickup_time < delivery_time.
      - weight_kg must be > 0.

    Pricing:
      - Uses a flat rate per kilogram (100 PKR/kg in this example).

    Returns:
      JSON response with created order details.
    """
    try:
        current_user = AuthService.get_current_user()
        data = request.get_json()

        if current_user.role == UserRole.CUSTOMER:
            customer_id = current_user.id
            creator_id = current_user.id
            status = OrderStatus.CREATED

        elif current_user.role == UserRole.WORKER:
            customer_id = data.get("customer_id")
            if not customer_id:
                return jsonify({"error": "customer_id is required when worker creates an order"}), 400

            # Check if that customer is assigned to this worker
            customer = User.query.filter_by(id=customer_id, role=UserRole.CUSTOMER).first()
            if not customer or customer.worker_id != current_user.id:
                return jsonify({"error": "This customer is not assigned to you"}), 403

            creator_id = current_user.id
            status = OrderStatus.ACCEPTED

        else:
            return jsonify({"error": "Invalid role"}), 403

        # Validate customer exists
        customer = User.query.filter_by(id=customer_id, role=UserRole.CUSTOMER).first()
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        if not customer.addresses:
            return jsonify({"error": "Customer must have at least one address"}), 400

        # Validate address_id
        address_id = data.get("address_id")
        address = Address.query.filter_by(id=address_id, user_id=customer.id).first()
        if not address:
            return jsonify({"error": "Invalid address_id for this customer"}), 400

        # Required fields
        required_fields = ["pickup_time", "delivery_time", "weight_kg"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        # Parse datetimes
        try:
            pickup_time = datetime.fromisoformat(data["pickup_time"].replace("Z", "+00:00"))
            delivery_time = datetime.fromisoformat(data["delivery_time"].replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "Invalid datetime format"}), 400

        if delivery_time <= pickup_time:
            return jsonify({"error": "Delivery time must be after pickup time"}), 400
        
        # Calculate total price (100 PKR per kg for example)
        try:
            weight_kg = float(data["weight_kg"])
        except ValueError:
            return jsonify({"error": "weight_kg must be a number"}), 400

        if weight_kg <= 0:
            return jsonify({"error": "weight_kg must be greater than 0"}), 400

        price_per_kg = 100  # set your rate here
        total_price = weight_kg * price_per_kg

        # Create order
        order = Order(
            customer_id=customer_id,
            created_by=creator_id,
            address_id=address.id,
            pickup_time=pickup_time,
            delivery_time=delivery_time,
            total_price=total_price,
            status=status,
            cancellation_fee=0.00,
        )

        db.session.add(order)
        db.session.commit()

        return jsonify({"message": "Order created successfully", "order": order.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@orders_bp.route("/", methods=["GET"])
@jwt_required()
def get_orders():
    """
    Retrieve a list of orders for the current user.

    - Customers: see only their own orders.
    - Workers: see orders assigned to them OR unassigned (status = CREATED).
    - Admins: not allowed.

    Returns:
      JSON response containing a list of orders.
    """
    try:
        current_user = AuthService.get_current_user()

        if current_user.role == UserRole.CUSTOMER:
            orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()

        elif current_user.role == UserRole.WORKER:
            orders = Order.query.filter(
                (Order.worker_id == current_user.id) |
                (Order.status == OrderStatus.CREATED)
            ).order_by(Order.created_at.desc()).all()

        else:
            return jsonify({"error": "Invalid role"}), 403

        return jsonify({"orders": [o.to_dict() for o in orders]}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@orders_bp.route("/<int:order_id>", methods=["DELETE"])
@jwt_required()
def cancel_order(order_id):
    """
    Cancel an existing order.

    Permissions:
      - Customers can cancel their own orders.
      - Workers can cancel orders assigned to them.
      - Admins cannot cancel from this endpoint.

    Business rules:
      - Applies a cancellation fee (calculated via service).
      - Order status is updated to CANCELLED.

    Returns:
      JSON response with cancellation confirmation and applied fee.
    """
    current_user = AuthService.get_current_user()
    order = Order.query.get_or_404(order_id)

    # Admins cannot cancel from this endpoint
    if current_user.role == UserRole.ADMIN:
        return jsonify({"error": "Admins cannot cancel orders from this endpoint"}), 403

    # Only customer, assigned worker can cancel
    if current_user.role == UserRole.CUSTOMER and order.customer_id != current_user.id:
        return jsonify({"error": "You can only cancel your own orders"}), 403

    if current_user.role == UserRole.WORKER and order.worker_id != current_user.id:
        return jsonify({"error": "You can only cancel orders assigned to you"}), 403

    # Apply cancellation policy
    fee = calculate_cancellation_fee(order, current_user.role.value)
    order.status = OrderStatus.CANCELLED
    order.cancellation_fee = fee

    db.session.commit()

    return jsonify({
        "message": "Order cancelled",
        "order_id": order.id,
        "cancellation_fee": fee
    }), 200


@orders_bp.route("/unclaimed", methods=["GET"])
@jwt_required()
def list_unclaimed_orders():
    """
    List all unclaimed (status = CREATED) orders.

    - Only workers are allowed to access this endpoint.
    - Useful for workers to see which jobs are available to claim.

    Returns:
      JSON response containing list of unclaimed orders.
    """
    current_user = AuthService.get_current_user()

    if current_user.role != UserRole.WORKER:
        return jsonify({"error": "Only workers can access this"}), 403

    orders = Order.query.filter_by(status=OrderStatus.CREATED).order_by(Order.created_at.desc()).all()
    return jsonify({"orders": [order.to_dict() for order in orders]}), 200


@orders_bp.route("/<int:order_id>/claim", methods=["POST"])
@jwt_required()
def claim_order(order_id):
    """
    Claim an available order.

    - Only workers can claim.
    - The order must be in CREATED status.
    - When claimed, the worker is assigned and status → ACCEPTED.

    Returns:
      JSON response with updated order details.
    """
    current_user = AuthService.get_current_user()

    if current_user.role != UserRole.WORKER:
        return jsonify({"error": "Only workers can claim orders"}), 403

    order = Order.query.get_or_404(order_id)

    if order.status != OrderStatus.CREATED:
        return jsonify({"error": "Order is not available for claiming"}), 400

    order.worker_id = current_user.id
    order.status = OrderStatus.ACCEPTED

    db.session.commit()
    return jsonify({"message": "Order claimed successfully", "order": order.to_dict()}), 200


@orders_bp.route("/<int:order_id>/status", methods=["POST"])
@jwt_required()
def update_order_status(order_id):
    """
    Update the status of an order.

    - Only the assigned worker can update the status.
    - Status must follow valid transitions (see VALID_TRANSITIONS mapping).
      Example: ACCEPTED → IN_PROGRESS → COMPLETED.
    - Invalid transitions are rejected.

    Returns:
      JSON response with the new status and order ID.
    """
    current_user = AuthService.get_current_user()

    if current_user.role != UserRole.WORKER:
        return jsonify({"error": "Only workers can update order status"}), 403

    order = Order.query.get_or_404(order_id)

    if order.worker_id != current_user.id:
        return jsonify({"error": "You are not assigned to this order"}), 403
    
    data = request.get_json()
    new_status = data.get("status")

    try:
        # Convert string → Enum
        status = OrderStatus(new_status)
    except ValueError:
        return {"message": f"Invalid status '{new_status}'"}, 400

    # Validate transition
    if status not in VALID_TRANSITIONS[order.status]:
        return {
            "success": False,
            "message": f"Invalid transition: cannot move from {order.status.value} → {new_status}"
        }, 400

    # Apply transition
    order.status = status
    order.updated_at = datetime.now(timezone.utc)

    db.session.commit()

    return {
        "success": True,
        "message": f"Order status updated: {order.status.value}",
        "order_id": order.id,
        "new_status": order.status.value
    }
