import os
import sys
from typing import Dict, Any

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, ScheduleModel, AuditLogModel
from common.utils import create_response


def handler(event, context):
    """
    List audit logs, filtered by scheduleId, accountId, and/or date range

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

        # Check permissions (reuses the existing view_savings permission)
        is_admin = user["role"] == "admin"
        has_view_permission = has_permission(user, "view_savings")

        if not (is_admin or has_view_permission):
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have permission to view audit logs",
                },
            )

        # Parse query parameters
        query_params = event.get("queryStringParameters", {}) or {}
        schedule_id = query_params.get("scheduleId")
        account_id = query_params.get("accountId")
        start_date = query_params.get("startDate")
        end_date = query_params.get("endDate")

        if not schedule_id and not account_id and not (start_date or end_date):
            return create_response(
                400,
                {
                    "success": False,
                    "message": "At least one filter (scheduleId, accountId, or a date range) is required",
                },
            )

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        audit_model = AuditLogModel(tables["auditLogs"])
        schedule_model = ScheduleModel(tables["schedules"])

        # Resolve target account for the ownership check
        target_account = account_id
        if schedule_id:
            schedule = schedule_model.get_schedule(schedule_id)
            if not schedule:
                return create_response(
                    404, {"success": False, "message": "Schedule not found"}
                )
            target_account = schedule["accountId"]

        if target_account and not is_admin:
            if target_account not in user.get("awsAccounts", []):
                return create_response(
                    403,
                    {
                        "success": False,
                        "message": "You do not have access to this AWS account",
                    },
                )

        # Dispatch to the appropriate query
        if schedule_id:
            logs = audit_model.get_logs_by_schedule(schedule_id, start_date, end_date)
        elif account_id:
            logs = audit_model.get_logs_by_account(account_id, start_date, end_date)
        else:
            if not is_admin:
                return create_response(
                    400,
                    {
                        "success": False,
                        "message": "scheduleId or accountId is required for date-only queries",
                    },
                )
            logs = audit_model.get_logs_by_date_range(start_date, end_date)

        return create_response(200, {"success": True, "count": len(logs), "logs": logs})

    except Exception as e:
        print(f"Error in audit logs list handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
