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
    Handle updating subscription (upgrading/downgrading)

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

        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Required fields
        tier = body.get("tier")
        if not tier:
            return create_response(
                400, {"success": False, "message": "Subscription tier is required"}
            )

        # Optional fields
        billing_cycle = body.get("billingCycle", "monthly")
        payment_method = body.get("paymentMethod")

        # Validate tier
        valid_tiers = [
            SubscriptionTier.FREE,
            SubscriptionTier.STARTER,
            SubscriptionTier.BUSINESS,
            SubscriptionTier.ENTERPRISE,
        ]

        if tier.lower() not in valid_tiers:
            return create_response(
                400,
                {
                    "success": False,
                    "message": f"Invalid tier. Must be one of: {', '.join(valid_tiers)}",
                },
            )

        # Validate billing cycle
        if billing_cycle.lower() not in ["monthly", "annual"]:
            return create_response(
                400,
                {
                    "success": False,
                    "message": "Invalid billing cycle. Must be 'monthly' or 'annual'",
                },
            )

        # Initialize database
        db_tables = DynamoDBTables()

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
        current_subscription = subscription_model.get_user_subscription(user_id)

        # For free tier upgrades, we need payment method for paid tiers
        is_upgrade_from_free = (
            not current_subscription
            or current_subscription.get("tier") == SubscriptionTier.FREE
        ) and tier.lower() != SubscriptionTier.FREE

        if (
            is_upgrade_from_free
            and tier.lower() != SubscriptionTier.FREE
            and not payment_method
        ):
            return create_response(
                400,
                {
                    "success": False,
                    "message": "Payment method is required for upgrading from free tier",
                },
            )

        # Check if we need to create or update subscription
        if not current_subscription:
            # Create new subscription
            subscription = subscription_model.create_subscription(
                user_id=user_id,
                tier=tier,
                payment_method=payment_method,
                billing_cycle=billing_cycle,
            )
        else:
            # Update existing subscription
            subscription = subscription_model.update_subscription(
                subscription_id=current_subscription.get("subscriptionId"),
                tier=tier,
                billing_cycle=billing_cycle,
                payment_method=payment_method,
            )

        # Get updated usage statistics
        usage_stats = subscription_model.get_usage_stats(user_id)

        return create_response(
            200,
            {
                "success": True,
                "message": "Subscription updated successfully",
                "subscription": subscription,
                "usage": usage_stats,
            },
        )

    except Exception as e:
        print(f"Error in update subscription handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
