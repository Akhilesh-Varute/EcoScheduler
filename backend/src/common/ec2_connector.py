import boto3
import time
from typing import Dict, List, Any, Optional, Tuple
from botocore.exceptions import ClientError
import os

from .utils import assume_role, get_instance_price, parse_aws_arn


class EC2Connector:
    """
    Class for EC2 operations across accounts
    """

    def __init__(self, account_id: str, region: str = None):
        """
        Initialize EC2 connector for a specific AWS account

        Args:
            account_id: AWS account ID
            region: AWS region (defaults to environment variable or 'us-east-1')
        """
        self.account_id = account_id
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.role_name = os.environ.get(
            "CROSS_ACCOUNT_ROLE", "EcoScheduler-CrossAccount-Role"
        )
        self.ec2_client = None
        self.credentials = None
        self.credential_expiry = 0

    def _refresh_credentials_if_needed(self):
        """
        Refresh cross-account credentials if they're expired or about to expire
        """
        current_time = int(time.time())

        # Refresh if no credentials or they expire within 5 minutes
        if self.credentials is None or self.credential_expiry < current_time + 300:

            try:
                self.credentials = assume_role(
                    account_id=self.account_id, role_name=self.role_name
                )

                # Store expiry time
                if isinstance(self.credentials.get("expiration"), int):
                    self.credential_expiry = self.credentials["expiration"]
                else:
                    # Default to 1 hour from now if expiration not provided as timestamp
                    self.credential_expiry = current_time + 3600

                # Create EC2 client with new credentials
                self.ec2_client = boto3.client(
                    "ec2",
                    region_name=self.region,
                    aws_access_key_id=self.credentials["aws_access_key_id"],
                    aws_secret_access_key=self.credentials["aws_secret_access_key"],
                    aws_session_token=self.credentials["aws_session_token"],
                )

            except Exception as e:
                print(
                    f"Error refreshing credentials for account {self.account_id}: {str(e)}"
                )
                raise Exception(
                    f"Failed to assume role in account {self.account_id}: {str(e)}"
                )

    def _credentials_error(self) -> Optional[Dict[str, Any]]:
        """
        Attempt to refresh cross-account credentials, returning a clean
        {"success": False, ...} dict if that fails (e.g. the customer never
        deployed EcoScheduler-CrossAccount-Role in their account) instead of
        letting the exception propagate as an opaque 500 to the caller.

        Returns:
            Optional[Dict]: error response if credentials could not be obtained, else None
        """
        try:
            self._refresh_credentials_if_needed()
            return None
        except Exception as e:
            return {
                "success": False,
                "message": (
                    f"Could not access AWS account {self.account_id}. "
                    f"Make sure the EcoScheduler-CrossAccount-Role has been "
                    f"deployed in that account (see the account setup guide)."
                ),
                "error": str(e),
            }

    def start_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """
        Start EC2 instances

        Args:
            instance_ids: List of EC2 instance IDs

        Returns:
            Dict: Response from start_instances API call
        """
        cred_error = self._credentials_error()
        if cred_error:
            return cred_error

        try:
            response = self.ec2_client.start_instances(InstanceIds=instance_ids)
            return {
                "success": True,
                "message": f"Started {len(instance_ids)} instances",
                "startingInstances": response.get("StartingInstances", []),
            }
        except ClientError as e:
            error_message = e.response["Error"]["Message"]
            return {
                "success": False,
                "message": f"Error starting instances: {error_message}",
                "error": str(e),
            }

    def stop_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """
        Stop EC2 instances

        Args:
            instance_ids: List of EC2 instance IDs

        Returns:
            Dict: Response from stop_instances API call
        """
        cred_error = self._credentials_error()
        if cred_error:
            return cred_error

        try:
            response = self.ec2_client.stop_instances(InstanceIds=instance_ids)
            return {
                "success": True,
                "message": f"Stopped {len(instance_ids)} instances",
                "stoppingInstances": response.get("StoppingInstances", []),
            }
        except ClientError as e:
            error_message = e.response["Error"]["Message"]
            return {
                "success": False,
                "message": f"Error stopping instances: {error_message}",
                "error": str(e),
            }

    def get_instance_status(self, instance_ids: List[str]) -> Dict[str, Any]:
        """
        Get status of EC2 instances

        Args:
            instance_ids: List of EC2 instance IDs

        Returns:
            Dict: Instance statuses
        """
        cred_error = self._credentials_error()
        if cred_error:
            return cred_error

        try:
            response = self.ec2_client.describe_instance_status(
                InstanceIds=instance_ids, IncludeAllInstances=True
            )

            return {"success": True, "statuses": response.get("InstanceStatuses", [])}
        except ClientError as e:
            error_message = e.response["Error"]["Message"]
            return {
                "success": False,
                "message": f"Error getting instance status: {error_message}",
                "error": str(e),
            }

    def describe_instances(
        self, instance_ids: List[str] = None, filters: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Describe EC2 instances

        Args:
            instance_ids: List of EC2 instance IDs (optional)
            filters: Filters for describe_instances API call (optional)

        Returns:
            Dict: Instance details
        """
        cred_error = self._credentials_error()
        if cred_error:
            return cred_error

        try:
            params = {}

            if instance_ids:
                params["InstanceIds"] = instance_ids

            if filters:
                params["Filters"] = filters

            response = self.ec2_client.describe_instances(**params)

            # Flatten the response for easier consumption
            instances = []

            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instances.append(instance)

            return {"success": True, "instances": instances}
        except ClientError as e:
            error_message = e.response["Error"]["Message"]
            return {
                "success": False,
                "message": f"Error describing instances: {error_message}",
                "error": str(e),
            }

    def list_instances(
        self, tag_filters: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        List EC2 instances, optionally filtered by tags

        Args:
            tag_filters: List of tag filters (optional)

        Returns:
            Dict: List of instances
        """
        filters = []

        # Add tag filters if provided
        if tag_filters:
            for tag_filter in tag_filters:
                for key, value in tag_filter.items():
                    filters.append({"Name": f"tag:{key}", "Values": [value]})

        return self.describe_instances(filters=filters or None)

    def get_instance_hourly_cost(self, instance_id: str) -> float:
        """
        Get the hourly cost for an EC2 instance

        Args:
            instance_id: EC2 instance ID

        Returns:
            float: Hourly cost in USD
        """
        self._refresh_credentials_if_needed()

        try:
            # Get instance details
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])

            # Extract instance type and platform
            instance = response["Reservations"][0]["Instances"][0]
            instance_type = instance["InstanceType"]

            # Determine OS
            platform = instance.get("Platform", "Linux")

            # Get the hourly price
            hourly_price = get_instance_price(instance_type, self.region, platform)

            return hourly_price

        except Exception as e:
            print(f"Error getting hourly cost for instance {instance_id}: {str(e)}")
            return 0.0

    def calculate_instance_savings(
        self, instance_id: str, hours_off: float
    ) -> Dict[str, Any]:
        """
        Calculate savings for an instance being off for a specific number of hours

        Args:
            instance_id: EC2 instance ID
            hours_off: Number of hours the instance was off

        Returns:
            Dict: Savings information
        """
        hourly_cost = self.get_instance_hourly_cost(instance_id)
        savings = hourly_cost * hours_off

        return {
            "instanceId": instance_id,
            "hourlyRate": hourly_cost,
            "hoursOff": hours_off,
            "savings": round(savings, 4),
        }

    def get_instance_tags(self, instance_id: str) -> Dict[str, str]:
        """
        Get tags for an EC2 instance

        Args:
            instance_id: EC2 instance ID

        Returns:
            Dict: Dictionary of tags
        """
        self._refresh_credentials_if_needed()

        try:
            response = self.ec2_client.describe_tags(
                Filters=[{"Name": "resource-id", "Values": [instance_id]}]
            )

            tags = {}
            for tag in response.get("Tags", []):
                tags[tag["Key"]] = tag["Value"]

            return tags

        except Exception as e:
            print(f"Error getting tags for instance {instance_id}: {str(e)}")
            return {}

    def validate_instances(
        self, instance_ids: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Validate that instances exist and are in a valid state

        Args:
            instance_ids: List of EC2 instance IDs

        Returns:
            Tuple: (valid_instances, invalid_instances)
        """
        self._refresh_credentials_if_needed()

        valid_instances = []
        invalid_instances = []

        try:
            response = self.ec2_client.describe_instances(InstanceIds=instance_ids)

            # Track which instances were found
            found_instances = set()

            # Check each instance
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance["InstanceId"]
                    found_instances.add(instance_id)

                    # Check instance state
                    state = instance.get("State", {}).get("Name")

                    # Valid states for scheduling: running, stopped, stopping
                    if state in ["running", "stopped", "stopping"]:
                        valid_instances.append(instance_id)
                    else:
                        invalid_instances.append(instance_id)

            # Add any instances that weren't found to invalid list
            for instance_id in instance_ids:
                if instance_id not in found_instances:
                    invalid_instances.append(instance_id)

            return valid_instances, invalid_instances

        except Exception as e:
            print(f"Error validating instances: {str(e)}")
            # If we can't validate, all are invalid
            return [], instance_ids
