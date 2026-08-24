import os
import sys
from typing import Dict, Any

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, ScheduleModel
from common.utils import create_response
from common.scheduler import SchedulerManager


def handler(event, context):
    """
    Handle deleting a schedule

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

        # Extract schedule ID from path parameter
        schedule_id = event.get("pathParameters", {}).get("scheduleId")
        if not schedule_id:
            return create_response(
                400, {"success": False, "message": "Schedule ID is required"}
            )

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        schedule_model = ScheduleModel(tables["schedules"])

        # Get existing schedule
        schedule = schedule_model.get_schedule(schedule_id)
        if not schedule:
            return create_response(
                404, {"success": False, "message": "Schedule not found"}
            )

        # Check permissions
        is_owner = schedule["userId"] == user["userId"]
        is_admin = user["role"] == "admin"
        has_delete_permission = has_permission(user, "delete_schedule")

        if not (is_owner or is_admin or has_delete_permission):
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have permission to delete this schedule",
                },
            )

        # Delete EventBridge rules
        try:
            scheduler = SchedulerManager()
            scheduler.delete_schedule_rules(schedule_id)
        except Exception as e:
            print(f"Error deleting EventBridge rules: {str(e)}")
            # Continue with schedule deletion even if rule deletion fails

        # Delete schedule
        success = schedule_model.delete_schedule(schedule_id)

        if not success:
            return create_response(
                500, {"success": False, "message": "Failed to delete schedule"}
            )

        return create_response(
            200,
            {
                "success": True,
                "message": "Schedule deleted successfully",
                "scheduleId": schedule_id,
            },
        )

    except Exception as e:
        print(f"Error in delete schedule handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
