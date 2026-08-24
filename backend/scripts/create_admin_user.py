#!/usr/bin/env python
"""
Script to create an admin user in the EcoScheduler application
"""
import os
import sys
import json
import boto3
import uuid
import getpass
import argparse
import time

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from common packages
from src.common.db_models import DynamoDBTables, UserModel, hash_password
from src.common.utils import is_valid_email


def get_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Create an admin user for EcoScheduler"
    )
    parser.add_argument("--email", help="Admin user email address")
    parser.add_argument("--name", help="Admin user full name")
    parser.add_argument(
        "--aws-accounts", help="Comma-separated list of AWS account IDs", default=""
    )
    parser.add_argument("--stage", help="Deployment stage", default="dev")
    parser.add_argument("--region", help="AWS region", default="us-east-1")
    return parser.parse_args()


def main():
    """Main function"""
    args = get_args()

    # Set environment variables for DynamoDB table names
    stage = args.stage
    region = args.region

    # Set table names based on stage
    os.environ["USERS_TABLE"] = f"eco-scheduler-users-{stage}"
    os.environ["SCHEDULES_TABLE"] = f"eco-scheduler-schedules-{stage}"
    os.environ["SAVINGS_TABLE"] = f"eco-scheduler-savings-{stage}"
    os.environ["EXCEPTIONS_TABLE"] = f"eco-scheduler-exceptions-{stage}"

    # Check if tables exist
    dynamodb = boto3.resource("dynamodb", region_name=region)
    try:
        dynamodb.Table(os.environ["USERS_TABLE"]).table_status
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        print(f"Error: DynamoDB table {os.environ['USERS_TABLE']} not found.")
        print(
            f"Make sure you have deployed the application with 'npm run deploy:{stage}' first."
        )
        sys.exit(1)

    # Get user information
    email = args.email
    while not email or not is_valid_email(email):
        email = input("Enter admin email address: ").strip().lower()
        if not is_valid_email(email):
            print("Invalid email format. Please try again.")

    # Get user name
    name = args.name
    if not name:
        name = input("Enter admin full name: ").strip()

    # Get password
    password = getpass.getpass("Enter admin password: ")
    confirm_password = getpass.getpass("Confirm password: ")

    if password != confirm_password:
        print("Passwords do not match. Please try again.")
        sys.exit(1)

    if len(password) < 8:
        print("Password must be at least 8 characters long.")
        sys.exit(1)

    # Parse AWS accounts
    aws_accounts = []
    if args.aws_accounts:
        aws_accounts = [
            acc.strip() for acc in args.aws_accounts.split(",") if acc.strip()
        ]
    else:
        accounts_input = input(
            "Enter AWS account IDs (comma-separated, leave blank if none): "
        )
        if accounts_input.strip():
            aws_accounts = [
                acc.strip() for acc in accounts_input.split(",") if acc.strip()
            ]

    # Validate AWS account IDs
    for account in aws_accounts:
        if not account.isdigit() or len(account) != 12:
            print(f"Invalid AWS account ID: {account}. Must be a 12-digit number.")
            sys.exit(1)

    # Initialize database
    db_tables = DynamoDBTables(region_name=region)
    tables = db_tables.get_tables()
    user_model = UserModel(tables["users"])

    # Check if user already exists
    existing_user = user_model.get_user_by_email(email)
    if existing_user:
        print(f"User with email {email} already exists.")
        update = input("Do you want to update this user to admin role? (y/n): ")
        if update.lower() == "y":
            user_model.update_user(
                existing_user["userId"],
                {
                    "role": "admin",
                    "awsAccounts": aws_accounts,
                    "password": hash_password(password),
                },
            )
            print(f"User {email} has been updated to admin role.")
            sys.exit(0)
        else:
            sys.exit(1)

    # Create admin user
    try:
        user = user_model.create_user(
            email=email,
            password=password,  # In production, this should be hashed
            role="admin",
            aws_accounts=aws_accounts,
            name=name,
        )
        print(f"\nAdmin user created successfully:")
        print(f"User ID: {user['userId']}")
        print(f"Email: {user['email']}")
        print(f"Role: {user['role']}")
        print(
            f"AWS Accounts: {', '.join(user['awsAccounts']) if user['awsAccounts'] else 'None'}"
        )
        print("\nYou can now log in to the application with these credentials.")
    except Exception as e:
        print(f"Error creating admin user: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
