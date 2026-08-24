import os
import sys
from typing import Dict, Any

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, UserModel
from common.utils import create_response


def handler(event, context):
    """
    Handle retrieving user details

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

        # If no user ID in path, return current user
        if not target_user_id:
            return create_response(200, {"success": True, "user": current_user})

        # Check if the user is requesting their own info
        is_self = target_user_id == current_user.get("userId")
        is_admin = current_user.get("role") == "admin"
        can_manage_users = has_permission(current_user, "manage_users")

        # Only allow users to access their own info or admins to access any user
        if not (is_self or is_admin or can_manage_users):
            return create_response(
                403, {"success": False, "message": "Permission denied"}
            )

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        user_model = UserModel(tables["users"])

        # Get user
        user = user_model.get_user(target_user_id)

        if not user:
            return create_response(404, {"success": False, "message": "User not found"})

        return create_response(200, {"success": True, "user": user})

    except Exception as e:
        print(f"Error in get user handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
