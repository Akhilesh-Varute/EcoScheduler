import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, ScheduleModel, SavingsModel
from common.utils import create_response


def handler(event, context):
    """
    Generate savings reports

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

        # Check permissions
        has_view_permission = has_permission(user, "view_savings")
        is_admin = user["role"] == "admin"
        is_finance = user["role"] == "finance"

        if not (is_admin or is_finance or has_view_permission):
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have permission to view savings reports",
                },
            )

        # Parse query parameters
        query_params = event.get("queryStringParameters", {}) or {}
        report_type = query_params.get("type", "summary")

        # Get date range parameters
        start_date = query_params.get("startDate")
        end_date = query_params.get("endDate")

        # Default to last 30 days if not specified
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")

        # Get account or user filter
        account_id = query_params.get("accountId")
        user_id = query_params.get("userId")
        schedule_id = query_params.get("scheduleId")

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        savings_model = SavingsModel(tables["savings"])
        schedule_model = ScheduleModel(tables["schedules"])

        # Admin/finance are trusted to see everything (unchanged). Anyone
        # else (e.g. a developer, who only just got view_savings) must be
        # scoped to resources they actually own - has_view_permission alone
        # says nothing about *whose* schedule/account is being requested.
        is_trusted = is_admin or is_finance

        # Generate appropriate report
        if report_type == "summary":
            # Like generate_daily_report below, get_savings_summary() accepts
            # user_id/account_id but never actually filters by them (a
            # full-table scan filtered only by date) - block for non-trusted
            # callers rather than let it leak everyone's data.
            if not is_trusted:
                return create_response(
                    403,
                    {
                        "success": False,
                        "message": "Summary reports are only available to admin/finance",
                    },
                )
            report = generate_summary_report(
                savings_model, start_date, end_date, account_id, user_id
            )
        elif report_type == "daily":
            # generate_daily_report doesn't actually filter by account/user
            # (it's a pre-existing stub returning global daily totals
            # regardless of the filters passed) - block it for non-trusted
            # callers entirely rather than let it leak everyone's data.
            if not is_trusted:
                return create_response(
                    403,
                    {
                        "success": False,
                        "message": "Daily reports are only available to admin/finance",
                    },
                )
            report = generate_daily_report(
                savings_model, start_date, end_date, account_id, user_id
            )
        elif report_type == "schedule":
            if not schedule_id:
                return create_response(
                    400,
                    {
                        "success": False,
                        "message": "Schedule ID is required for schedule reports",
                    },
                )
            if not is_trusted:
                owned_schedule = schedule_model.get_schedule(schedule_id)
                if not owned_schedule or owned_schedule.get("userId") != user["userId"]:
                    return create_response(
                        403,
                        {
                            "success": False,
                            "message": "You do not have permission to view this schedule's savings",
                        },
                    )
            report = generate_schedule_report(
                savings_model, schedule_model, schedule_id, start_date, end_date
            )
        elif report_type == "account":
            if not account_id:
                return create_response(
                    400,
                    {
                        "success": False,
                        "message": "Account ID is required for account reports",
                    },
                )
            if not is_trusted and account_id not in user.get("awsAccounts", []):
                return create_response(
                    403,
                    {
                        "success": False,
                        "message": "You do not have access to this AWS account",
                    },
                )
            report = generate_account_report(
                savings_model, schedule_model, account_id, start_date, end_date
            )
        else:
            return create_response(
                400,
                {"success": False, "message": f"Invalid report type: {report_type}"},
            )

        return create_response(200, {"success": True, "report": report})

    except Exception as e:
        print(f"Error in savings report handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )


def generate_summary_report(
    savings_model: SavingsModel,
    start_date: str,
    end_date: str,
    account_id: str = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """
    Generate a summary savings report

    Args:
        savings_model: SavingsModel instance
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        account_id: AWS account ID filter (optional)
        user_id: User ID filter (optional)

    Returns:
        Dict: Summary report
    """
    # Get savings summary
    summary = savings_model.get_savings_summary(
        user_id, account_id, start_date, end_date
    )

    # Format for response
    return {
        "type": "summary",
        "startDate": start_date,
        "endDate": end_date,
        "totalHoursSaved": summary.get("totalHoursSaved", 0),
        "totalCostSaved": summary.get("totalCostSaved", 0),
        "instanceCount": summary.get("instanceCount", 0),
        "filters": {"accountId": account_id, "userId": user_id},
    }


def generate_daily_report(
    savings_model: SavingsModel,
    start_date: str,
    end_date: str,
    account_id: str = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """
    Generate a daily savings report

    Args:
        savings_model: SavingsModel instance
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        account_id: AWS account ID filter (optional)
        user_id: User ID filter (optional)

    Returns:
        Dict: Daily report
    """
    # This would require a more complex implementation in a real system
    # For now, we'll generate some sample data

    # Generate date range
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    delta = end - start

    daily_data = []
    total_hours = 0
    total_cost = 0

    for i in range(delta.days + 1):
        day = start + timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")

        # Get savings for this day
        day_savings = savings_model.get_savings_by_date(date_str)

        # Calculate totals
        day_hours = sum(item.get("hoursSaved", 0) for item in day_savings)
        day_cost = sum(item.get("costSaved", 0) for item in day_savings)

        daily_data.append(
            {
                "date": date_str,
                "hoursSaved": day_hours,
                "costSaved": day_cost,
                "instanceCount": len(
                    set(item.get("instanceId") for item in day_savings)
                ),
            }
        )

        total_hours += day_hours
        total_cost += day_cost

    return {
        "type": "daily",
        "startDate": start_date,
        "endDate": end_date,
        "totalHoursSaved": total_hours,
        "totalCostSaved": total_cost,
        "filters": {"accountId": account_id, "userId": user_id},
        "days": daily_data,
    }


def generate_schedule_report(
    savings_model: SavingsModel,
    schedule_model: ScheduleModel,
    schedule_id: str,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """
    Generate a report for a specific schedule

    Args:
        savings_model: SavingsModel instance
        schedule_model: ScheduleModel instance
        schedule_id: Schedule ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Dict: Schedule report
    """
    # Get schedule details
    schedule = schedule_model.get_schedule(schedule_id)

    if not schedule:
        return {"type": "schedule", "error": f"Schedule not found: {schedule_id}"}

    # Get savings for this schedule
    savings = savings_model.get_savings_by_schedule(schedule_id, start_date, end_date)

    # Group by instance
    instances = {}
    total_hours = 0
    total_cost = 0

    for item in savings:
        instance_id = item.get("instanceId")
        hours = item.get("hoursSaved", 0)
        cost = item.get("costSaved", 0)

        if instance_id not in instances:
            instances[instance_id] = {
                "instanceId": instance_id,
                "instanceType": item.get("instanceType"),
                "region": item.get("region"),
                "hoursSaved": 0,
                "costSaved": 0,
            }

        instances[instance_id]["hoursSaved"] += hours
        instances[instance_id]["costSaved"] += cost

        total_hours += hours
        total_cost += cost

    return {
        "type": "schedule",
        "scheduleId": schedule_id,
        "scheduleName": schedule.get("name"),
        "startDate": start_date,
        "endDate": end_date,
        "totalHoursSaved": total_hours,
        "totalCostSaved": total_cost,
        "instanceCount": len(instances),
        "instances": list(instances.values()),
    }


def generate_account_report(
    savings_model: SavingsModel,
    schedule_model: ScheduleModel,
    account_id: str,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """
    Generate a report for a specific AWS account

    Args:
        savings_model: SavingsModel instance
        schedule_model: ScheduleModel instance
        account_id: AWS account ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Dict: Account report
    """
    # Get schedules for this account
    schedules = schedule_model.get_schedules_by_account(account_id)

    schedule_data = []
    total_hours = 0
    total_cost = 0
    total_instances = set()

    for schedule in schedules:
        schedule_id = schedule.get("scheduleId")

        # Get savings for this schedule
        savings = savings_model.get_savings_by_schedule(
            schedule_id, start_date, end_date
        )

        schedule_hours = sum(item.get("hoursSaved", 0) for item in savings)
        schedule_cost = sum(item.get("costSaved", 0) for item in savings)
        schedule_instances = set(item.get("instanceId") for item in savings)

        schedule_data.append(
            {
                "scheduleId": schedule_id,
                "scheduleName": schedule.get("name"),
                "hoursSaved": schedule_hours,
                "costSaved": schedule_cost,
                "instanceCount": len(schedule_instances),
            }
        )

        total_hours += schedule_hours
        total_cost += schedule_cost
        total_instances.update(schedule_instances)

    return {
        "type": "account",
        "accountId": account_id,
        "startDate": start_date,
        "endDate": end_date,
        "totalHoursSaved": total_hours,
        "totalCostSaved": total_cost,
        "totalInstances": len(total_instances),
        "scheduleCount": len(schedules),
        "schedules": schedule_data,
    }
