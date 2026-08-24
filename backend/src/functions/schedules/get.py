import json
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
    Handle retrieving a schedule

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

        # Get schedule
        schedule = schedule_model.get_schedule(schedule_id)
        if not schedule:
            return create_response(
                404, {"success": False, "message": "Schedule not found"}
            )

        # Check permissions
        is_owner = schedule["userId"] == user["userId"]
        has_access = schedule["accountId"] in user["awsAccounts"]
        is_admin = user["role"] == "admin"

        if not (
            is_owner or has_access or is_admin or has_permission(user, "view_schedule")
        ):
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have permission to view this schedule",
                },
            )

        # Calculate next run times
        next_run_times = None
        try:
            scheduler = SchedulerManager()
            next_run_times = scheduler.get_next_run_times(schedule)
        except Exception as e:
            print(f"Error calculating next run times: {str(e)}")

        return create_response(
            200, {"success": True, "schedule": schedule, "nextRunTimes": next_run_times}
        )

    except Exception as e:
        print(f"Error in get schedule handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
