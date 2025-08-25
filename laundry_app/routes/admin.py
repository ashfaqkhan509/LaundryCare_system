from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from laundry_app.models import Order, OrderStatus, User, UserRole
from laundry_app.services.auth_service import AuthService
from laundry_app import db
from laundry_app.services.order_service import calculate_cancellation_fee


admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.route("/orders", methods=["GET"])
@jwt_required()
def get_orders():
    """
    Get All Orders (Admin Only)
    ---
    Retrieve all orders in the system.

    **Headers:**
    - Authorization: Bearer <access_token> (Admin required)

    **Responses:**
    - 200: List of all orders
    - 403: Invalid role (only admin allowed)
    - 500: Internal server error
    """
    try:
        current_user = AuthService.get_current_user()

        if current_user.role == UserRole.ADMIN:
            orders = Order.query.all()
        else:
            return jsonify({"error": "Invalid role"}), 403

        return jsonify({"orders": [order.to_dict() for order in orders]}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/orders", methods=["POST"])
@jwt_required()
def create_order_admin():
    """
    Create Order (Admin Only)
    ---
    Allows admin to create an order and assign a worker directly.

    **Request JSON:**
    {
        "customer_id": 1,
        "worker_id": 2,
        "pickup_time": "2025-08-22T12:00:00Z",
        "delivery_time": "2025-08-23T12:00:00Z",
        "total_price": 100.00
    }

    **Responses:**
    - 201: Order created successfully
    - 400: Missing or invalid fields
    - 403: Only admins can create orders
    - 404: Customer or worker not found
    - 500: Internal server error
    """
    try:
        current_user = AuthService.get_current_user()

        if current_user.role != UserRole.ADMIN:
            return jsonify({"error": "Only admin can create orders"}), 403

        data = request.get_json()

        required_fields = [
            "customer_id",
            "worker_id",
            "pickup_time",
            "delivery_time",
            "weight_kg"
        ]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        customer = User.query.filter_by(id=data["customer_id"], role=UserRole.CUSTOMER).first()
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        if not customer.addresses:
            return jsonify({"error": "Customer must have at least one address"}), 400

        worker = User.query.filter_by(id=data["worker_id"], role=UserRole.WORKER).first()
        if not worker:
            return jsonify({"error": "Worker not found"}), 404

        try:
            pickup_time = datetime.fromisoformat(data["pickup_time"].replace("Z", "+00:00"))
            delivery_time = datetime.fromisoformat(data["delivery_time"].replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "Invalid datetime format"}), 400

        if pickup_time <= datetime.now(timezone.utc):
            return jsonify({"error": "Pickup time must be in the future"}), 400
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
            customer_id=data.get('customer_id'),
            created_by=current_user.id,
            address_id=customer.addresses[0].id,
            pickup_time=pickup_time,
            delivery_time=delivery_time,
            total_price=total_price,
            status=OrderStatus.CREATED,
            cancellation_fee=0.00,
        )
        db.session.add(order)
        db.session.commit()

        return jsonify({
            "message": "Order created successfully and assigned to worker",
            "order": order.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/<int:order_id>", methods=["DELETE"])
@jwt_required()
def cancel_order(order_id):
    """
    Cancel Order (Admin Only)
    ---
    Admin can cancel any order with a cancellation fee applied.

    **Path Parameter:**
    - order_id (int): ID of the order to cancel

    **Responses:**
    - 200: Order cancelled successfully with fee details
    - 403: Only admins can cancel orders
    - 404: Order not found
    """
    current_user = AuthService.get_current_user()

    if current_user.role != UserRole.ADMIN:
        return jsonify({"error": "Only admins can cancel orders"}), 403

    order = Order.query.get_or_404(order_id)

    fee = calculate_cancellation_fee(order, current_user.role.value)
    order.status = OrderStatus.CANCELLED
    order.cancellation_fee = fee

    db.session.commit()

    return jsonify({
        "message": "Order cancelled by admin",
        "order_id": order.id,
        "cancellation_fee": fee
    }), 200


@admin_bp.route("/workers", methods=["POST"])
@jwt_required()
def add_worker():
    """
    Add Worker (Admin Only)
    ---
    Create a new worker account.

    **Request JSON:**
    {
        "name": "Worker Name",
        "email": "worker@example.com",
        "phone": "1234567890",
        "password": "securepassword"
    }

    **Responses:**
    - 201: Worker created successfully
    - 400: Missing or duplicate fields
    - 403: Only admins can add workers
    - 500: Internal server error
    """
    try:
        current_user = AuthService.get_current_user()

        if current_user.role != UserRole.ADMIN:
            return jsonify({"error": "Only admins can add workers"}), 403

        data = request.get_json()
        required_fields = ["name", "email", "phone", "password"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        if User.query.filter_by(email=data["email"]).first():
            return jsonify({"error": "Email already exists"}), 400
        if User.query.filter_by(phone=data["phone"]).first():
            return jsonify({"error": "Phone already exists"}), 400

        worker = User(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            role=UserRole.WORKER,
        )
        worker.set_password(data["password"])

        db.session.add(worker)
        db.session.commit()

        return jsonify({
            "message": "Worker added successfully",
            "worker": worker.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/workers/<int:worker_id>", methods=["PUT"])
@jwt_required()
def edit_worker(worker_id):
    """
    Edit Worker (Admin Only)
    ---
    Update an existing worker’s details.

    **Path Parameter:**
    - worker_id (int): ID of the worker

    **Request JSON (optional fields):**
    {
        "name": "Updated Name",
        "email": "updated@example.com",
        "phone": "9876543210"
    }

    **Responses:**
    - 200: Worker updated successfully
    - 400: Duplicate email/phone
    - 403: Only admins can edit workers
    - 404: Worker not found
    """
    try:
        current_user = AuthService.get_current_user()

        if current_user.role != UserRole.ADMIN:
            return jsonify({"error": "Only admins can edit workers"}), 403

        worker = User.query.filter_by(id=worker_id, role=UserRole.WORKER).first()
        if not worker:
            return jsonify({"error": "Worker not found"}), 404

        data = request.get_json()

        if "name" in data:
            worker.name = data["name"]
        if "email" in data:
            if User.query.filter(User.email == data["email"], User.id != worker.id).first():
                return jsonify({"error": "Email already exists"}), 400
            worker.email = data["email"]
        if "phone" in data:
            if User.query.filter(User.phone == data["phone"], User.id != worker.id).first():
                return jsonify({"error": "Phone already exists"}), 400
            worker.phone = data["phone"]

        db.session.commit()

        return jsonify({
            "message": "Worker updated successfully",
            "worker": worker.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/<int:worker_id>/assign_customer", methods=["POST"])
@jwt_required()
def assign_customer_to_worker(worker_id):
    """
    Assign Customer to Worker (Admin Only)
    ---
    Assign an existing customer to a specific worker.

    **Path Parameter:**
    - worker_id (int): ID of the worker

    **Request JSON:**
    {
        "customer_id": 5
    }

    **Responses:**
    - 200: Customer assigned successfully
    - 400: Invalid role or missing fields
    - 403: Only admins can assign customers
    - 404: Worker or customer not found
    """
    current_user = AuthService.get_current_user()
    if current_user.role != UserRole.ADMIN:
        return jsonify({"error": "Only admins can assign customers to workers"}), 403

    data = request.get_json()
    customer_id = data.get("customer_id")
    if not customer_id:
        return jsonify({"error": "customer_id is required"}), 400

    worker = User.query.get_or_404(worker_id)
    if worker.role != UserRole.WORKER:
        return jsonify({"error": "Target user is not a worker"}), 400

    customer = User.query.get_or_404(customer_id)
    if customer.role != UserRole.CUSTOMER:
        return jsonify({"error": "Target user is not a customer"}), 400

    customer.worker_id = worker.id
    db.session.commit()

    return jsonify({
        "message": f"Customer {customer.id} assigned to Worker {worker.id}",
        "worker": worker.to_dict(include_customers=True)
    }), 200
