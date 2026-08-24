import json
from typing import Dict, Any, List, Union, Optional
import datetime
import re
import boto3
import os
from decimal import Decimal
from croniter import croniter
from dateutil import parser, tz


def create_response(status_code: int, body: Any) -> Dict[str, Any]:
    """
    Create a standardized API response

    Args:
        status_code: HTTP status code
        body: Response body

    Returns:
        Dict: API Gateway response object
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # For CORS
            "Access-Control-Allow-Credentials": True,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
        },
        "body": json.dumps(body, default=json_serializer),
    }


def json_serializer(obj):
    """
    JSON serializer for objects not serializable by default json code

    Args:
        obj: Object to serialize

    Returns:
        str or dict: Serialized object
    """
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()

    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)

    if hasattr(obj, "__dict__"):
        return obj.__dict__

    raise TypeError(f"Type {type(obj)} not serializable")


def validate_cron_expression(cron_expr: str) -> bool:
    """
    Validate a cron expression

    Args:
        cron_expr: Cron expression to validate

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        croniter(cron_expr)
        return True
    except Exception:
        return False


def get_next_schedule_time(cron_expr: str, timezone: str = "UTC") -> datetime.datetime:
    """
    Get the next schedule time from a cron expression

    Args:
        cron_expr: Cron expression
        timezone: Timezone (default: UTC)

    Returns:
        datetime: Next schedule time
    """
    now = datetime.datetime.now(tz.gettz(timezone))
    cron = croniter(cron_expr, now)
    return cron.get_next(datetime.datetime)


def parse_aws_arn(arn: str) -> Dict[str, str]:
    """
    Parse an AWS ARN into its components

    Args:
        arn: ARN to parse

    Returns:
        Dict: ARN components
    """
    # ARN format: arn:partition:service:region:account-id:resource
    # or: arn:partition:service:region:account-id:resource-type/resource-id
    parts = arn.split(":")

    if len(parts) < 6:
        raise ValueError(f"Invalid ARN format: {arn}")

    result = {
        "arn": arn,
        "partition": parts[1],
        "service": parts[2],
        "region": parts[3],
        "account_id": parts[4],
    }

    # Handle resource part
    if len(parts) >= 6:
        resource_part = ":".join(parts[5:])

        # Check if resource part contains a slash
        if "/" in resource_part:
            resource_type, resource_id = resource_part.split("/", 1)
            result["resource_type"] = resource_type
            result["resource_id"] = resource_id
        else:
            result["resource"] = resource_part

    return result


def assume_role(
    account_id: str, role_name: str = "EcoScheduler-CrossAccount-Role"
) -> Dict[str, Any]:
    """
    Assume a cross-account IAM role

    Args:
        account_id: AWS account ID
        role_name: IAM role name

    Returns:
        Dict: Credentials for the assumed role
    """
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    try:
        sts_client = boto3.client("sts")
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="EcoSchedulerSession",
            DurationSeconds=3600,  # 1 hour
        )

        return {
            "aws_access_key_id": response["Credentials"]["AccessKeyId"],
            "aws_secret_access_key": response["Credentials"]["SecretAccessKey"],
            "aws_session_token": response["Credentials"]["SessionToken"],
            "expiration": response["Credentials"]["Expiration"],
        }
    except Exception as e:
        print(f"Error assuming role {role_arn}: {str(e)}")
        raise Exception(f"Failed to assume role in account {account_id}: {str(e)}")


def get_instance_price(instance_type: str, region: str, os: str = "Linux") -> float:
    """
    Get the hourly price for an EC2 instance type

    Args:
        instance_type: EC2 instance type (e.g., t2.micro)
        region: AWS region (e.g., us-east-1)
        os: Operating system (default: Linux)

    Returns:
        float: Hourly price in USD
    """
    # In a real implementation, this would call the AWS Price List API
    # For now, we'll use a simplified lookup table

    # Default prices (very rough estimates, use AWS Price List API for accuracy)
    price_table = {
        "t2.micro": 0.0116,
        "t2.small": 0.023,
        "t2.medium": 0.0464,
        "t2.large": 0.0928,
        "t3.micro": 0.0104,
        "t3.small": 0.0208,
        "t3.medium": 0.0416,
        "m5.large": 0.096,
        "m5.xlarge": 0.192,
        "c5.large": 0.085,
        "c5.xlarge": 0.17,
        "r5.large": 0.126,
        "r5.xlarge": 0.252,
    }

    # Regional multipliers (very simplified)
    region_multipliers = {
        "us-east-1": 1.0,  # N. Virginia
        "us-east-2": 1.0,  # Ohio
        "us-west-1": 1.2,  # N. California
        "us-west-2": 1.1,  # Oregon
        "eu-west-1": 1.15,  # Ireland
        "eu-central-1": 1.2,  # Frankfurt
        "ap-northeast-1": 1.25,  # Tokyo
        "ap-southeast-1": 1.2,  # Singapore
        "ap-southeast-2": 1.2,  # Sydney
    }

    # OS multipliers
    os_multipliers = {"Linux": 1.0, "Windows": 2.0, "RHEL": 1.7, "SUSE": 1.4}

    # Get base price
    base_price = price_table.get(instance_type, 0.05)  # Default if not found

    # Apply multipliers
    region_mult = region_multipliers.get(region, 1.1)
    os_mult = os_multipliers.get(os, 1.0)

    return round(base_price * region_mult * os_mult, 4)


