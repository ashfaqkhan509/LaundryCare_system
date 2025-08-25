from flask import Blueprint, request, jsonify
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt
from laundry_app import db
from laundry_app.models import User, UserRole, TokenBlocklist
from laundry_app.services.auth_service import AuthService
from laundry_app.utils.auth_util import generate_tokens


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    User Signup Endpoint

    Create a new user account (Customer/Worker/Admin).

    **Request JSON:**
    {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "1234567890",
        "password": "mypassword",
        "role": "CUSTOMER" | "WORKER" | "ADMIN"
    }

    **Responses:**
    - 201: User created successfully
    - 409: Email already exists
    - 500: Internal server error
    """
    try:
        data = request.get_json()
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'message': 'Email already exists'}), 409
        
        # Create user
        user = User(
            name = data['name'],
            email = data['email'],
            role=UserRole(data['role']),
            phone = data['phone']
            
        )
        user.set_password(data['password'])

        # Add to database
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': 'User signup successfully',
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc() 
        return jsonify({
            'error': 'Something went wrong during signup',
            'details': str(e)
        }), 500


@auth_bp.route('/customer/login', methods=['POST'])
def customer_login():
    """
    Customer Login Endpoint
    ---
    Authenticate a customer using email & password.

    **Request JSON:**
    {
        "email": "customer@example.com",
        "password": "mypassword"
    }

    **Responses:**
    - 200: Returns access & refresh tokens with user info
    - 400: Missing email or password
    - 401: Invalid credentials
    - 500: Internal server error
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('email') or not data.get('password'):
            return jsonify({'message': 'email and password are required'}), 400
        
        # Find user
        user = User.query.filter_by(email=data['email'], role=UserRole.CUSTOMER).first()
        if not user or not user.check_password(data['password']):
            return jsonify({'message': 'Invalid email or password'}), 401
        
        # Generate tokens
        access_token, refresh_token = generate_tokens(user.id, user.role.value)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'An error occurred during login'}), 500


@auth_bp.route('/worker/login', methods=['POST'])
def worker_login():
    """
    Worker Login Endpoint
    ---
    Authenticate a worker using email & password.

    **Request JSON:**
    {
        "email": "worker@example.com",
        "password": "mypassword"
    }

    **Responses:**
    - 200: Returns access & refresh tokens with user info
    - 400: Missing email or password
    - 401: Invalid credentials
    - 500: Internal server error
    """
    try:
        data = request.get_json()
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password required'}), 400
        
        user = User.query.filter_by(email=data['email'], role=UserRole.WORKER).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        access_token, refresh_token = generate_tokens(user.id, user.role.value)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/admin/login', methods=['POST'])
def admin_login():
    """
    Admin Login Endpoint
    ---
    Authenticate an admin using email & password.

    **Request JSON:**
    {
        "email": "admin@example.com",
        "password": "mypassword"
    }

    **Responses:**
    - 200: Returns access & refresh tokens with user info
    - 400: Missing email or password
    - 401: Wrong password
    - 403: User exists but is not admin
    - 404: No user found with this email
    - 500: Internal server error
    """
    try:
        data = request.get_json()
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password required'}), 400
        
        user = User.query.filter_by(email=data['email']).first()

        if not user:
            return jsonify({'error': 'No user found with this email'}), 404

        if user.role != UserRole.ADMIN:
            return jsonify({'error': f'User is not admin, role={user.role}'}), 403

        if not user.check_password(data['password']):
            return jsonify({'error': 'Wrong password'}), 401
        
        access_token, refresh_token = generate_tokens(user.id, user.role.value)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/api/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout Endpoint
    ---
    Invalidate the current JWT token by adding it to the blocklist.

    **Headers:**
    - Authorization: Bearer <access_token>

    **Responses:**
    - 200: Successfully logged out
    - 500: Internal server error
    """
    try:
        jti = get_jwt()['jti']
        db.session.add(TokenBlocklist(jti=jti))
        db.session.commit()
        return jsonify({'message': 'Successfully logged out'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    """
    Get Profile Endpoint
    ---
    Retrieve the profile details of the logged-in user.

    **Headers:**
    - Authorization: Bearer <access_token>

    **Responses:**
    - 200: Returns profile info including addresses and worker (if assigned)
    - 404: User not found
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user.to_dict(include_worker=True)), 200


@auth_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    """
    Update Profile Endpoint
    ---
    Update name or phone of the logged-in user.

    **Headers:**
    - Authorization: Bearer <access_token>

    **Request JSON (optional fields):**
    {
        "name": "New Name",
        "phone": "9876543210"
    }

    **Responses:**
    - 200: Profile updated successfully
    - 404: User not found
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if "name" in data:
        user.name = data["name"]
    if "phone" in data:
        user.phone = data["phone"]

    db.session.commit()
    return jsonify({"message": "Profile updated successfully"}), 200

