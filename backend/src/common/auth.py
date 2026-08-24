import jwt
import time
import os
import json
from typing import Dict, Optional, List, Union, Any

# Environment variables
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key')
JWT_ALGORITHM = 'HS256'
TOKEN_EXPIRY = 24 * 60 * 60  # 24 hours

# Role definitions
ROLES = {
    'admin': {
        'description': 'Configures schedules, manages team access',
        'permissions': ['create_schedule', 'update_schedule', 'delete_schedule',
                      'manage_users', 'view_savings', 'manage_accounts',
                      'start_instances', 'stop_instances']
    },
    'developer': {
        'description': 'Manages their own schedules and connected AWS instances',
        'permissions': ['view_schedule', 'create_schedule', 'update_schedule',
                      'delete_schedule', 'request_override', 'view_instances',
                      'start_instances', 'stop_instances', 'view_savings']
    },
    'finance': {
        'description': 'Monitors savings reports',
        'permissions': ['view_savings', 'export_reports']
    }
}


def generate_token(user_id: str, email: str, role: str, aws_accounts: List[str]) -> str:
    """
    Generate a JWT token for a user with role-based permissions
    
    Args:
        user_id: User's unique ID
        email: User's email address
        role: User's role (admin, developer, finance)
        aws_accounts: List of AWS account IDs the user has access to
        
    Returns:
        str: JWT token
    """
    # Validate role
    if role not in ROLES:
        role = 'developer'  # Default to developer if invalid role
    
    payload = {
        'sub': user_id,
        'email': email,
        'role': role,
        'permissions': ROLES[role]['permissions'],
        'aws_accounts': aws_accounts,
        'exp': int(time.time()) + TOKEN_EXPIRY,
        'iat': int(time.time())
    }
    
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token
    
    Args:
        token: JWT token to decode
        
    Returns:
        Dict: Token claims
        
    Raises:
        ValueError: If token is invalid or expired
    """
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def has_permission(token_claims: Dict[str, Any], required_permission: str) -> bool:
    """
    Check if a user has a specific permission
    
    Args:
        token_claims: Decoded JWT token claims
        required_permission: Permission to check
        
    Returns:
        bool: True if user has permission, False otherwise
    """
    permissions = token_claims.get('permissions', [])
    return required_permission in permissions


def lambda_authorizer(event, context):
    """
    Custom JWT authorizer for API Gateway
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        Dict: IAM policy document
    """
    try:
        # Extract token from Authorization header
        auth_header = event.get('authorizationToken', '')
        if not auth_header.startswith('Bearer '):
            raise ValueError("Authorization header must start with 'Bearer '")
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Decode and validate token
        claims = decode_token(token)
        
        # Create AWS policy document
        policy = {
            'principalId': claims['sub'],
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Allow',
                        'Resource': event['methodArn']
                    }
                ]
            },
            'context': {
                'userId': claims['sub'],
                'email': claims['email'],
                'role': claims['role'],
                'permissions': json.dumps(claims['permissions']),
                'awsAccounts': json.dumps(claims['aws_accounts'])
            }
        }
        
        return policy
    except Exception as e:
        print(f"Authorization failed: {str(e)}")
        # Unauthorized
        raise Exception(f"Unauthorized: {str(e)}")


def get_token_from_header(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract JWT token from Authorization header
    
    Args:
        event: API Gateway event
        
    Returns:
        Optional[str]: JWT token or None if not found
    """
    headers = event.get('headers', {}) or {}
    auth_header = headers.get('Authorization', '')
    
    if not auth_header.startswith('Bearer '):
        return None
    
    return auth_header[7:]  # Remove 'Bearer ' prefix


def get_current_user(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get current user from API Gateway event
    
    Args:
        event: API Gateway event
        
    Returns:
        Optional[Dict]: User information or None if not authenticated
    """
    # First try to get from authorizer context
    auth_context = event.get('requestContext', {}).get('authorizer', {})
    if auth_context:
        return {
            'userId': auth_context.get('userId'),
            'email': auth_context.get('email'),
            'role': auth_context.get('role'),
            'permissions': json.loads(auth_context.get('permissions', '[]')),
            'awsAccounts': json.loads(auth_context.get('awsAccounts', '[]'))
        }
    
    # If not available, try to decode from token
    token = get_token_from_header(event)
    if token:
        try:
            claims = decode_token(token)
            return {
                'userId': claims.get('sub'),
                'email': claims.get('email'),
                'role': claims.get('role'),
                'permissions': claims.get('permissions', []),
                'awsAccounts': claims.get('aws_accounts', [])
            }
        except Exception:
            return None
    
    return None


def require_permission(permission: str):
    """
    Decorator to require a specific permission for a Lambda handler
    
    Args:
        permission: Required permission
        
    Returns:
        Function: Decorated function
    """
    def decorator(func):
        def wrapper(event, context):
            user = get_current_user(event)
            
            if not user:
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Authentication required'})
                }
            
            if permission not in user.get('permissions', []):
                return {
                    'statusCode': 403,
                    'body': json.dumps({'error': 'Permission denied'})
                }
            
            return func(event, context)
        
        return wrapper
    
    return decorator