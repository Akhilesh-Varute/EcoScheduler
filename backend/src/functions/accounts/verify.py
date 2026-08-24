import os
import sys

# Add common directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from common.auth import get_current_user
from common.utils import create_response
from common.ec2_connector import EC2Connector


def handler(event, context):
    """
    Verify that the EcoScheduler-CrossAccount-Role has been deployed in a given
    AWS account, without requiring that account to already be associated with
    the caller. Used by the account-connection flow before a user adds an
    account to their own profile.

    Deliberately returns only a connectivity result + instance count, not full
    instance details (those still require the account to be on the caller's
    `awsAccounts` list via GET /ec2/list) — this endpoint is authenticated-only
    by design, since it exists specifically to test an account before it's
    claimed by anyone.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    try:
        user = get_current_user(event)
        if not user:
            return create_response(
                401, {"success": False, "message": "Authentication required"}
            )

        query_params = event.get("queryStringParameters", {}) or {}
        account_id = query_params.get("accountId")

        if not account_id:
            return create_response(
                400, {"success": False, "message": "AWS account ID is required"}
            )

        ec2 = EC2Connector(account_id)
        result = ec2.list_instances()

        if result.get("success"):
            return create_response(
                200,
                {
                    "success": True,
                    "connected": True,
                    "instanceCount": len(result.get("instances", [])),
                },
            )
        else:
            return create_response(
                400,
                {
                    "success": False,
                    "connected": False,
                    "message": result.get("message"),
                },
            )

    except Exception as e:
        print(f"Error in account verify handler: {str(e)}")
        return create_response(
            500, {"success": False, "message": "Internal server error"}
        )
