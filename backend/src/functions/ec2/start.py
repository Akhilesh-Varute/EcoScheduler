import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, ScheduleModel, AuditLogModel
from common.utils import create_response
from common.ec2_connector import EC2Connector
from common.scheduler import SchedulerManager


def handler(event, context):
    """
    Handle starting EC2 instances - can be triggered by:
    1. API Gateway - direct user request
    2. EventBridge - scheduled event

    Args:
        event: API Gateway event or EventBridge event
        context: Lambda context

    Returns:
        Dict: API Gateway response or EventBridge result
    """
    # Determine if this is an API call or EventBridge event
    if "httpMethod" in event:
        # API Gateway request
        return handle_api_request(event, context)
    else:
        # EventBridge event
        return handle_schedule_event(event, context)


def handle_api_request(event, context):
    """
    Handle API request to start instances

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

        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Extract and validate input
        account_id = body.get("accountId")
        instance_ids = body.get("instanceIds", [])
        dry_run = bool(body.get("dryRun", False))

        if not account_id:
            return create_response(
                400, {"success": False, "message": "AWS account ID is required"}
            )

        if not instance_ids:
            return create_response(
                400, {"success": False, "message": "Instance IDs are required"}
            )

        # Check permissions
        has_start_permission = has_permission(user, "start_instances")
        is_admin = user["role"] == "admin"
        has_account_access = account_id in user.get("awsAccounts", [])

        if not (is_admin or (has_start_permission and has_account_access)):
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have permission to start instances in this account",
                },
            )

        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        audit_model = AuditLogModel(tables["auditLogs"])
        triggered_by = user.get("email") or user.get("userId")

        if dry_run:
            print(f"[DRY RUN] Would start instances {instance_ids} in account {account_id}")
            audit_model.record_action(
                action="start",
                trigger_type="manual",
                triggered_by=triggered_by,
                instance_ids=instance_ids,
                account_id=account_id,
                dry_run=True,
                result="dry-run",
            )
            return create_response(
                200,
                {
                    "success": True,
                    "dryRun": True,
                    "message": f"[Dry run] Would have started {len(instance_ids)} instance(s)",
                    "instances": instance_ids,
                },
            )

        # Initialize EC2 connector and start instances
        ec2 = EC2Connector(account_id)
        result = ec2.start_instances(instance_ids)

        if result.get("success"):
            audit_model.record_action(
                action="start",
                trigger_type="manual",
                triggered_by=triggered_by,
                instance_ids=instance_ids,
                account_id=account_id,
                result="success",
            )
            return create_response(
                200,
                {
                    "success": True,
                    "message": result.get("message"),
                    "instances": result.get("startingInstances", []),
                },
            )
        else:
            audit_model.record_action(
                action="start",
                trigger_type="manual",
                triggered_by=triggered_by,
                instance_ids=instance_ids,
                account_id=account_id,
                result="failure",
                error=result.get("message"),
            )
            return create_response(
                400,
                {
                    "success": False,
                    "message": result.get("message"),
                    "error": result.get("error"),
                },
            )

    except Exception as e:
        print(f"Error in EC2 start API handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )


def handle_schedule_event(event, context):
    """
    Handle EventBridge scheduled event to start instances

    Args:
        event: EventBridge event
        context: Lambda context

    Returns:
        Dict: Result
    """
    try:
        # Extract schedule information from event
        schedule_id = event.get("scheduleId")
        account_id = event.get("accountId")
        instance_ids = event.get("instanceIds", [])

        if not all([schedule_id, account_id, instance_ids]):
            print(f"Missing required event data: {event}")
            return {"success": False, "message": "Missing required event data"}

        # Get schedule
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        schedule_model = ScheduleModel(tables["schedules"])
        audit_model = AuditLogModel(tables["auditLogs"])

        schedule = schedule_model.get_schedule(schedule_id)

        if not schedule:
            print(f"Schedule not found: {schedule_id}")
            return {"success": False, "message": "Schedule not found"}

        # Check if schedule is enabled
        if not schedule.get("enabled", True):
            print(f"Schedule {schedule_id} is disabled - skipping")
            return {
                "success": True,
                "message": "Schedule is disabled - no action taken",
                "scheduleId": schedule_id,
            }

        # Check if today is an exception date
        scheduler = SchedulerManager()
        if scheduler.is_exception_date(schedule):
            print(f"Today is an exception date for schedule {schedule_id} - skipping")
            return {
                "success": True,
                "message": "Today is an exception date - no action taken",
                "scheduleId": schedule_id,
            }

        # Check dry-run mode
        if schedule.get("dryRun", False):
            print(f"[DRY RUN] Schedule {schedule_id}: would start instances {instance_ids}")
            audit_model.record_action(
                action="start",
                trigger_type="scheduled",
                triggered_by="system",
                instance_ids=instance_ids,
                account_id=account_id,
                schedule_id=schedule_id,
                dry_run=True,
                result="dry-run",
            )
            schedule_model.update_schedule(
                schedule_id,
                {
                    "lastAction": "start",
                    "lastActionResult": "dry-run",
                },
            )
            return {
                "success": True,
                "message": "Dry run - no action taken",
                "scheduleId": schedule_id,
                "dryRun": True,
                "instances": instance_ids,
            }

        # Start the instances
        ec2 = EC2Connector(account_id)
        result = ec2.start_instances(instance_ids)

        # Record start time for future savings calculation
        current_time = datetime.utcnow().isoformat()

        if result.get("success"):
            audit_model.record_action(
                action="start",
                trigger_type="scheduled",
                triggered_by="system",
                instance_ids=instance_ids,
                account_id=account_id,
                schedule_id=schedule_id,
                result="success",
            )
            # Update schedule with latest start time
            schedule_model.update_schedule(
                schedule_id,
                {
                    "lastStartTime": current_time,
                    "lastAction": "start",
                    "lastActionResult": "success",
                },
            )

            return {
                "success": True,
                "message": result.get("message"),
                "scheduleId": schedule_id,
                "startTime": current_time,
                "instances": result.get("startingInstances", []),
            }
        else:
            # Update schedule with failure information
            schedule_model.update_schedule(
                schedule_id,
                {
                    "lastAction": "start",
                    "lastActionResult": "failure",
                    "lastError": result.get("message"),
                },
            )

            audit_model.record_action(
                action="start",
                trigger_type="scheduled",
                triggered_by="system",
                instance_ids=instance_ids,
                account_id=account_id,
                schedule_id=schedule_id,
                result="failure",
                error=result.get("message"),
            )

            return {
                "success": False,
                "message": result.get("message"),
                "scheduleId": schedule_id,
                "error": result.get("error"),
            }

    except Exception as e:
        print(f"Error in EC2 start schedule handler: {str(e)}")
        return {"success": False, "message": f"Internal error: {str(e)}"}
