import json
import os
import sys
from typing import Dict, Any, List

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.db_models import DynamoDBTables, ScheduleModel
from common.subscription_models import SubscriptionModel, SubscriptionTier
from common.utils import (
    create_response,
    validate_cron_expression,
    is_valid_aws_account_id,
)
from common.ec2_connector import EC2Connector
from common.scheduler import SchedulerManager


def handler(event, context):
    """
    Handle schedule creation with subscription limit checks

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
        if not has_permission(user, "create_schedule"):
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have permission to create schedules",
                },
            )

        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Validate required fields
        required_fields = ["name", "accountId", "instanceIds", "startCron", "stopCron"]
        for field in required_fields:
            if field not in body or not body[field]:
                return create_response(
                    400,
                    {"success": False, "message": f"Missing required field: {field}"},
                )

        # Extract and validate fields
        name = body["name"].strip()
        account_id = body["accountId"].strip()
        instance_ids = body["instanceIds"]
        start_cron = body["startCron"].strip()
        stop_cron = body["stopCron"].strip()
        timezone = body.get("timezone", "UTC")
        exceptions = body.get("exceptions", [])
        tags = body.get("tags", {})

        # Further validation
        if not is_valid_aws_account_id(account_id):
            return create_response(
                400, {"success": False, "message": "Invalid AWS account ID format"}
            )

        # Check if user has access to this AWS account
        if account_id not in user["awsAccounts"] and user["role"] != "admin":
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have access to this AWS account",
                },
            )

        # Validate cron expressions
        if not validate_cron_expression(start_cron):
            return create_response(
                400, {"success": False, "message": "Invalid start cron expression"}
            )

        if not validate_cron_expression(stop_cron):
            return create_response(
                400, {"success": False, "message": "Invalid stop cron expression"}
            )

        # Validate instance IDs
        if not isinstance(instance_ids, list) or not instance_ids:
            return create_response(
                400,
                {"success": False, "message": "Instance IDs must be a non-empty list"},
            )

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()

        # Check subscription limits
        # Add subscriptions table to environment variable if not present
        os.environ["SUBSCRIPTIONS_TABLE"] = os.environ.get(
            "SUBSCRIPTIONS_TABLE", "EcoScheduler-Subscriptions"
        )

        # Get subscriptions table
        subscriptions_table = db_tables.dynamodb.Table(
            os.environ.get("SUBSCRIPTIONS_TABLE")
        )
        subscription_model = SubscriptionModel(subscriptions_table)

        # Check if user can add these instances
        instance_count = len(instance_ids)
        user_id = user["userId"]

        if not subscription_model.can_add_instances(user_id, instance_count):
            # Get user's subscription
            subscription = subscription_model.get_user_subscription(user_id)
            tier_name = (
                subscription.get("tier", SubscriptionTier.FREE)
                if subscription
                else SubscriptionTier.FREE
            )
            tier_limit = subscription.get("maxInstances", 5) if subscription else 5

            # Get usage stats for the error message
            usage = subscription_model.get_usage_stats(user_id)
            current_instances = usage.get("currentInstances", 0)

            # Provide upgrade information
            upgrade_options = []
            for tier in [
                SubscriptionTier.STARTER,
                SubscriptionTier.BUSINESS,
                SubscriptionTier.ENTERPRISE,
            ]:
                tier_max = SubscriptionTier.get_tier_limits(tier)
                if tier_max >= (current_instances + instance_count):
                    upgrade_options.append(
                        {
                            "tier": tier,
                            "maxInstances": tier_max,
                            "monthlyPrice": SubscriptionTier.get_tier_price_monthly(
                                tier
                            ),
                            "annualPrice": SubscriptionTier.get_tier_price_annual(tier),
                        }
                    )

            return create_response(
                402,
                {  # 402 Payment Required
                    "success": False,
                    "message": f"Subscription limit reached. Your {tier_name.capitalize()} tier allows {tier_limit} instances, and you are using {current_instances}.",
                    "currentTier": tier_name,
                    "currentLimit": tier_limit,
                    "currentUsage": current_instances,
                    "attemptedToAdd": instance_count,
                    "upgradeOptions": upgrade_options,
                },
            )

        # Validate instance existence
        try:
            ec2_connector = EC2Connector(account_id)
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
        except Exception as e:
            return create_response(
                400,
                {"success": False, "message": f"Error validating instances: {str(e)}"},
            )

        # Initialize schedule model
        schedule_model = ScheduleModel(tables["schedules"])

        # Create schedule
        schedule = schedule_model.create_schedule(
            user_id=user["userId"],
            name=name,
            account_id=account_id,
            instance_ids=instance_ids,
            start_cron=start_cron,
            stop_cron=stop_cron,
            timezone=timezone,
            exceptions=exceptions,
            tags=tags,
        )

        # Create EventBridge rules
        try:
            scheduler = SchedulerManager()
            rules = scheduler.create_schedule_rules(schedule)

            # Add rule ARNs to schedule
            schedule_model.update_schedule(
                schedule["scheduleId"],
                {
                    "startRuleArn": rules.get("startRule"),
                    "stopRuleArn": rules.get("stopRule"),
                },
            )
        except Exception as e:
            print(f"Error creating EventBridge rules: {str(e)}")
            # Continue without rules, they can be created later

        # Calculate next run times
        next_run_times = None
        try:
            scheduler = SchedulerManager()
            next_run_times = scheduler.get_next_run_times(schedule)
        except Exception as e:
            print(f"Error calculating next run times: {str(e)}")

        # Get updated subscription usage
        usage_stats = subscription_model.get_usage_stats(user_id)

        return create_response(
            201,
            {
                "success": True,
                "message": "Schedule created successfully",
                "schedule": schedule,
                "nextRunTimes": next_run_times,
                "usage": usage_stats,
            },
        )

    except Exception as e:
        print(f"Error in schedule creation handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
