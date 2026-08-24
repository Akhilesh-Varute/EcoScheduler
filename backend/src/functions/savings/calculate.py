import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.db_models import DynamoDBTables, ScheduleModel, SavingsModel
from common.ec2_connector import EC2Connector
from common.utils import get_instance_price


def handler(event, context):
    """
    Calculate savings for instances based on their scheduled on/off times
    This function is triggered by EventBridge on a daily basis

    Args:
        event: EventBridge event
        context: Lambda context

    Returns:
        Dict: Result
    """
    try:
        # Get schedule ID from event or calculate for all schedules
        schedule_id = event.get("scheduleId")

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()
        schedule_model = ScheduleModel(tables["schedules"])
        savings_model = SavingsModel(tables["savings"])

        # Get target date (yesterday by default)
        target_date = event.get("date")
        if not target_date:
            yesterday = datetime.utcnow() - timedelta(days=1)
            target_date = yesterday.strftime("%Y-%m-%d")

        # If schedule ID provided, calculate for that schedule only
        if schedule_id:
            schedule = schedule_model.get_schedule(schedule_id)
            if not schedule:
                return {
                    "success": False,
                    "message": f"Schedule not found: {schedule_id}",
                }

            # Calculate savings for this schedule
            result = calculate_schedule_savings(schedule, target_date, savings_model)
            return {
                "success": True,
                "schedule": {
                    "scheduleId": schedule_id,
                    "name": schedule.get("name"),
                    "savings": result,
                },
            }

        # Otherwise calculate for all active schedules
        schedules_response = schedule_model.list_schedules()
        schedules = schedules_response.get("items", [])

        results = []
        for schedule in schedules:
            if schedule.get("enabled", True):
                result = calculate_schedule_savings(
                    schedule, target_date, savings_model
                )

                if result.get("success"):
                    results.append(
                        {
                            "scheduleId": schedule.get("scheduleId"),
                            "name": schedule.get("name"),
                            "savings": result,
                        }
                    )

        return {
            "success": True,
            "date": target_date,
            "schedulesProcessed": len(results),
            "results": results,
        }

    except Exception as e:
        print(f"Error in savings calculation handler: {str(e)}")
        return {"success": False, "message": f"Internal error: {str(e)}"}


def calculate_schedule_savings(
    schedule: Dict[str, Any], date: str, savings_model: SavingsModel
) -> Dict[str, Any]:
    """
    Calculate savings for a specific schedule

    Args:
        schedule: Schedule object
        date: Date in YYYY-MM-DD format
        savings_model: SavingsModel instance

    Returns:
        Dict: Savings calculation result
    """
    try:
        schedule_id = schedule.get("scheduleId")
        account_id = schedule.get("accountId")
        instance_ids = schedule.get("instanceIds", [])

        # Initialize EC2 connector
        ec2 = EC2Connector(account_id)

        total_hours_saved = 0
        total_cost_saved = 0
        instances_processed = []

        # Get instance details
        instance_response = ec2.describe_instances(instance_ids=instance_ids)

        if not instance_response.get("success"):
            return {
                "success": False,
                "message": instance_response.get("message"),
                "error": instance_response.get("error"),
            }

        instances = instance_response.get("instances", [])

        # Calculate savings per instance
        for instance in instances:
            instance_id = instance.get("InstanceId")
            instance_type = instance.get("InstanceType")
            region = ec2.region

            # Determine instance hourly cost
            hourly_cost = 0
            try:
                platform = instance.get("Platform", "Linux")
                hourly_cost = get_instance_price(instance_type, region, platform)
            except Exception as e:
                print(f"Error getting hourly cost for instance {instance_id}: {str(e)}")
                hourly_cost = 0

            # Get savings previously recorded for this instance/date
            existing_savings = 0
            existing_hours = 0

            # Determine hours saved today based on schedule
            # This is a simplified calculation - in reality, you would track actual start/stop times
            # For demo, let's assume 8 hours of savings per weekday (typical workday)
            hours_saved = 0

            # Check if the date is a weekday
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                weekday = date_obj.weekday()

                # Weekday (0-4 = Mon-Fri)
                if weekday < 5:
                    # Typical office hours (8hr/day)
                    hours_saved = 16  # 24 - 8 = 16 hours saved
                else:
                    # Weekend - assume 24 hours saved
                    hours_saved = 24

                # Check if this date is an exception date
                if date in schedule.get("exceptions", []):
                    hours_saved = 0
            except Exception as e:
                print(f"Error calculating hours saved: {str(e)}")
                hours_saved = 0

            # Calculate cost saved
            cost_saved = hourly_cost * hours_saved

            # Record savings
            if hours_saved > 0:
                try:
                    savings_model.record_savings(
                        schedule_id=schedule_id,
                        instance_id=instance_id,
                        instance_type=instance_type,
                        region=region,
                        hours_saved=hours_saved,
                        cost_saved=cost_saved,
                        date=date,
                    )
                except Exception as e:
                    print(f"Error recording savings: {str(e)}")

            # Add to totals
            total_hours_saved += hours_saved
            total_cost_saved += cost_saved

            # Add instance to processed list
            instances_processed.append(
                {
                    "instanceId": instance_id,
                    "instanceType": instance_type,
                    "hoursSaved": hours_saved,
                    "hourlyCost": hourly_cost,
                    "costSaved": cost_saved,
                }
            )

        return {
            "success": True,
            "date": date,
            "totalHoursSaved": total_hours_saved,
            "totalCostSaved": total_cost_saved,
            "instancesProcessed": len(instances_processed),
            "instances": instances_processed,
        }

    except Exception as e:
        print(
            f"Error calculating savings for schedule {schedule.get('scheduleId')}: {str(e)}"
        )
        return {"success": False, "message": f"Error: {str(e)}"}
