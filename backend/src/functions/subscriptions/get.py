import json
import os
import sys
from typing import Dict, Any

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user
from common.db_models import DynamoDBTables
from common.subscription_models import SubscriptionModel, SubscriptionTier
from common.utils import create_response


def handler(event, context):
    """
    Handle getting subscription details for the current user

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        # Get current user from token
        current_user = get_current_user(event)
        if not current_user:
            return create_response(
                401, {"success": False, "message": "Authentication required"}
            )

        user_id = current_user.get("userId")

        # Initialize database
        db_tables = DynamoDBTables()
        tables = db_tables.get_tables()

        # Add subscriptions table to environment variable if not present
        os.environ["SUBSCRIPTIONS_TABLE"] = os.environ.get(
            "SUBSCRIPTIONS_TABLE", "EcoScheduler-Subscriptions"
        )

        # Get subscriptions table
        subscriptions_table = db_tables.dynamodb.Table(
            os.environ.get("SUBSCRIPTIONS_TABLE")
        )
        subscription_model = SubscriptionModel(subscriptions_table)

        # Get user's subscription
        subscription = subscription_model.get_user_subscription(user_id)

        # If no subscription found, return free tier info
        if not subscription:
            subscription = {
                "tier": SubscriptionTier.FREE,
                "maxInstances": SubscriptionTier.get_tier_limits(SubscriptionTier.FREE),
                "price": 0,
                "billingCycle": "monthly",
                "status": "active",
            }

        # Get usage statistics
        usage_stats = subscription_model.get_usage_stats(user_id)

        return create_response(
            200, {"success": True, "subscription": subscription, "usage": usage_stats}
        )

    except Exception as e:
        print(f"Error in get subscription handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
