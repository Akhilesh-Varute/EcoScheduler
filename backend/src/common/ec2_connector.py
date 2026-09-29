import boto3
import time
from typing import Dict, List, Any, Optional, Tuple
from botocore.exceptions import ClientError
import os

from .utils import assume_role, get_instance_price, parse_aws_arn

# Error codes where retrying will not help: the customer needs to fix
# something on their end (role deleted/trust policy wrong, instance really
# doesn't exist, etc). No amount of backoff changes the outcome.
PERMANENT_ERROR_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "InvalidClientTokenId",
    "AuthFailure",
    "InvalidInstanceID.NotFound",
}

# Error codes worth a short retry: transient AWS-side conditions that
# often clear up within a few seconds.
TRANSIENT_ERROR_CODES = {
    "Throttling",
    "ThrottlingException",
    "RequestLimitExceeded",
    "InternalError",
    "InternalFailure",
    "ServiceUnavailable",
    "RequestTimeout",
}

MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1


def classify_error(error_code: str) -> str:
    """
    Sort an AWS error code into "permanent" (retrying will not help - the
    customer needs to fix something), "transient" (worth a short retry),
    or "unknown" (an error code we have not seen before - treated the same
    as permanent, i.e. fail fast rather than guess it is safe to retry).
    """
    if error_code in PERMANENT_ERROR_CODES:
        return "permanent"
    if error_code in TRANSIENT_ERROR_CODES:
        return "transient"
    return "unknown"


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

    def _credentials_error(self) -> Optional[Dict[str, Any]]:
        """
        Attempt to refresh cross-account credentials, retrying a bounded
        number of times if STS itself reports a transient error (e.g. it is
        throttling us), and returning a clean {"success": False, ...} dict if
        that still fails - e.g. the customer never deployed
        EcoScheduler-CrossAccount-Role, or deleted/narrowed it - instead of
        letting the exception propagate as an opaque 500 to the caller.

        Returns:
            Optional[Dict]: error response if credentials could not be obtained, else None
        """
        last_error: Optional[Exception] = None
        last_category = "unknown"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                self._refresh_credentials_if_needed()
                return None
            except ClientError as e:
                last_error = e
                error_code = e.response.get("Error", {}).get("Code", "")
                last_category = classify_error(error_code)
            except Exception as e:
                last_error = e
                last_category = "unknown"

            if last_category != "transient" or attempt == MAX_ATTEMPTS:
                break

            print(
                f"Transient error assuming role in account {self.account_id} "
                f"(attempt {attempt}/{MAX_ATTEMPTS}), retrying: {str(last_error)}"
            )
            time.sleep(RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))

        print(
            f"Error refreshing credentials for account {self.account_id} "
            f"[{last_category}]: {str(last_error)}"
        )
        return {
            "success": False,
            "message": (
                f"Could not access AWS account {self.account_id}. "
                f"Make sure the EcoScheduler-CrossAccount-Role has been "
                f"deployed in that account (see the account setup guide)."
            ),
            "error": str(last_error),
            "errorCategory": last_category,
        }

    def _call_ec2_with_retry(self, operation_name: str, api_call, success_fields: Dict[str, str]) -> Dict[str, Any]:
        """
        Call an EC2 API operation, retrying a bounded number of times on
        transient AWS errors (throttling, internal errors) with a short
        exponential backoff, and failing fast (no retry) on permanent errors
        like AccessDenied or an instance ID that genuinely doesn't exist -
        retrying those just burns Lambda time for the same result.

        Args:
            operation_name: human-readable name for log/error messages (e.g. "starting instances")
            api_call: zero-arg callable that makes the boto3 EC2 API call and returns its response
            success_fields: extra {resultKey: responseKey} pairs to copy from the API response into the success dict

        Returns:
            Dict: {"success": True, ...success_fields} or
                  {"success": False, "message", "error", "errorCategory", "attempts"}
        """
        last_error: Optional[ClientError] = None
        last_category = "unknown"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = api_call()
                result: Dict[str, Any] = {"success": True}
                for result_key, response_key in success_fields.items():
                    result[result_key] = response.get(response_key, [])
                return result
            except ClientError as e:
                last_error = e
                error_code = e.response.get("Error", {}).get("Code", "")
                last_category = classify_error(error_code)

                if last_category != "transient" or attempt == MAX_ATTEMPTS:
                    error_message = e.response.get("Error", {}).get("Message", str(e))
                    return {
                        "success": False,
                        "message": f"Error {operation_name}: {error_message}",
                        "error": str(e),
                        "errorCategory": last_category,
                        "attempts": attempt,
                    }

                print(
                    f"Transient error {operation_name} for account {self.account_id} "
                    f"(attempt {attempt}/{MAX_ATTEMPTS}), retrying: {error_code}"
                )
                time.sleep(RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))

        # Unreachable in practice (the loop always returns or raises above),
        # but keeps this method's return type honest if MAX_ATTEMPTS is 0.
        return {
            "success": False,
            "message": f"Error {operation_name}: {str(last_error)}",
            "error": str(last_error),
            "errorCategory": last_category,
            "attempts": MAX_ATTEMPTS,
        }

    def start_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """
        Start EC2 instances, retrying transient AWS errors with backoff.

        Args:
            instance_ids: List of EC2 instance IDs

        Returns:
            Dict: {"success": True, "message", "startingInstances"} or a
                  failure dict with "errorCategory" ("permanent" | "transient" | "unknown")
        """
        cred_error = self._credentials_error()
        if cred_error:
            return cred_error

        result = self._call_ec2_with_retry(
            "starting instances",
            lambda: self.ec2_client.start_instances(InstanceIds=instance_ids),
            {"startingInstances": "StartingInstances"},
        )
        if result.get("success"):
            result["message"] = f"Started {len(instance_ids)} instances"
        return result

    def stop_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """
        Stop EC2 instances, retrying transient AWS errors with backoff.

        Args:
            instance_ids: List of EC2 instance IDs

        Returns:
            Dict: {"success": True, "message", "stoppingInstances"} or a
                  failure dict with "errorCategory" ("permanent" | "transient" | "unknown")
        """
        cred_error = self._credentials_error()
        if cred_error:
            return cred_error

        result = self._call_ec2_with_retry(
            "stopping instances",
            lambda: self.ec2_client.stop_instances(InstanceIds=instance_ids),
            {"stoppingInstances": "StoppingInstances"},
        )
        if result.get("success"):
            result["message"] = f"Stopped {len(instance_ids)} instances"
        return result

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
