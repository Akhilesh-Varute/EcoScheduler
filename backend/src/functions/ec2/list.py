import json
import os
import sys
from typing import Dict, Any, List

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user, has_permission
from common.utils import create_response
from common.ec2_connector import EC2Connector


def handler(event, context):
    """
    Handle listing EC2 instances

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

        # Parse query parameters
        query_params = event.get("queryStringParameters", {}) or {}
        account_id = query_params.get("accountId")

        # Validate account ID
        if not account_id:
            return create_response(
                400, {"success": False, "message": "AWS account ID is required"}
            )

        # Check permissions
        has_view_permission = has_permission(user, "view_instances")
        is_admin = user["role"] == "admin"
        has_account_access = account_id in user.get("awsAccounts", [])

        if not (is_admin or (has_view_permission and has_account_access)):
            return create_response(
                403,
                {
                    "success": False,
                    "message": "You do not have permission to list instances in this account",
                },
            )

        # Optional tag filters
        tag_filters = None
        if "tagFilters" in query_params:
            try:
                tag_filters = json.loads(query_params.get("tagFilters", "[]"))
            except json.JSONDecodeError:
                return create_response(
                    400,
                    {
                        "success": False,
                        "message": "Invalid tag filters format. Must be valid JSON",
                    },
                )

        # Initialize EC2 connector and list instances
        ec2 = EC2Connector(account_id)
        result = ec2.list_instances(tag_filters)

        if result.get("success"):
            instances = result.get("instances", [])

            # Simplify instance data to reduce response size
            simplified_instances = []

            for instance in instances:
                # Extract instance details
                instance_id = instance.get("InstanceId")
                instance_type = instance.get("InstanceType")
                state = instance.get("State", {}).get("Name")
                name = next(
                    (
                        tag.get("Value")
                        for tag in instance.get("Tags", [])
                        if tag.get("Key") == "Name"
                    ),
                    None,
                )

                # Extract tags
                tags = {}
                for tag in instance.get("Tags", []):
                    if "Key" in tag and "Value" in tag:
                        tags[tag["Key"]] = tag["Value"]

                # Create simplified instance object
                simplified_instance = {
                    "instanceId": instance_id,
                    "name": name or instance_id,
                    "instanceType": instance_type,
                    "state": state,
                    "privateIpAddress": instance.get("PrivateIpAddress"),
                    "publicIpAddress": instance.get("PublicIpAddress"),
                    "launchTime": instance.get("LaunchTime"),
                    "tags": tags,
                    "securityGroups": [
                        sg.get("GroupName") for sg in instance.get("SecurityGroups", [])
                    ],
                    "vpcId": instance.get("VpcId"),
                    "subnetId": instance.get("SubnetId"),
                    "platform": instance.get("Platform", "Linux"),
                }

                simplified_instances.append(simplified_instance)

            return create_response(
                200,
                {
                    "success": True,
                    "instances": simplified_instances,
                    "count": len(simplified_instances),
                },
            )
        else:
            return create_response(
                400,
                {
                    "success": False,
                    "message": result.get("message"),
                    "error": result.get("error"),
                },
            )

    except Exception as e:
        print(f"Error in EC2 list handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
