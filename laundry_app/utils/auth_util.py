from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta


def generate_tokens(user_id, role):
    """Generate access and refresh tokens for a user"""
    additional_claims = {'role': role}
    access_token = create_access_token(
        identity=str(user_id),
        additional_claims=additional_claims,
        expires_delta=timedelta(days=1)
    )
    refresh_token = create_refresh_token(
        identity=user_id,
        additional_claims=additional_claims,
        expires_delta=timedelta(days=30)
    )
    return access_token, refresh_token


def verify_token():
    """Verify JWT token and return user identity"""
    return get_jwt_identity()


def hash_password(password):
    """Hash a password"""
    return generate_password_hash(password)


def verify_password(password_hash, password):
    """Verify a password against its hash"""
    return check_password_hash(password_hash, password)
