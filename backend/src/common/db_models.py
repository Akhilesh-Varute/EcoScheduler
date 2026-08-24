import boto3
import uuid
import time
import os
import hashlib
import hmac
import secrets
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Any, Optional
from boto3.dynamodb.conditions import Key, Attr

PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """
    Hash a password with PBKDF2-HMAC-SHA256 (stdlib only, no native deps).

    Returns a self-describing string: "pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>"
    """
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """
    Verify a password against a hash produced by hash_password().
    """
    try:
        algorithm, iterations, salt, hash_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(derived.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


class DynamoDBTables:
    """
    Class for handling DynamoDB tables creation and access
    """

    def __init__(self, region_name=None):
        """
        Initialize DynamoDB tables manager

        Args:
            region_name: AWS region name (defaults to environment variable or 'us-east-1')
        """
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region_name)

        # Table names from environment variables with defaults
        self.tables = {
            "users": os.environ.get("USERS_TABLE", "EcoScheduler-Users"),
            "schedules": os.environ.get("SCHEDULES_TABLE", "EcoScheduler-Schedules"),
            "savings": os.environ.get("SAVINGS_TABLE", "EcoScheduler-Savings"),
            "exceptions": os.environ.get("EXCEPTIONS_TABLE", "EcoScheduler-Exceptions"),
            "auditLogs": os.environ.get("AUDIT_LOGS_TABLE", "EcoScheduler-AuditLogs"),
        }

    def create_tables(self):
        """
        Create the required DynamoDB tables if they don't exist

        Returns:
            Dict: References to all created tables
        """
        tables = {}

        # Users Table
        try:
            tables["users"] = self.dynamodb.create_table(
                TableName=self.tables["users"],
                KeySchema=[
                    {"AttributeName": "userId", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "userId", "AttributeType": "S"},
                    {"AttributeName": "email", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "EmailIndex",
                        "KeySchema": [
                            {"AttributeName": "email", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            print(f"Table {self.tables['users']} created successfully")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"Table {self.tables['users']} already exists")
            tables["users"] = self.dynamodb.Table(self.tables["users"])

        # Schedules Table
        try:
            tables["schedules"] = self.dynamodb.create_table(
                TableName=self.tables["schedules"],
                KeySchema=[
                    {"AttributeName": "scheduleId", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "scheduleId", "AttributeType": "S"},
                    {"AttributeName": "userId", "AttributeType": "S"},
                    {"AttributeName": "accountId", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "UserIdIndex",
                        "KeySchema": [
                            {"AttributeName": "userId", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                    {
                        "IndexName": "AccountIdIndex",
                        "KeySchema": [
                            {"AttributeName": "accountId", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            print(f"Table {self.tables['schedules']} created successfully")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"Table {self.tables['schedules']} already exists")
            tables["schedules"] = self.dynamodb.Table(self.tables["schedules"])

        # Savings Table
        try:
            tables["savings"] = self.dynamodb.create_table(
                TableName=self.tables["savings"],
                KeySchema=[
                    {"AttributeName": "savingsId", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "savingsId", "AttributeType": "S"},
                    {"AttributeName": "scheduleId", "AttributeType": "S"},
                    {"AttributeName": "date", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "ScheduleIdIndex",
                        "KeySchema": [
                            {"AttributeName": "scheduleId", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                    {
                        "IndexName": "DateIndex",
                        "KeySchema": [
                            {"AttributeName": "date", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            print(f"Table {self.tables['savings']} created successfully")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"Table {self.tables['savings']} already exists")
            tables["savings"] = self.dynamodb.Table(self.tables["savings"])

        # Exceptions Table
        try:
            tables["exceptions"] = self.dynamodb.create_table(
                TableName=self.tables["exceptions"],
                KeySchema=[
                    {"AttributeName": "exceptionId", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "exceptionId", "AttributeType": "S"},
                    {"AttributeName": "scheduleId", "AttributeType": "S"},
                    {"AttributeName": "date", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "ScheduleIdIndex",
                        "KeySchema": [
                            {"AttributeName": "scheduleId", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                    {
                        "IndexName": "DateIndex",
                        "KeySchema": [
                            {"AttributeName": "date", "KeyType": "HASH"},
                            {"AttributeName": "scheduleId", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            print(f"Table {self.tables['exceptions']} created successfully")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"Table {self.tables['exceptions']} already exists")
            tables["exceptions"] = self.dynamodb.Table(self.tables["exceptions"])

        # Audit Logs Table
        try:
            tables["auditLogs"] = self.dynamodb.create_table(
                TableName=self.tables["auditLogs"],
                KeySchema=[
                    {"AttributeName": "auditId", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "auditId", "AttributeType": "S"},
                    {"AttributeName": "scheduleId", "AttributeType": "S"},
                    {"AttributeName": "accountId", "AttributeType": "S"},
                    {"AttributeName": "date", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "N"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "ScheduleIdIndex",
                        "KeySchema": [
                            {"AttributeName": "scheduleId", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                    {
                        "IndexName": "AccountIdIndex",
                        "KeySchema": [
                            {"AttributeName": "accountId", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                    {
                        "IndexName": "DateIndex",
                        "KeySchema": [
                            {"AttributeName": "date", "KeyType": "HASH"},
                            {"AttributeName": "timestamp", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            print(f"Table {self.tables['auditLogs']} created successfully")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            print(f"Table {self.tables['auditLogs']} already exists")
            tables["auditLogs"] = self.dynamodb.Table(self.tables["auditLogs"])

        return tables

    def get_tables(self):
        """
        Get references to existing DynamoDB tables

        Returns:
            Dict: References to all tables
        """
        return {
            "users": self.dynamodb.Table(self.tables["users"]),
            "schedules": self.dynamodb.Table(self.tables["schedules"]),
            "savings": self.dynamodb.Table(self.tables["savings"]),
            "exceptions": self.dynamodb.Table(self.tables["exceptions"]),
            "auditLogs": self.dynamodb.Table(self.tables["auditLogs"]),
        }


class UserModel:
    """
    Class for User data model operations
    """

    def __init__(self, users_table):
        """
        Initialize User model

        Args:
            users_table: DynamoDB users table reference
        """
        self.table = users_table

    def create_user(
        self,
        email: str,
        password: str,
        role: str = "developer",
        aws_accounts: List[str] = None,
        name: str = None,
    ) -> Dict[str, Any]:
        """
        Create a new user

        Args:
            email: User email address
            password: Plaintext password (hashed with bcrypt before storage)
            role: User role (admin, developer, finance)
            aws_accounts: List of AWS account IDs the user has access to
            name: User's full name

        Returns:
            Dict: Created user object (without password)
        """
        if aws_accounts is None:
            aws_accounts = []

        # Generate UUID for user
        user_id = str(uuid.uuid4())
        timestamp = int(time.time())

        # Create user item
        item = {
            "userId": user_id,
            "email": email,
            "password": hash_password(password),
            "role": role,
            "awsAccounts": aws_accounts,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }

        # Add name if provided
        if name:
            item["name"] = name

        # Save to DynamoDB
        self.table.put_item(Item=item)

        # Remove password from returned item
        item_copy = item.copy()
        if "password" in item_copy:
            del item_copy["password"]

        return item_copy

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by ID

        Args:
            user_id: User ID

        Returns:
            Optional[Dict]: User object or None if not found
        """
        response = self.table.get_item(Key={"userId": user_id})

        if "Item" not in response:
            return None

        # Remove password from returned item
        item = response["Item"]
        if "password" in item:
            del item["password"]

        return item

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email

        Args:
            email: User email address

        Returns:
            Optional[Dict]: User object or None if not found
        """
        response = self.table.query(
            IndexName="EmailIndex", KeyConditionExpression=Key("email").eq(email)
        )

        if not response["Items"]:
            return None

        # Remove password from returned item
        item = response["Items"][0]
        if "password" in item:
            del item["password"]

        return item

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with email and password

        Args:
            email: User email address
            password: User password

        Returns:
            Optional[Dict]: User object or None if authentication fails
        """
        response = self.table.query(
            IndexName="EmailIndex", KeyConditionExpression=Key("email").eq(email)
        )

        if not response["Items"]:
            return None

        user = response["Items"][0]

        # Check password
        if not verify_password(password, user.get("password", "")):
            return None

        # Remove password from returned user
        user_copy = user.copy()
        if "password" in user_copy:
            del user_copy["password"]

        return user_copy

    def update_user(
        self, user_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update a user

        Args:
            user_id: User ID
            updates: Dictionary of fields to update

        Returns:
            Optional[Dict]: Updated user object or None if not found
        """
        # First check if user exists
        if not self.get_user(user_id):
            return None

        # Build update expression
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        for key, value in updates.items():
            if key not in ["userId", "createdAt"]:  # Can't update these fields
                update_expression_parts.append(f"#{key} = :{key}")
                expression_attribute_values[f":{key}"] = value
                expression_attribute_names[f"#{key}"] = key

        if not update_expression_parts:
            return self.get_user(user_id)  # No updates to apply

        # Add updatedAt timestamp
        update_expression_parts.append("#updatedAt = :updatedAt")
        expression_attribute_values[":updatedAt"] = int(time.time())
        expression_attribute_names["#updatedAt"] = "updatedAt"

        # Create update expression
        update_expression = "SET " + ", ".join(update_expression_parts)

        # Update item
        response = self.table.update_item(
            Key={"userId": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW",
        )

        # Remove password from returned item
        item = response.get("Attributes", {})
        if "password" in item:
            del item["password"]

        return item

    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user

        Args:
            user_id: User ID

        Returns:
            bool: True if successful, False if user not found
        """
        # First check if user exists
        if not self.get_user(user_id):
            return False

        # Delete user
        self.table.delete_item(Key={"userId": user_id})
        return True

    def list_users(
        self, limit: int = 100, last_evaluated_key: Dict = None
    ) -> Dict[str, Any]:
        """
        List all users with pagination

        Args:
            limit: Maximum number of items to return
            last_evaluated_key: Last evaluated key for pagination

        Returns:
            Dict: List of users and last evaluated key for pagination
        """
        params = {"Limit": limit}

        if last_evaluated_key:
            params["ExclusiveStartKey"] = last_evaluated_key

        response = self.table.scan(**params)

        # Remove passwords from all items
        items = response.get("Items", [])
        for item in items:
            if "password" in item:
                del item["password"]

        return {"items": items, "lastEvaluatedKey": response.get("LastEvaluatedKey")}


class ScheduleModel:
    """
    Class for Schedule data model operations
    """

    def __init__(self, schedules_table):
        """
        Initialize Schedule model

        Args:
            schedules_table: DynamoDB schedules table reference
        """
        self.table = schedules_table

    def create_schedule(
        self,
        user_id: str,
        name: str,
        account_id: str,
        instance_ids: List[str],
        start_cron: str,
        stop_cron: str,
        timezone: str = "UTC",
        exceptions: List[str] = None,
        tags: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new schedule

        Args:
            user_id: Owner user ID
            name: Schedule name
            account_id: AWS account ID
            instance_ids: List of EC2 instance IDs
            start_cron: Cron expression for start time
            stop_cron: Cron expression for stop time
            timezone: Timezone (default: UTC)
            exceptions: List of exception dates (ISO format)
            tags: Tags for the schedule

        Returns:
            Dict: Created schedule object
        """
        if exceptions is None:
            exceptions = []

        if tags is None:
            tags = {}

        # Generate UUID for schedule
        schedule_id = str(uuid.uuid4())
        timestamp = int(time.time())

        # Create schedule item
        item = {
            "scheduleId": schedule_id,
            "userId": user_id,
            "name": name,
            "accountId": account_id,
            "instanceIds": instance_ids,
            "startCron": start_cron,
            "stopCron": stop_cron,
            "timezone": timezone,
            "exceptions": exceptions,
            "tags": tags,
            "enabled": True,
            "dryRun": False,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }

        # Save to DynamoDB
        self.table.put_item(Item=item)
        return item

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a schedule by ID

        Args:
            schedule_id: Schedule ID

        Returns:
            Optional[Dict]: Schedule object or None if not found
        """
        response = self.table.get_item(Key={"scheduleId": schedule_id})

        if "Item" not in response:
            return None

        return response["Item"]

    def get_schedules_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all schedules for a user

        Args:
            user_id: User ID

        Returns:
            List[Dict]: List of schedules
        """
        response = self.table.query(
            IndexName="UserIdIndex", KeyConditionExpression=Key("userId").eq(user_id)
        )

        return response["Items"]

    def get_schedules_by_account(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Get all schedules for an AWS account

        Args:
            account_id: AWS account ID

        Returns:
            List[Dict]: List of schedules
        """
        response = self.table.query(
            IndexName="AccountIdIndex",
            KeyConditionExpression=Key("accountId").eq(account_id),
        )

        return response["Items"]

    def update_schedule(
        self, schedule_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update a schedule

        Args:
            schedule_id: Schedule ID
            updates: Dictionary of fields to update

        Returns:
            Optional[Dict]: Updated schedule object or None if not found
        """
        # First check if schedule exists
        if not self.get_schedule(schedule_id):
            return None

        # Build update expression
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        for key, value in updates.items():
            if key not in [
                "scheduleId",
                "userId",
                "createdAt",
            ]:  # Can't update these fields
                update_expression_parts.append(f"#{key} = :{key}")
                expression_attribute_values[f":{key}"] = value
                expression_attribute_names[f"#{key}"] = key

        if not update_expression_parts:
            return self.get_schedule(schedule_id)  # No updates to apply

        # Add updatedAt timestamp
        update_expression_parts.append("#updatedAt = :updatedAt")
        expression_attribute_values[":updatedAt"] = int(time.time())
        expression_attribute_names["#updatedAt"] = "updatedAt"

        # Create update expression
        update_expression = "SET " + ", ".join(update_expression_parts)

        # Update item
        response = self.table.update_item(
            Key={"scheduleId": schedule_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW",
        )

        return response.get("Attributes", {})

    def delete_schedule(self, schedule_id: str) -> bool:
        """
        Delete a schedule

        Args:
            schedule_id: Schedule ID

        Returns:
            bool: True if successful, False if schedule not found
        """
        # First check if schedule exists
        if not self.get_schedule(schedule_id):
            return False

        # Delete schedule
        self.table.delete_item(Key={"scheduleId": schedule_id})
        return True

    def list_schedules(
        self, limit: int = 100, last_evaluated_key: Dict = None
    ) -> Dict[str, Any]:
        """
        List all schedules with pagination

        Args:
            limit: Maximum number of items to return
            last_evaluated_key: Last evaluated key for pagination

        Returns:
            Dict: List of schedules and last evaluated key for pagination
        """
        params = {"Limit": limit}

        if last_evaluated_key:
            params["ExclusiveStartKey"] = last_evaluated_key

        response = self.table.scan(**params)

        return {
            "items": response.get("Items", []),
            "lastEvaluatedKey": response.get("LastEvaluatedKey"),
        }


class SavingsModel:
    """
    Class for Savings data model operations
    """

    def __init__(self, savings_table):
        """
        Initialize Savings model

        Args:
            savings_table: DynamoDB savings table reference
        """
        self.table = savings_table

    def record_savings(
        self,
        schedule_id: str,
        instance_id: str,
        instance_type: str,
        region: str,
        hours_saved: float,
        cost_saved: float,
        date: str,
    ) -> Dict[str, Any]:
        """
        Record savings for an instance

        Args:
            schedule_id: Schedule ID
            instance_id: EC2 instance ID
            instance_type: EC2 instance type
            region: AWS region
            hours_saved: Hours saved
            cost_saved: Cost saved (USD)
            date: Date in YYYY-MM-DD format

        Returns:
            Dict: Created savings record
        """
        # Generate unique ID for savings record
        savings_id = f"{instance_id}-{date}-{int(time.time())}"
        timestamp = int(time.time())

        # Create savings item
        # DynamoDB's boto3 resource API rejects native Python floats for
        # Number attributes outright ("Float types are not supported") -
        # str() first to avoid binary-float precision noise leaking into the
        # Decimal conversion (e.g. 0.1 -> Decimal("0.1000000000000000055...")).
        item = {
            "savingsId": savings_id,
            "scheduleId": schedule_id,
            "instanceId": instance_id,
            "instanceType": instance_type,
            "region": region,
            "hoursSaved": Decimal(str(hours_saved)),
            "costSaved": Decimal(str(cost_saved)),
            "date": date,
            "createdAt": timestamp,
        }

        # Save to DynamoDB
        self.table.put_item(Item=item)
        return item

    def get_savings_by_schedule(
        self,
        schedule_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all savings for a schedule with optional date filtering

        Args:
            schedule_id: Schedule ID
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)

        Returns:
            List[Dict]: List of savings records
        """
        # Query by schedule ID
        params = {
            "IndexName": "ScheduleIdIndex",
            "KeyConditionExpression": Key("scheduleId").eq(schedule_id),
        }

        # Add date filter if provided
        # "date" is a DynamoDB reserved keyword - a raw FilterExpression string
        # referencing it directly fails with a ValidationException, so it needs
        # an ExpressionAttributeNames placeholder like the rest of this file
        # already does (e.g. get_savings_summary below).
        filter_expressions = []
        expression_attribute_values = {}

        if start_date:
            filter_expressions.append("#date >= :start_date")
            expression_attribute_values[":start_date"] = start_date

        if end_date:
            filter_expressions.append("#date <= :end_date")
            expression_attribute_values[":end_date"] = end_date

        if filter_expressions:
            params["FilterExpression"] = " AND ".join(filter_expressions)
            params["ExpressionAttributeValues"] = expression_attribute_values
            params["ExpressionAttributeNames"] = {"#date": "date"}

        response = self.table.query(**params)
        return response["Items"]

    def get_savings_by_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Get all savings for a specific date

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            List[Dict]: List of savings records
        """
        response = self.table.query(
            IndexName="DateIndex", KeyConditionExpression=Key("date").eq(date)
        )

        return response["Items"]

    def get_savings_summary(
        self,
        user_id: Optional[str] = None,
        account_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get savings summary

        Args:
            user_id: Filter by user ID (optional)
            account_id: Filter by AWS account ID (optional)
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)

        Returns:
            Dict: Savings summary
        """
        # This would require a more complex query in a real implementation
        # For now, we'll use a scan with filters

        filter_expressions = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        if start_date:
            filter_expressions.append("#date >= :start_date")
            expression_attribute_values[":start_date"] = start_date
            expression_attribute_names["#date"] = "date"

        if end_date:
            filter_expressions.append("#date <= :end_date")
            expression_attribute_values[":end_date"] = end_date
            expression_attribute_names["#date"] = "date"

        params = {}

        if filter_expressions:
            params["FilterExpression"] = " AND ".join(filter_expressions)
            params["ExpressionAttributeValues"] = expression_attribute_values

            if expression_attribute_names:
                params["ExpressionAttributeNames"] = expression_attribute_names

        response = self.table.scan(**params)
        items = response["Items"]

        # Calculate summary
        total_hours_saved = sum(item.get("hoursSaved", 0) for item in items)
        total_cost_saved = sum(item.get("costSaved", 0) for item in items)
        instance_count = len(set(item.get("instanceId") for item in items))

        return {
            "totalHoursSaved": total_hours_saved,
            "totalCostSaved": total_cost_saved,
            "instanceCount": instance_count,
            "recordCount": len(items),
            "startDate": start_date,
            "endDate": end_date,
        }


class AuditLogModel:
    """
    Class for Audit Log data model operations
    """

    def __init__(self, audit_logs_table):
        """
        Initialize Audit Log model

        Args:
            audit_logs_table: DynamoDB audit logs table reference
        """
        self.table = audit_logs_table

    def record_action(
        self,
        action: str,
        trigger_type: str,
        triggered_by: str,
        instance_ids: List[str],
        account_id: str,
        schedule_id: Optional[str] = None,
        dry_run: bool = False,
        result: str = "success",
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record an EC2 start/stop action for audit purposes

        Args:
            action: "start" or "stop"
            trigger_type: "scheduled" or "manual"
            triggered_by: userId/email of the requester, or "system" for scheduled runs
            instance_ids: List of EC2 instance IDs affected
            account_id: AWS account ID
            schedule_id: Schedule ID, if the action originated from a schedule
            dry_run: Whether this was a dry-run (no real EC2 call made)
            result: "success", "failure", or "dry-run"
            error: Error message, if result is "failure"

        Returns:
            Dict: Created audit log record
        """
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
        audit_id = f"{schedule_id or account_id}-{action}-{timestamp}-{uuid.uuid4().hex[:8]}"

        item = {
            "auditId": audit_id,
            "action": action,
            "triggerType": trigger_type,
            "triggeredBy": triggered_by,
            "dryRun": dry_run,
            "result": result,
            "instanceIds": instance_ids,
            "accountId": account_id,
            "date": date,
            "timestamp": timestamp,
        }

        if schedule_id:
            item["scheduleId"] = schedule_id

        if error:
            item["error"] = error

        self.table.put_item(Item=item)
        return item

    def get_logs_by_schedule(
        self,
        schedule_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all audit logs for a schedule with optional date filtering

        Args:
            schedule_id: Schedule ID
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)

        Returns:
            List[Dict]: List of audit log records
        """
        params = {
            "IndexName": "ScheduleIdIndex",
            "KeyConditionExpression": Key("scheduleId").eq(schedule_id),
        }

        filter_expressions = []
        expression_attribute_values = {}

        if start_date:
            filter_expressions.append("#date >= :start_date")
            expression_attribute_values[":start_date"] = start_date

        if end_date:
            filter_expressions.append("#date <= :end_date")
            expression_attribute_values[":end_date"] = end_date

        if filter_expressions:
            params["FilterExpression"] = " AND ".join(filter_expressions)
            params["ExpressionAttributeValues"] = expression_attribute_values
            params["ExpressionAttributeNames"] = {"#date": "date"}

        response = self.table.query(**params)
        return response["Items"]

    def get_logs_by_account(
        self,
        account_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all audit logs for an AWS account with optional date filtering

        Args:
            account_id: AWS account ID
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)

        Returns:
            List[Dict]: List of audit log records
        """
        params = {
            "IndexName": "AccountIdIndex",
            "KeyConditionExpression": Key("accountId").eq(account_id),
        }

        filter_expressions = []
        expression_attribute_values = {}

        if start_date:
            filter_expressions.append("#date >= :start_date")
            expression_attribute_values[":start_date"] = start_date

        if end_date:
            filter_expressions.append("#date <= :end_date")
            expression_attribute_values[":end_date"] = end_date

        if filter_expressions:
            params["FilterExpression"] = " AND ".join(filter_expressions)
            params["ExpressionAttributeValues"] = expression_attribute_values
            params["ExpressionAttributeNames"] = {"#date": "date"}

        response = self.table.query(**params)
        return response["Items"]

    def get_logs_by_date_range(
        self, start_date: str, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all audit logs within a date range (queries each date individually
        since DateIndex is partitioned by exact date)

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (defaults to start_date)

        Returns:
            List[Dict]: List of audit log records
        """
        from datetime import timedelta

        end_date = end_date or start_date

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        items = []
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            response = self.table.query(
                IndexName="DateIndex", KeyConditionExpression=Key("date").eq(date_str)
            )
            items.extend(response["Items"])
            current = current + timedelta(days=1)

        return items


class ExceptionModel:
    """
    Class for Exception date data model operations
    """

    def __init__(self, exceptions_table):
        """
        Initialize Exception model

        Args:
            exceptions_table: DynamoDB exceptions table reference
        """
        self.table = exceptions_table

    def add_exception(
        self, schedule_id: str, date: str, description: str = None
    ) -> Dict[str, Any]:
        """
        Add an exception date to a schedule

        Args:
            schedule_id: Schedule ID
            date: Exception date in YYYY-MM-DD format
            description: Optional description (e.g., "Public Holiday")

        Returns:
            Dict: Created exception record
        """
        # Generate unique ID for exception
        exception_id = f"{schedule_id}-{date}"
        timestamp = int(time.time())

        # Create exception item
        item = {
            "exceptionId": exception_id,
            "scheduleId": schedule_id,
            "date": date,
            "createdAt": timestamp,
        }

        if description:
            item["description"] = description

        # Save to DynamoDB
        self.table.put_item(Item=item)
        return item

    def remove_exception(self, schedule_id: str, date: str) -> bool:
        """
        Remove an exception date from a schedule

        Args:
            schedule_id: Schedule ID
            date: Exception date in YYYY-MM-DD format

        Returns:
            bool: True if successful, False otherwise
        """
        exception_id = f"{schedule_id}-{date}"

        # Delete exception
        self.table.delete_item(Key={"exceptionId": exception_id})
        return True

    def get_exceptions_by_schedule(self, schedule_id: str) -> List[Dict[str, Any]]:
        """
        Get all exception dates for a schedule

        Args:
            schedule_id: Schedule ID

        Returns:
            List[Dict]: List of exception records
        """
        response = self.table.query(
            IndexName="ScheduleIdIndex",
            KeyConditionExpression=Key("scheduleId").eq(schedule_id),
        )

        return response["Items"]

    def get_exceptions_by_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Get all exceptions for a specific date

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            List[Dict]: List of exception records
        """
        response = self.table.query(
            IndexName="DateIndex", KeyConditionExpression=Key("date").eq(date)
        )

        return response["Items"]
