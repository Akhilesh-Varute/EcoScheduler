import json
import os
import sys
import boto3
from typing import Dict, Any

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import generate_token
from common.db_models import DynamoDBTables, UserModel
from common.utils import create_response, is_valid_email


def handler(event, context):
    """
    Handle user registration

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Validate input
        email = body.get("email", "").strip().lower()
        password = body.get("password", "")
        name = body.get("name", "").strip()
        # This endpoint is public/unauthenticated (self-registration) — the
        # caller can never choose their own role. Always developer; an existing
        # admin can promote via PUT /users/{userId} afterward.
        role = "developer"
        aws_accounts = []

        # Basic validation
        if not email or not password:
            return create_response(
                400, {"success": False, "message": "Email and password are required"}
            )

        if not is_valid_email(email):
            return create_response(
                400, {"success": False, "message": "Invalid email format"}
            )

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        user_model = UserModel(tables["users"])

        # Check if user already exists
        existing_user = user_model.get_user_by_email(email)
        if existing_user:
            return create_response(
                409, {"success": False, "message": "Email already registered"}
            )

        # Create user
        user = user_model.create_user(
            email=email,
            password=password,  # UNSAFE: In production, hash the password
            role=role,
            aws_accounts=aws_accounts,
            name=name,
        )

        # Generate JWT token
        token = generate_token(
            user_id=user["userId"],
            email=user["email"],
            role=user["role"],
            aws_accounts=user.get("awsAccounts", []),
        )

        return create_response(
            201,
            {
                "success": True,
                "message": "User created successfully",
                "token": token,
                "user": user,
            },
        )

    except Exception as e:
        print(f"Error in user creation handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
