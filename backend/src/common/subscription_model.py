import boto3
import uuid
import time
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key, Attr


class SubscriptionTier:
    """Represents a subscription tier"""

    FREE = "free"
    STARTER = "starter"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"

    @staticmethod
    def get_tier_limits(tier: str) -> int:
        """Get instance limit for a tier"""
        limits = {
            SubscriptionTier.FREE: 5,
            SubscriptionTier.STARTER: 25,
            SubscriptionTier.BUSINESS: 100,
            SubscriptionTier.ENTERPRISE: 999999,  # Effectively unlimited
        }
        return limits.get(tier.lower(), 0)

    @staticmethod
    def get_tier_price_monthly(tier: str) -> float:
        """Get monthly price for a tier"""
        prices = {
            SubscriptionTier.FREE: 0.0,
            SubscriptionTier.STARTER: 49.0,
            SubscriptionTier.BUSINESS: 149.0,
            SubscriptionTier.ENTERPRISE: 499.0,
        }
        return prices.get(tier.lower(), 0.0)

    @staticmethod
    def get_tier_price_annual(tier: str) -> float:
        """Get annual price for a tier (20% discount)"""
        monthly = SubscriptionTier.get_tier_price_monthly(tier)
        annual = monthly * 12 * 0.8  # 20% discount
        return annual


