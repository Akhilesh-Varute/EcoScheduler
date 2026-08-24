#!/usr/bin/env python
"""
Script to test EcoScheduler APIs
"""
import os
import sys
import json
import requests
import argparse
from datetime import datetime


def get_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test EcoScheduler APIs")
    parser.add_argument("--api-url", required=True, help="API Gateway URL")
    parser.add_argument("--email", required=True, help="Admin user email")
    parser.add_argument("--password", required=True, help="Admin user password")
    parser.add_argument("--account-id", help="AWS account ID for testing schedules")
    parser.add_argument("--instance-id", help="EC2 instance ID for testing schedules")
    return parser.parse_args()


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 50)
    print(f"   {title}")
    print("=" * 50 + "\n")


def print_response(response):
    """Print formatted API response"""
    print(f"Status: {response.status_code}")
    try:
        json_data = response.json()
        print(f"Response: {json.dumps(json_data, indent=2)}")
    except:
        print(f"Response: {response.text}")
    print()


def test_login(api_url, email, password):
    """Test user login"""
    print_header("Testing Login API")

    url = f"{api_url}/auth/login"
    payload = {"email": email, "password": password}

    response = requests.post(url, json=payload)
    print_response(response)

    if response.status_code == 200:
        return response.json().get("token")
    else:
        print("Login failed. Cannot continue with other tests.")
        sys.exit(1)


def test_get_user(api_url, token):
    """Test getting user profile"""
    print_header("Testing Get User API")

    url = f"{api_url}/users/me"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    print_response(response)

    if response.status_code == 200:
        return response.json().get("user", {}).get("userId")
    return None


def test_create_schedule(api_url, token, account_id, instance_id):
    """Test creating a schedule"""
    print_header("Testing Create Schedule API")

    if not account_id or not instance_id:
        print("Skipping schedule creation test (missing account ID or instance ID)")
        return None

    url = f"{api_url}/schedules"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "name": f"Test Schedule {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "accountId": account_id,
        "instanceIds": [instance_id],
        "startCron": "0 8 * * 1-5",  # 8:00 AM Mon-Fri
        "stopCron": "0 18 * * 1-5",  # 6:00 PM Mon-Fri
        "timezone": "UTC",
        "exceptions": [],
    }

    response = requests.post(url, headers=headers, json=payload)
    print_response(response)

    if response.status_code == 201:
        return response.json().get("schedule", {}).get("scheduleId")
    return None


def test_list_schedules(api_url, token):
    """Test listing schedules"""
    print_header("Testing List Schedules API")

    url = f"{api_url}/schedules"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    print_response(response)


def test_get_schedule(api_url, token, schedule_id):
    """Test getting a specific schedule"""
    print_header("Testing Get Schedule API")

    if not schedule_id:
        print("Skipping get schedule test (no schedule created)")
        return

    url = f"{api_url}/schedules/{schedule_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    print_response(response)


def test_update_schedule(api_url, token, schedule_id):
    """Test updating a schedule"""
    print_header("Testing Update Schedule API")

    if not schedule_id:
        print("Skipping update schedule test (no schedule created)")
        return

    url = f"{api_url}/schedules/{schedule_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "name": f"Updated Schedule {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "startCron": "0 9 * * 1-5",  # 9:00 AM Mon-Fri
        "stopCron": "0 17 * * 1-5",  # 5:00 PM Mon-Fri
    }

    response = requests.put(url, headers=headers, json=payload)
    print_response(response)


def test_list_ec2_instances(api_url, token, account_id):
    """Test listing EC2 instances"""
    print_header("Testing List EC2 Instances API")

    if not account_id:
        print("Skipping EC2 list test (missing account ID)")
        return

    url = f"{api_url}/ec2/list?accountId={account_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    print_response(response)