def is_valid_email(email: str) -> bool:
    """
    Validate an email address

    Args:
        email: Email address to validate

    Returns:
        bool: True if valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def is_valid_aws_account_id(account_id: str) -> bool:
    """
    Validate an AWS account ID

    Args:
        account_id: AWS account ID to validate

    Returns:
        bool: True if valid, False otherwise
    """
    pattern = r"^[0-9]{12}$"
    return bool(re.match(pattern, account_id))


def is_valid_instance_id(instance_id: str) -> bool:
    """
    Validate an EC2 instance ID

    Args:
        instance_id: EC2 instance ID to validate

    Returns:
        bool: True if valid, False otherwise
    """
    pattern = r"^i-[a-f0-9]{8,17}$"
    return bool(re.match(pattern, instance_id))


def get_eventbridge_client():
    """
    Get an EventBridge client

    Returns:
        boto3.client: EventBridge client
    """
    return boto3.client("events")


def create_eventbridge_rule(
    name: str, schedule_expression: str, target_arn: str, input_json: Dict[str, Any]
) -> str:
    """
    Create an EventBridge rule

    Args:
        name: Rule name
        schedule_expression: Schedule expression (cron or rate)
        target_arn: Target Lambda ARN
        input_json: Input to pass to the target

    Returns:
        str: Rule ARN
    """
    events = get_eventbridge_client()

    # Create rule
    rule_response = events.put_rule(
        Name=name,
        ScheduleExpression=schedule_expression,
        State="ENABLED",
        Description=f"EcoScheduler rule for {name}",
    )

    # EventBridge needs its own resource-based permission on the target Lambda
    # to actually invoke it when the rule fires - put_targets succeeding does
    # NOT grant this. Without it, the rule fires "successfully" but the
    # invocation is silently rejected with no error visible anywhere except
    # the Lambda's own (empty) invocation logs. Ensure it exists before wiring
    # up the target, idempotently (safe to call for every rule pointing at the
    # same function).
    _ensure_eventbridge_invoke_permission(target_arn, rule_response["RuleArn"])

    # Add target
    events.put_targets(
        Rule=name,
        Targets=[
            {"Id": f"{name}-target", "Arn": target_arn, "Input": json.dumps(input_json)}
        ],
    )

    return rule_response["RuleArn"]


def _ensure_eventbridge_invoke_permission(target_arn: str, rule_arn: str) -> None:
    """
    Grant EventBridge permission to invoke a target Lambda function, if it
    doesn't already have it. Scoped to any EcoScheduler-managed rule (not just
    this one rule_arn), since many schedules' rules all target the same
    EC2Start/EC2Stop function - adding a fresh statement per rule would hit
    Lambda's resource policy size limit quickly.

    Args:
        target_arn: ARN of the Lambda function EventBridge will invoke
        rule_arn: ARN of the rule being wired up (used to derive the
            wildcard source-arn pattern all EcoScheduler rules share)
    """
    lambda_client = boto3.client("lambda")

    # rule_arn looks like arn:aws:events:region:account:rule/RuleName -
    # build a wildcard covering every EcoScheduler-* rule in this account/region
    arn_prefix = rule_arn.rsplit("/", 1)[0]
    source_arn_pattern = f"{arn_prefix}/EcoScheduler-*"

    try:
        lambda_client.add_permission(
            FunctionName=target_arn,
            StatementId="AllowEventBridgeInvoke",
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=source_arn_pattern,
        )
    except lambda_client.exceptions.ResourceConflictException:
        # Permission already granted (e.g. a previous schedule already added it
        # for this same function) - nothing to do.
        pass


def delete_eventbridge_rule(name: str) -> bool:
    """
    Delete an EventBridge rule

    Args:
        name: Rule name

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        events = get_eventbridge_client()

        # Remove targets
        events.remove_targets(Rule=name, Ids=[f"{name}-target"])

        # Delete rule
        events.delete_rule(Name=name)

        return True
    except Exception as e:
        print(f"Error deleting EventBridge rule {name}: {str(e)}")
        return False
