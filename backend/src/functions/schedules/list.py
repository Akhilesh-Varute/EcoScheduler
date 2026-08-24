import json
import os
import sys
from typing import Dict, Any, List

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, ScheduleModel
from common.utils import create_response


def handler(event, context):
    """
    Handle listing schedules

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        # Get user from token
        user = get_current_user(event)
        if not user:
            return create_response(
                401, {"success": False, "message": "Authentication required"}
            )

        # Parse query parameters
        query_params = event.get("queryStringParameters", {}) or {}
        account_id = query_params.get("accountId")
        user_id = query_params.get("userId")
        limit = int(query_params.get("limit", "100"))
        last_key = query_params.get("nextToken")
        if last_key:
            try:
                last_key = json.loads(last_key)
            except:
                last_key = None

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        schedule_model = ScheduleModel(tables["schedules"])

        # Initialize results
        schedules = []

        # Check permissions and filter accordingly
        is_admin = user["role"] == "admin"

        if account_id:
            # Check if user has access to this AWS account
            if account_id not in user["awsAccounts"] and not is_admin:
                return create_response(
                    403,
                    {
                        "success": False,
                        "message": "You do not have access to this AWS account",
                    },
                )

            # List schedules for the specified account
            schedules = schedule_model.get_schedules_by_account(account_id)
        elif user_id:
            # Check if requesting schedules for self or if admin
            if user_id != user["userId"] and not is_admin:
                return create_response(
                    403,
                    {
                        "success": False,
                        "message": "You do not have permission to view schedules for other users",
                    },
                )

            # List schedules for the specified user
            schedules = schedule_model.get_schedules_by_user(user_id)
        else:
            # Default to listing user's own schedules
            if is_admin and has_permission(user, "view_schedule"):
                # Admin can see all schedules
                result = schedule_model.list_schedules(limit, last_key)
                schedules = result["items"]
                last_key = result.get("lastEvaluatedKey")
            else:
                # Regular users see their own schedules
                schedules = schedule_model.get_schedules_by_user(user["userId"])

        # Format for response
        if isinstance(last_key, dict):
            last_key = json.dumps(last_key)

        return create_response(
            200,
            {
                "success": True,
                "schedules": schedules,
                "count": len(schedules),
                "nextToken": last_key,
            },
        )

    except Exception as e:
        print(f"Error in list schedules handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