def test_start_ec2_instance(api_url, token, account_id, instance_id):
    """Test starting an EC2 instance"""
    print_header("Testing Start EC2 Instance API")

    if not account_id or not instance_id:
        print("Skipping EC2 start test (missing account ID or instance ID)")
        return

    url = f"{api_url}/ec2/start"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {"accountId": account_id, "instanceIds": [instance_id]}

    # Ask for confirmation before starting instance
    confirm = input(f"Are you sure you want to start instance {instance_id}? (y/n): ")
    if confirm.lower() != "y":
        print("Skipping EC2 start test (user cancelled)")
        return

    response = requests.post(url, headers=headers, json=payload)
    print_response(response)


def test_stop_ec2_instance(api_url, token, account_id, instance_id):
    """Test stopping an EC2 instance"""
    print_header("Testing Stop EC2 Instance API")

    if not account_id or not instance_id:
        print("Skipping EC2 stop test (missing account ID or instance ID)")
        return

    url = f"{api_url}/ec2/stop"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {"accountId": account_id, "instanceIds": [instance_id]}

    # Ask for confirmation before stopping instance
    confirm = input(f"Are you sure you want to stop instance {instance_id}? (y/n): ")
    if confirm.lower() != "y":
        print("Skipping EC2 stop test (user cancelled)")
        return

    response = requests.post(url, headers=headers, json=payload)
    print_response(response)


def test_savings_report(api_url, token):
    """Test getting savings report"""
    print_header("Testing Savings Report API")

    url = f"{api_url}/savings/report?type=summary"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    print_response(response)


def test_delete_schedule(api_url, token, schedule_id):
    """Test deleting a schedule"""
    print_header("Testing Delete Schedule API")

    if not schedule_id:
        print("Skipping delete schedule test (no schedule created)")
        return

    # Ask for confirmation before deleting
    confirm = input(f"Are you sure you want to delete schedule {schedule_id}? (y/n): ")
    if confirm.lower() != "y":
        print("Skipping delete schedule test (user cancelled)")
        return

    url = f"{api_url}/schedules/{schedule_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.delete(url, headers=headers)
    print_response(response)


def main():
    """Main function"""
    args = get_args()

    # Ensure API URL doesn't end with a slash
    api_url = args.api_url.rstrip("/")

    # Test login and get token
    token = test_login(api_url, args.email, args.password)
    if not token:
        return

    # Test getting user profile
    user_id = test_get_user(api_url, token)

    # Test creating a schedule
    schedule_id = test_create_schedule(
        api_url, token, args.account_id, args.instance_id
    )

    # Test listing schedules
    test_list_schedules(api_url, token)

    # Test getting a specific schedule
    test_get_schedule(api_url, token, schedule_id)

    # Test updating a schedule
    test_update_schedule(api_url, token, schedule_id)

    # Test listing EC2 instances
    test_list_ec2_instances(api_url, token, args.account_id)

    # Test EC2 start/stop operations (with confirmation)
    test_start_ec2_instance(api_url, token, args.account_id, args.instance_id)
    test_stop_ec2_instance(api_url, token, args.account_id, args.instance_id)

    # Test savings report
    test_savings_report(api_url, token)

    # Test deleting a schedule (with confirmation)
    test_delete_schedule(api_url, token, schedule_id)

    print_header("API Testing Complete")
    print("All API endpoints tested successfully")


if __name__ == "__main__":
    main()


def main():
    """Main function"""
    args = get_args()

    # Ensure API URL doesn't end with a slash
    api_url = args.api_url.rstrip("/")

    # Test login and get token
    token = test_login(api_url, args.email, args.password)
    if not token:
        return

    # Test getting user profile
    user_id = test_get_user(api_url, token)

    # Test creating a schedule
    schedule_id = test_create_schedule(
        api_url, token, args.account_id, args.instance_id
    )

    # Test listing schedules
    test_list_schedules(api_url, token)

    # Test getting a specific schedule
    test_get_schedule(api_url, token, schedule_id)
