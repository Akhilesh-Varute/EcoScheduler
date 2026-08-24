import json
import os
import sys
from typing import Dict, Any, List

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, ScheduleModel
from common.utils import create_response, validate_cron_expression
from common.ec2_connector import EC2Connector
from common.scheduler import SchedulerManager


def handler(event, context):
    """
    Handle updating a schedule

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

        # Parse request body
        body = json.loads(event.get("body", "{}"))

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
        has_update_permission = has_permission(user, "update_schedule")

        if not (is_owner or is_admin or has_update_permission):
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have permission to update this schedule",
                },
            )

        # Prepare updates
        updates = {}

        # Update name if provided
        if "name" in body:
            updates["name"] = body["name"].strip()

        # Update instance IDs if provided
        if "instanceIds" in body:
            instance_ids = body["instanceIds"]

            # Validate instance IDs
            if not isinstance(instance_ids, list) or not instance_ids:
                return create_response(
                    400,
                    {
                        "success": False,
                        "message": "Instance IDs must be a non-empty list",
                    },
                )

            # Validate instance existence
            try:
                ec2_connector = EC2Connector(schedule["accountId"])
                valid_instances, invalid_instances = ec2_connector.validate_instances(
                    instance_ids
                )

                if invalid_instances:
                    return create_response(
                        400,
                        {
                            "success": False,
                            "message": "Some instance IDs are invalid or in an invalid state",
                            "invalidInstances": invalid_instances,
                        },
                    )

                updates["instanceIds"] = instance_ids
            except Exception as e:
                return create_response(
                    400,
                    {
                        "success": False,
                        "message": f"Error validating instances: {str(e)}",
                    },
                )

        # Update cron expressions if provided
        if "startCron" in body:
            start_cron = body["startCron"].strip()

            # Validate cron expression
            if not validate_cron_expression(start_cron):
                return create_response(
                    400, {"success": False, "message": "Invalid start cron expression"}
                )

            updates["startCron"] = start_cron

        if "stopCron" in body:
            stop_cron = body["stopCron"].strip()

            # Validate cron expression
            if not validate_cron_expression(stop_cron):
                return create_response(
                    400, {"success": False, "message": "Invalid stop cron expression"}
                )

            updates["stopCron"] = stop_cron

        # Update timezone if provided
        if "timezone" in body:
            updates["timezone"] = body["timezone"]

        # Update exceptions if provided
        if "exceptions" in body:
            updates["exceptions"] = body["exceptions"]

        # Update tags if provided
        if "tags" in body:
            updates["tags"] = body["tags"]

        # Update enabled status if provided
        if "enabled" in body:
            updates["enabled"] = bool(body["enabled"])

        # Update dry-run mode if provided
        if "dryRun" in body:
            updates["dryRun"] = bool(body["dryRun"])

        # Apply updates
        if updates:
            schedule = schedule_model.update_schedule(schedule_id, updates)

            # Update EventBridge rules if necessary
            if "startCron" in updates or "stopCron" in updates or "timezone" in updates:
                try:
                    scheduler = SchedulerManager()
                    rules = scheduler.update_schedule_rules(schedule)

                    # Update rule ARNs
                    schedule_model.update_schedule(
                        schedule_id,
                        {
                            "startRuleArn": rules.get("startRule"),
                            "stopRuleArn": rules.get("stopRule"),
                        },
                    )
                except Exception as e:
                    print(f"Error updating EventBridge rules: {str(e)}")

            # Update rule status based on enabled flag
            if "enabled" in updates:
                try:
                    scheduler = SchedulerManager()

                    if updates["enabled"]:
                        scheduler.enable_schedule_rules(schedule_id)
                    else:
                        scheduler.disable_schedule_rules(schedule_id)
                except Exception as e:
                    print(f"Error updating rule status: {str(e)}")

        # Calculate next run times
        next_run_times = None
        try:
            scheduler = SchedulerManager()
            next_run_times = scheduler.get_next_run_times(schedule)
        except Exception as e:
            print(f"Error calculating next run times: {str(e)}")

        return create_response(
            200,
            {
                "success": True,
                "message": "Schedule updated successfully",
                "schedule": schedule,
                "nextRunTimes": next_run_times,
            },
        )

    except Exception as e:
        print(f"Error in update schedule handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
