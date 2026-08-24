import os
import sys

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, generate_token
from common.db_models import DynamoDBTables, UserModel
from common.utils import create_response


def handler(event, context):
    """
    Reissue a JWT for the currently authenticated user, with fresh role/
    awsAccounts/permissions read from the database. Lets the client pick up
    changes (like just having connected a new AWS account to themselves)
    without forcing a full logout/login cycle.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        current_user = get_current_user(event)
        if not current_user:
            return create_response(
                401, {"success": False, "message": "Authentication required"}
            )

        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        user_model = UserModel(tables["users"])

        fresh_user = user_model.get_user(current_user["userId"])
        if not fresh_user:
            return create_response(
                404, {"success": False, "message": "User not found"}
            )

        token = generate_token(
            user_id=fresh_user["userId"],
            email=fresh_user["email"],
            role=fresh_user["role"],
            aws_accounts=fresh_user.get("awsAccounts", []),
        )

        return create_response(
            200,
            {"success": True, "message": "Token refreshed", "token": token, "user": fresh_user},
        )

    except Exception as e:
        print(f"Error in token refresh handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
