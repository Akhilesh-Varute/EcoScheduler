import os
import sys
import json

# Add the common directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
from common.auth import decode_token


def handler(event, context):
    """
    Custom JWT authorizer for API Gateway

    Args:
        event: API Gateway authorizer event
        context: Lambda context

    Returns:
        Dict: IAM policy document
    """
    try:
        # Get the token from the Authorization header
        token = event.get("authorizationToken", "")

        if not token:
            raise Exception("Authorization header is missing")

        # Check if it has the Bearer prefix
        if token.startswith("Bearer "):
            token = token[7:]  # Remove 'Bearer ' prefix

        # Decode and validate the token
        claims = decode_token(token)

        # Scope to the whole API+stage, not just the one route currently being
        # called. API Gateway caches the authorizer's returned policy per-token
        # (resultTtlInSeconds, default 300s) and reuses it for ANY subsequent
        # request using that same token — if the Resource here were scoped to
        # just this one method ARN, every other route would get an implicit
        # deny for the rest of that cache window the first time a fresh token
        # is used anywhere else.
        wildcard_resource = _wildcard_resource(event["methodArn"])

        # Create an IAM policy
        policy = generate_policy(claims["sub"], "Allow", wildcard_resource, claims)
        return policy

    except Exception as e:
        print(f"Authorization failed: {str(e)}")
        # For security, don't include error details in response
        return generate_policy(
            "anonymous", "Deny", _wildcard_resource(event["methodArn"]), {}
        )


def _wildcard_resource(method_arn: str) -> str:
    """
    Turn a specific method ARN
    (arn:aws:execute-api:region:account:apiId/stage/METHOD/path)
    into a wildcard covering every method/path on that API+stage.
    """
    arn_prefix, stage, *_ = method_arn.split("/", 2)
    return f"{arn_prefix}/{stage}/*"


def generate_policy(principal_id, effect, resource, claims=None):
    """
    Generate an IAM policy document

    Args:
        principal_id: Principal ID (user ID)
        effect: Allow or Deny
        resource: Resource ARN
        claims: Token claims to include in context

    Returns:
        Dict: Policy document
    """
    policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}
            ],
        },
    }

    # Add context if claims are provided
    if claims:
        # Include relevant user info in context
        # These values will be available in the event.requestContext.authorizer object
        context = {
            "userId": claims.get("sub", ""),
            "email": claims.get("email", ""),
            "role": claims.get("role", ""),
        }

        # Add permissions and AWS accounts as JSON strings (API Gateway context must be string values)
        if "permissions" in claims:
            context["permissions"] = json.dumps(claims["permissions"])

        if "aws_accounts" in claims:
            context["awsAccounts"] = json.dumps(claims["aws_accounts"])

        policy["context"] = context

    return policy