class SubscriptionModel:
    """
    Class for Subscription data model operations
    """

    def __init__(self, subscriptions_table):
        """
        Initialize Subscription model

        Args:
            subscriptions_table: DynamoDB subscriptions table reference
        """
        self.table = subscriptions_table

    def create_subscription(
        self,
        user_id: str,
        tier: str = SubscriptionTier.FREE,
        payment_method: str = None,
        billing_cycle: str = "monthly",
        trial_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Create a new subscription

        Args:
            user_id: User ID
            tier: Subscription tier (free, starter, business, enterprise)
            payment_method: Payment method ID (e.g., Stripe payment method ID)
            billing_cycle: Billing cycle (monthly or annual)
            trial_end: Trial end date

        Returns:
            Dict: Created subscription object
        """
        # Generate UUID for subscription
        subscription_id = str(uuid.uuid4())
        timestamp = int(time.time())

        # Calculate tier limits and prices
        max_instances = SubscriptionTier.get_tier_limits(tier)

        if billing_cycle.lower() == "annual":
            price = SubscriptionTier.get_tier_price_annual(tier)
            # Calculate next billing date (1 year from now)
            next_billing_date = datetime.now() + timedelta(days=365)
        else:
            price = SubscriptionTier.get_tier_price_monthly(tier)
            # Calculate next billing date (1 month from now)
            next_billing_date = datetime.now() + timedelta(days=30)

        # Format next billing date as ISO string
        next_billing_date_str = next_billing_date.isoformat()

        # Create subscription item
        item = {
            "subscriptionId": subscription_id,
            "userId": user_id,
            "tier": tier.lower(),
            "maxInstances": max_instances,
            "price": price,
            "billingCycle": billing_cycle.lower(),
            "nextBillingDate": next_billing_date_str,
            "status": "active",
            "paymentMethod": payment_method,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }

        # Add trial end date if provided
        if trial_end:
            item["trialEnd"] = trial_end.isoformat()

        # Save to DynamoDB
        self.table.put_item(Item=item)
        return item

    def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a subscription by ID

        Args:
            subscription_id: Subscription ID

        Returns:
            Optional[Dict]: Subscription object or None if not found
        """
        response = self.table.get_item(Key={"subscriptionId": subscription_id})

        if "Item" not in response:
            return None

        return response["Item"]

    def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get subscription for a user

        Args:
            user_id: User ID

        Returns:
            Optional[Dict]: Subscription object or None if not found
        """
        response = self.table.query(
            IndexName="UserIdIndex", KeyConditionExpression=Key("userId").eq(user_id)
        )

        items = response.get("Items", [])
        if not items:
            return None

        # Return the most recently created subscription
        return sorted(items, key=lambda x: x.get("createdAt", 0), reverse=True)[0]

    def update_subscription(
        self,
        subscription_id: str,
        tier: Optional[str] = None,
        status: Optional[str] = None,
        billing_cycle: Optional[str] = None,
        payment_method: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a subscription

        Args:
            subscription_id: Subscription ID
            tier: New subscription tier
            status: New status (active, canceled, etc.)
            billing_cycle: New billing cycle (monthly, annual)
            payment_method: New payment method ID

        Returns:
            Optional[Dict]: Updated subscription object or None if not found
        """
        # Get existing subscription
        subscription = self.get_subscription(subscription_id)
        if not subscription:
            return None

        # Build update expression
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        if tier:
            update_expression_parts.append("#tier = :tier")
            expression_attribute_values[":tier"] = tier.lower()
            expression_attribute_names["#tier"] = "tier"

            # Update max instances based on tier
            max_instances = SubscriptionTier.get_tier_limits(tier)
            update_expression_parts.append("#maxInstances = :maxInstances")
            expression_attribute_values[":maxInstances"] = max_instances
            expression_attribute_names["#maxInstances"] = "maxInstances"

            # Update price based on tier and billing cycle
            if subscription.get("billingCycle") == "annual":
                price = SubscriptionTier.get_tier_price_annual(tier)
            else:
                price = SubscriptionTier.get_tier_price_monthly(tier)

            update_expression_parts.append("#price = :price")
            expression_attribute_values[":price"] = price
            expression_attribute_names["#price"] = "price"

        if status:
            update_expression_parts.append("#status = :status")
            expression_attribute_values[":status"] = status.lower()
            expression_attribute_names["#status"] = "status"

        if billing_cycle:
            update_expression_parts.append("#billingCycle = :billingCycle")
            expression_attribute_values[":billingCycle"] = billing_cycle.lower()
            expression_attribute_names["#billingCycle"] = "billingCycle"

            # Recalculate price based on new billing cycle
            current_tier = subscription.get("tier")
            if billing_cycle.lower() == "annual":
                price = SubscriptionTier.get_tier_price_annual(current_tier)
                # Update next billing date (1 year from now)
                next_billing_date = datetime.now() + timedelta(days=365)
            else:
                price = SubscriptionTier.get_tier_price_monthly(current_tier)
                # Update next billing date (1 month from now)
                next_billing_date = datetime.now() + timedelta(days=30)

            update_expression_parts.append("#price = :price")
            expression_attribute_values[":price"] = price
            expression_attribute_names["#price"] = "price"

            update_expression_parts.append("#nextBillingDate = :nextBillingDate")
            expression_attribute_values[":nextBillingDate"] = (
                next_billing_date.isoformat()
            )
            expression_attribute_names["#nextBillingDate"] = "nextBillingDate"

        if payment_method:
            update_expression_parts.append("#paymentMethod = :paymentMethod")
            expression_attribute_values[":paymentMethod"] = payment_method
            expression_attribute_names["#paymentMethod"] = "paymentMethod"

        if not update_expression_parts:
            return subscription  # No updates to apply

        # Add updatedAt timestamp
        update_expression_parts.append("#updatedAt = :updatedAt")
        expression_attribute_values[":updatedAt"] = int(time.time())
        expression_attribute_names["#updatedAt"] = "updatedAt"

        # Create update expression
        update_expression = "SET " + ", ".join(update_expression_parts)

        # Update item
        response = self.table.update_item(
            Key={"subscriptionId": subscription_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW",
        )

        return response.get("Attributes", {})

    def can_add_instances(self, user_id: str, count: int = 1) -> bool:
        """
        Check if a user can add more instances based on their subscription tier

        Args:
            user_id: User ID
            count: Number of instances to add

        Returns:
            bool: True if user can add instances, False otherwise
        """
        # Get user's subscription
        subscription = self.get_user_subscription(user_id)

        # If no subscription found, default to free tier
        if not subscription:
            tier_limit = SubscriptionTier.get_tier_limits(SubscriptionTier.FREE)
        else:
            tier_limit = subscription.get("maxInstances", 0)

        # Get current instance count from schedules
        current_count = self._get_user_instance_count(user_id)

        # Check if adding more instances would exceed limit
        return (current_count + count) <= tier_limit

    def _get_user_instance_count(self, user_id: str) -> int:
        """
        Get the current number of instances a user is managing

        Args:
            user_id: User ID

        Returns:
            int: Number of instances
        """
        # This would typically query the schedules table
        # For now, we'll use a placeholder implementation

        # Get DynamoDB tables
        region_name = os.environ.get("AWS_REGION", "us-east-1")
        dynamodb = boto3.resource("dynamodb", region_name=region_name)
        schedules_table = dynamodb.Table(
            os.environ.get("SCHEDULES_TABLE", "EcoScheduler-Schedules")
        )

        # Query schedules for this user
        response = schedules_table.query(
            IndexName="UserIdIndex", KeyConditionExpression=Key("userId").eq(user_id)
        )

        # Count total instances across all schedules
        total_instances = 0
        for schedule in response.get("Items", []):
            # Get unique instance IDs from this schedule
            instance_ids = schedule.get("instanceIds", [])
            total_instances += len(instance_ids)

        return total_instances

    def get_usage_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get usage statistics for a user

        Args:
            user_id: User ID

        Returns:
            Dict: Usage statistics
        """
        # Get user's subscription
        subscription = self.get_user_subscription(user_id)

        # If no subscription found, default to free tier
        if not subscription:
            tier = SubscriptionTier.FREE
            tier_limit = SubscriptionTier.get_tier_limits(tier)
            price = 0.0
        else:
            tier = subscription.get("tier", SubscriptionTier.FREE)
            tier_limit = subscription.get("maxInstances", 0)
            price = subscription.get("price", 0.0)

        # Get current instance count
        current_count = self._get_user_instance_count(user_id)

        # Calculate usage percentage
        if tier_limit > 0:
            usage_percentage = (current_count / tier_limit) * 100
        else:
            usage_percentage = 0

        return {
            "tier": tier,
            "currentInstances": current_count,
            "maxInstances": tier_limit,
            "usagePercentage": usage_percentage,
            "price": price,
            "upgradeOptions": self._get_upgrade_options(tier),
        }

    def _get_upgrade_options(self, current_tier: str) -> List[Dict[str, Any]]:
        """
        Get upgrade options for a tier

        Args:
            current_tier: Current subscription tier

        Returns:
            List[Dict]: List of upgrade options
        """
        all_tiers = [
            SubscriptionTier.FREE,
            SubscriptionTier.STARTER,
            SubscriptionTier.BUSINESS,
            SubscriptionTier.ENTERPRISE,
        ]

        # Filter tiers higher than current tier
        current_index = (
            all_tiers.index(current_tier.lower())
            if current_tier.lower() in all_tiers
            else -1
        )
        upgrade_tiers = (
            all_tiers[current_index + 1 :] if current_index < len(all_tiers) else []
        )

        # Build upgrade options
        options = []
        for tier in upgrade_tiers:
            options.append(
                {
                    "tier": tier,
                    "maxInstances": SubscriptionTier.get_tier_limits(tier),
                    "monthlyPrice": SubscriptionTier.get_tier_price_monthly(tier),
                    "annualPrice": SubscriptionTier.get_tier_price_annual(tier),
                }
            )

        return options
