from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from laundry_app import db
from laundry_app.models import User, Address
from laundry_app.services.auth_service import AuthService


customer_bp = Blueprint("customer", __name__, url_prefix="/customer")


@customer_bp.route('/address', methods=['POST'])
@jwt_required()
def add_address():
    """
    Add a new address for the currently authenticated customer.

    This endpoint allows the logged-in customer to add an address. 
    It requires the fields: street, area, postal_code, and city. 
    Only addresses within Lahore are allowed.

    Returns:
        JSON response:
            - 201: Address added successfully with address details.
            - 400: Missing required fields or invalid city.
            - 500: Internal server error.
    """
    try:
        current_user = AuthService.get_current_user()
        data = request.get_json()

        # Required fields
        required_fields = ["street", "area", "postal_code", "city"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        # City validation
        city = data["city"].strip()
        if city.lower() != "lahore":
            return jsonify({"error": "Address must belong to Lahore"}), 400

        # Create address
        address = Address(
            user_id=current_user.id,
            street=data["street"].strip(),
            area=data["area"].strip(),
            city=city.title(),
            postal_code=data["postal_code"].strip()
        )

        db.session.add(address)
        db.session.commit()

        return jsonify({
            "message": "Address added successfully",
            "address": address.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

