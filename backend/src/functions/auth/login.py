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
    Handle user login

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

        # Authenticate user
        user = user_model.authenticate(email, password)

        if not user:
            return create_response(
                401, {"success": False, "message": "Invalid credentials"}
            )

        # Generate JWT token
        token = generate_token(
            user_id=user["userId"],
            email=user["email"],
            role=user["role"],
            aws_accounts=user.get("awsAccounts", []),
        )

        return create_response(
            200,
            {
                "success": True,
                "message": "Login successful",
                "token": token,
                "user": user,
            },
        )

    except Exception as e:
        print(f"Error in login handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
