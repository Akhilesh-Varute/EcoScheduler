import json
import os
import sys
from typing import Dict, Any

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, UserModel, hash_password
from common.utils import create_response, is_valid_email


def handler(event, context):
    """
    Handle updating user details

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        # Get current user from token
        current_user = get_current_user(event)
        if not current_user:
            return create_response(
                401, {"success": False, "message": "Authentication required"}
            )

        # Extract user ID from path parameter
        path_parameters = event.get("pathParameters", {}) or {}
        target_user_id = path_parameters.get("userId")

        if not target_user_id:
            return create_response(
                400, {"success": False, "message": "User ID is required"}
            )

        # Check if the user is updating their own info
        is_self = target_user_id == current_user.get("userId")
        is_admin = current_user.get("role") == "admin"
        can_manage_users = has_permission(current_user, "manage_users")

        # Only allow users to update their own info or admins to update any user
        if not (is_self or is_admin or can_manage_users):
            return create_response(
                403, {"success": False, "message": "Permission denied"}
            )

        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        user_model = UserModel(tables["users"])

        # Get existing user
        existing_user = user_model.get_user(target_user_id)
        if not existing_user:
            return create_response(404, {"success": False, "message": "User not found"})

        # Prepare updates
        updates = {}

        # Role can only ever be changed by an admin (never self-service, to
        # prevent privilege escalation via this endpoint)
        if (is_admin or can_manage_users) and "role" in body:
            role = body.get("role", "").strip().lower()
            valid_roles = ["admin", "developer", "finance"]
            if role in valid_roles:
                updates["role"] = role

        # AWS accounts: admins can set this for anyone; any user can connect
        # AWS accounts to their own profile (self-service onboarding)
        if "awsAccounts" in body and (is_admin or can_manage_users or is_self):
            aws_accounts = body.get("awsAccounts", [])
            updates["awsAccounts"] = aws_accounts

        # Other fields any user can update for themselves
        if "name" in body:
            updates["name"] = body.get("name", "").strip()

        if "email" in body:
            email = body.get("email", "").strip().lower()
            if is_valid_email(email):
                # Check if email is already taken by another user
                existing_email_user = user_model.get_user_by_email(email)
                if (
                    existing_email_user
                    and existing_email_user.get("userId") != target_user_id
                ):
                    return create_response(
                        409,
                        {
                            "success": False,
                            "message": "Email already in use by another user",
                        },
                    )
                updates["email"] = email

        # Password update
        if "password" in body:
            password = body.get("password", "")
            if password:  # Ensure not empty
                updates["password"] = hash_password(password)

        # If no updates
        if not updates:
            return create_response(
                200,
                {
                    "success": True,
                    "message": "No changes to apply",
                    "user": existing_user,
                },
            )

        # Apply updates
        updated_user = user_model.update_user(target_user_id, updates)

        return create_response(
            200,
            {
                "success": True,
                "message": "User updated successfully",
                "user": updated_user,
            },
        )

    except Exception as e:
        print(f"Error in update user handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
