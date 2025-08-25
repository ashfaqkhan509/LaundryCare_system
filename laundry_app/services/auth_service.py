"""
Shared service for authentication and authorization
"""
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from laundry_app.models import User

class AuthService:
    @staticmethod
    def get_current_user():
        """
        Get the current authenticated user
        """
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        return user
