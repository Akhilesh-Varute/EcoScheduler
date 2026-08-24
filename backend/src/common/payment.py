import os
import stripe
from typing import Dict, Any, Optional, List

# Set Stripe API key from environment
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# Stripe product and price IDs
STRIPE_PRODUCTS = {
    "starter": {
        "monthly": os.environ.get(
            "STRIPE_STARTER_MONTHLY_PRICE_ID", "price_starter_monthly"
        ),
        "annual": os.environ.get(
            "STRIPE_STARTER_ANNUAL_PRICE_ID", "price_starter_annual"
        ),
    },
    "business": {
        "monthly": os.environ.get(
            "STRIPE_BUSINESS_MONTHLY_PRICE_ID", "price_business_monthly"
        ),
        "annual": os.environ.get(
            "STRIPE_BUSINESS_ANNUAL_PRICE_ID", "price_business_annual"
        ),
    },
    "enterprise": {
        "monthly": os.environ.get(
            "STRIPE_ENTERPRISE_MONTHLY_PRICE_ID", "price_enterprise_monthly"
        ),
        "annual": os.environ.get(
            "STRIPE_ENTERPRISE_ANNUAL_PRICE_ID", "price_enterprise_annual"
        ),
    },
}


def create_customer(email: str, name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a Stripe customer

    Args:
        email: Customer email
        name: Customer name

    Returns:
        Dict: Stripe customer object
    """
    try:
        customer = stripe.Customer.create(email=email, name=name)
        return customer
    except stripe.error.StripeError as e:
        print(f"Error creating Stripe customer: {str(e)}")
        raise


def create_payment_method(card_token: str) -> Dict[str, Any]:
    """
    Create a Stripe payment method

    Args:
        card_token: Stripe card token

    Returns:
        Dict: Stripe payment method object
    """
    try:
        payment_method = stripe.PaymentMethod.create(
            type="card", card={"token": card_token}
        )
        return payment_method
    except stripe.error.StripeError as e:
        print(f"Error creating Stripe payment method: {str(e)}")
        raise


def attach_payment_method(customer_id: str, payment_method_id: str) -> Dict[str, Any]:
    """
    Attach a payment method to a customer

    Args:
        customer_id: Stripe customer ID
        payment_method_id: Stripe payment method ID

    Returns:
        Dict: Stripe payment method object
    """
    try:
        payment_method = stripe.PaymentMethod.attach(
            payment_method_id, customer=customer_id
        )
        return payment_method
    except stripe.error.StripeError as e:
        print(f"Error attaching payment method: {str(e)}")
        raise


def set_default_payment_method(
    customer_id: str, payment_method_id: str
) -> Dict[str, Any]:
    """
    Set a payment method as default for a customer

    Args:
        customer_id: Stripe customer ID
        payment_method_id: Stripe payment method ID

    Returns:
        Dict: Stripe customer object
    """
    try:
        customer = stripe.Customer.modify(
            customer_id, invoice_settings={"default_payment_method": payment_method_id}
        )
        return customer
    except stripe.error.StripeError as e:
        print(f"Error setting default payment method: {str(e)}")
        raise


def create_subscription(
    customer_id: str, tier: str, billing_cycle: str = "monthly"
) -> Dict[str, Any]:
    """
    Create a Stripe subscription

    Args:
        customer_id: Stripe customer ID
        tier: Subscription tier
        billing_cycle: Billing cycle (monthly or annual)

    Returns:
        Dict: Stripe subscription object
    """
    try:
        # Get price ID
        price_id = STRIPE_PRODUCTS.get(tier.lower(), {}).get(billing_cycle.lower())
        if not price_id:
            raise ValueError(f"Invalid tier or billing cycle: {tier}, {billing_cycle}")

        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"],
        )

        return subscription
    except stripe.error.StripeError as e:
        print(f"Error creating Stripe subscription: {str(e)}")
        raise


def update_subscription(
    subscription_id: str, tier: str, billing_cycle: str = "monthly"
) -> Dict[str, Any]:
    """
    Update a Stripe subscription

    Args:
        subscription_id: Stripe subscription ID
        tier: New subscription tier
        billing_cycle: New billing cycle (monthly or annual)

    Returns:
        Dict: Stripe subscription object
    """
    try:
        # Get price ID
        price_id = STRIPE_PRODUCTS.get(tier.lower(), {}).get(billing_cycle.lower())
        if not price_id:
            raise ValueError(f"Invalid tier or billing cycle: {tier}, {billing_cycle}")

        # Get subscription to find item ID
        subscription = stripe.Subscription.retrieve(subscription_id)
        item_id = subscription["items"]["data"][0]["id"]

        # Update subscription
        updated_subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{"id": item_id, "price": price_id}],
            proration_behavior="create_prorations",
        )

        return updated_subscription
    except stripe.error.StripeError as e:
        print(f"Error updating Stripe subscription: {str(e)}")
        raise


def cancel_subscription(subscription_id: str) -> Dict[str, Any]:
    """
    Cancel a Stripe subscription

    Args:
        subscription_id: Stripe subscription ID

    Returns:
        Dict: Stripe subscription object
    """
    try:
        subscription = stripe.Subscription.delete(subscription_id)
        return subscription
    except stripe.error.StripeError as e:
        print(f"Error canceling Stripe subscription: {str(e)}")
        raise


def get_payment_intent_client_secret(payment_intent_id: str) -> str:
    """
    Get client secret for a payment intent

    Args:
        payment_intent_id: Stripe payment intent ID

    Returns:
        str: Client secret
    """
    try:
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return payment_intent.client_secret
    except stripe.error.StripeError as e:
        print(f"Error getting payment intent: {str(e)}")
        raise


def generate_subscription_checkout_session(
    customer_id: str,
    tier: str,
    billing_cycle: str = "monthly",
    success_url: str = None,
    cancel_url: str = None,
) -> Dict[str, Any]:
    """
    Generate a Stripe checkout session for subscription

    Args:
        customer_id: Stripe customer ID
        tier: Subscription tier
        billing_cycle: Billing cycle (monthly or annual)
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect if payment is canceled

    Returns:
        Dict: Stripe checkout session
    """
    try:
        # Get price ID
        price_id = STRIPE_PRODUCTS.get(tier.lower(), {}).get(billing_cycle.lower())
        if not price_id:
            raise ValueError(f"Invalid tier or billing cycle: {tier}, {billing_cycle}")

        # Default URLs
        if not success_url:
            success_url = os.environ.get(
                "STRIPE_SUCCESS_URL", "https://example.com/success"
            )

        if not cancel_url:
            cancel_url = os.environ.get(
                "STRIPE_CANCEL_URL", "https://example.com/cancel"
            )

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
        )

        return session
    except stripe.error.StripeError as e:
        print(f"Error creating checkout session: {str(e)}")
        raise
