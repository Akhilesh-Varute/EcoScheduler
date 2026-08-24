import json
import os
import sys
from typing import Dict, Any

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user
from common.db_models import DynamoDBTables, UserModel
from common.subscription_models import SubscriptionModel, SubscriptionTier
from common.payment import generate_subscription_checkout_session, create_customer
from common.utils import create_response


def handler(event, context):
    """
    Handle creating a Stripe checkout session for subscription

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
        email = current_user.get("email")

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
        success_url = body.get("successUrl")
        cancel_url = body.get("cancelUrl")

        # Validate tier
        valid_tiers = [
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

        # Free tier doesn't need checkout
        if tier.lower() == SubscriptionTier.FREE:
            return create_response(
                400, {"success": False, "message": "Free tier does not require payment"}
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
        tables = db_tables.get_tables()
        user_model = UserModel(tables["users"])

        # Get user from database to ensure we have the latest info
        user = user_model.get_user(user_id)
        if not user:
            return create_response(404, {"success": False, "message": "User not found"})

        # Check if user has a Stripe customer ID
        stripe_customer_id = user.get("stripeCustomerId")

        # If no Stripe customer ID, create one
        if not stripe_customer_id:
            try:
                # Create Stripe customer
                customer = create_customer(email=email, name=user.get("name"))

                stripe_customer_id = customer.id

                # Update user with Stripe customer ID
                user_model.update_user(
                    user_id, {"stripeCustomerId": stripe_customer_id}
                )
            except Exception as e:
                print(f"Error creating Stripe customer: {str(e)}")
                return create_response(
                    500,
                    {"success": False, "message": "Error creating payment customer"},
                )

        # Generate checkout session
        try:
            session = generate_subscription_checkout_session(
                customer_id=stripe_customer_id,
                tier=tier,
                billing_cycle=billing_cycle,
                success_url=success_url,
                cancel_url=cancel_url,
            )

            # Return checkout session ID and URL
            return create_response(
                200,
                {
                    "success": True,
                    "checkoutSessionId": session.id,
                    "checkoutUrl": session.url,
                },
            )
        except Exception as e:
            print(f"Error generating checkout session: {str(e)}")
            return create_response(
                500, {"success": False, "message": "Error generating checkout session"}
            )

    except Exception as e:
        print(f"Error in create checkout handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
