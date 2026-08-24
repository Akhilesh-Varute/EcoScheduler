import boto3
import json
import time
import datetime
from typing import Dict, List, Any, Optional, Tuple
from dateutil import parser, tz
from croniter import croniter
import os

from .utils import create_eventbridge_rule, delete_eventbridge_rule


class SchedulerManager:
    """
    Class for managing EventBridge schedules for EC2 instances
    """

    def __init__(self):
        """
        Initialize the scheduler manager
        """
        # Get region from environment variable or default to us-east-1
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.event_bus_name = os.environ.get("EVENT_BUS_NAME", "default")

        # Get Lambda function names from environment
        self.ec2_start_lambda_name = os.environ.get("EC2_START_LAMBDA_NAME", "")
        self.ec2_stop_lambda_name = os.environ.get("EC2_STOP_LAMBDA_NAME", "")

        # Account ID is needed to construct the ARN
        self.account_id = boto3.client("sts").get_caller_identity().get("Account")

        # Construct Lambda ARNs
        self.ec2_start_lambda_arn = f"arn:aws:lambda:{self.region}:{self.account_id}:function:{self.ec2_start_lambda_name}"
        self.ec2_stop_lambda_arn = f"arn:aws:lambda:{self.region}:{self.account_id}:function:{self.ec2_stop_lambda_name}"

        # Initialize EventBridge client
        self.events_client = boto3.client("events", region_name=self.region)

    def create_schedule_rules(self, schedule: Dict[str, Any]) -> Dict[str, str]:
        """
        Create EventBridge rules for a schedule

        Args:
            schedule: Schedule object with ID, cron expressions, etc.

        Returns:
            Dict: Dictionary of created rule ARNs
        """
        schedule_id = schedule["scheduleId"]
        account_id = schedule["accountId"]
        instance_ids = schedule["instanceIds"]
        start_cron = schedule["startCron"]
        stop_cron = schedule["stopCron"]
        timezone = schedule.get("timezone", "UTC")

        rules = {}

        # Create start rule
        start_rule_name = f"EcoScheduler-Start-{schedule_id}"
        start_input = {
            "action": "start",
            "scheduleId": schedule_id,
            "accountId": account_id,
            "instanceIds": instance_ids,
            "timezone": timezone,
        }

        # Convert cron to UTC if needed
        if timezone != "UTC":
            start_cron = self._convert_cron_to_utc(start_cron, timezone)

        # Create EventBridge rule for start
        start_rule_arn = create_eventbridge_rule(
            name=start_rule_name,
            schedule_expression=f"cron({self._to_eventbridge_cron(start_cron)})",
            target_arn=self.ec2_start_lambda_arn,
            input_json=start_input,
        )

        rules["startRule"] = start_rule_arn

        # Create stop rule
        stop_rule_name = f"EcoScheduler-Stop-{schedule_id}"
        stop_input = {
            "action": "stop",
            "scheduleId": schedule_id,
            "accountId": account_id,
            "instanceIds": instance_ids,
            "timezone": timezone,
        }

        # Convert cron to UTC if needed
        if timezone != "UTC":
            stop_cron = self._convert_cron_to_utc(stop_cron, timezone)

        # Create EventBridge rule for stop
        stop_rule_arn = create_eventbridge_rule(
            name=stop_rule_name,
            schedule_expression=f"cron({self._to_eventbridge_cron(stop_cron)})",
            target_arn=self.ec2_stop_lambda_arn,
            input_json=stop_input,
        )

        rules["stopRule"] = stop_rule_arn

        return rules

    def update_schedule_rules(self, schedule: Dict[str, Any]) -> Dict[str, str]:
        """
        Update EventBridge rules for a schedule

        Args:
            schedule: Schedule object with updated values

        Returns:
            Dict: Dictionary of updated rule ARNs
        """
        # First, delete existing rules
        self.delete_schedule_rules(schedule["scheduleId"])

        # Then create new rules
        return self.create_schedule_rules(schedule)

    def delete_schedule_rules(self, schedule_id: str) -> bool:
        """
        Delete EventBridge rules for a schedule

        Args:
            schedule_id: Schedule ID

        Returns:
            bool: True if successful, False otherwise
        """
        start_rule_name = f"EcoScheduler-Start-{schedule_id}"
        stop_rule_name = f"EcoScheduler-Stop-{schedule_id}"

        try:
            # Delete start rule
            delete_eventbridge_rule(start_rule_name)

            # Delete stop rule
            delete_eventbridge_rule(stop_rule_name)

            return True
        except Exception as e:
            print(
                f"Error deleting EventBridge rules for schedule {schedule_id}: {str(e)}"
            )
            return False

    def enable_schedule_rules(self, schedule_id: str) -> bool:
        """
        Enable EventBridge rules for a schedule

        Args:
            schedule_id: Schedule ID

        Returns:
            bool: True if successful, False otherwise
        """
        start_rule_name = f"EcoScheduler-Start-{schedule_id}"
        stop_rule_name = f"EcoScheduler-Stop-{schedule_id}"

        try:
            # Enable start rule
            self.events_client.enable_rule(Name=start_rule_name)

            # Enable stop rule
            self.events_client.enable_rule(Name=stop_rule_name)

            return True
        except Exception as e:
            print(
                f"Error enabling EventBridge rules for schedule {schedule_id}: {str(e)}"
            )
            return False

    def disable_schedule_rules(self, schedule_id: str) -> bool:
        """
        Disable EventBridge rules for a schedule

        Args:
            schedule_id: Schedule ID

        Returns:
            bool: True if successful, False otherwise
        """
        start_rule_name = f"EcoScheduler-Start-{schedule_id}"
        stop_rule_name = f"EcoScheduler-Stop-{schedule_id}"

        try:
            # Disable start rule
            self.events_client.disable_rule(Name=start_rule_name)

            # Disable stop rule
            self.events_client.disable_rule(Name=stop_rule_name)

            return True
        except Exception as e:
            print(
                f"Error disabling EventBridge rules for schedule {schedule_id}: {str(e)}"
            )
            return False

    def list_schedule_rules(self, schedule_id: str = None) -> List[Dict[str, Any]]:
        """
        List EventBridge rules for a schedule or all EcoScheduler rules

        Args:
            schedule_id: Schedule ID (optional)

        Returns:
            List[Dict]: List of rule details
        """
        prefix = f"EcoScheduler-{schedule_id}" if schedule_id else "EcoScheduler"

        try:
            response = self.events_client.list_rules(NamePrefix=prefix)

            return response.get("Rules", [])
        except Exception as e:
            print(f"Error listing EventBridge rules: {str(e)}")
            return []

    def get_next_run_times(
        self, schedule: Dict[str, Any]
    ) -> Dict[str, datetime.datetime]:
        """
        Get the next run times for a schedule

        Args:
            schedule: Schedule object

        Returns:
            Dict: Dictionary with next start and stop times
        """
        start_cron = schedule["startCron"]
        stop_cron = schedule["stopCron"]
        timezone = schedule.get("timezone", "UTC")

        # Get current time in the schedule's timezone
        now = datetime.datetime.now(tz=tz.gettz(timezone))

        # Calculate next start time
        start_iter = croniter(start_cron, now)
        next_start = start_iter.get_next(datetime.datetime)

        # Calculate next stop time
        stop_iter = croniter(stop_cron, now)
        next_stop = stop_iter.get_next(datetime.datetime)

        return {"nextStart": next_start, "nextStop": next_stop}

    def _to_eventbridge_cron(self, cron_expression: str) -> str:
        """
        Convert a standard 5-field cron expression (minute hour day-of-month
        month day-of-week) into AWS EventBridge's cron() syntax, which requires
        exactly 6 fields (with a trailing year) and exactly one of
        day-of-month/day-of-week set to "?" rather than both being "*".
        Passing a raw 5-field expression straight to EventBridge's PutRule
        fails outright with a ValidationException.

        Args:
            cron_expression: Standard 5-field cron expression

        Returns:
            str: 6-field EventBridge-compatible cron expression
        """
        parts = cron_expression.split(" ")
        if len(parts) != 5:
            # Not a standard 5-field expression - let EventBridge validate/reject it
            return cron_expression

        minute, hour, day_of_month, month, day_of_week = parts

        # Standard unix cron numbers day-of-week 0=Sunday..6=Saturday (what
        # croniter/validate_cron_expression validate against, and what the
        # rest of this codebase assumes - e.g. the common "1-5" for weekdays).
        # AWS EventBridge's cron() numbers it 1=Sunday..7=Saturday instead.
        # Passing numeric values through unconverted silently shifts every
        # recurring schedule by one day (e.g. "1-5" meant Mon-Fri but becomes
        # Sun-Thu on the real rule) - remap before substituting "?"/"*".
        day_of_week = self._remap_dow_to_eventbridge(day_of_week)

        if day_of_month == "*" and day_of_week == "*":
            day_of_week = "?"
        elif day_of_month != "*" and day_of_week == "*":
            day_of_week = "?"
        elif day_of_month == "*" and day_of_week != "*":
            day_of_month = "?"
        # If both are already specific (non-"*") values, leave as-is -
        # EventBridge will (correctly) reject that as ambiguous.

        return f"{minute} {hour} {day_of_month} {month} {day_of_week} *"

    @staticmethod
    def _remap_dow_to_eventbridge(day_of_week: str) -> str:
        """
        Remap a unix-style day-of-week field (0=Sunday..6=Saturday, single
        value/comma list/range) to AWS EventBridge's numbering
        (1=Sunday..7=Saturday). Non-numeric tokens (names like "MON-FRI",
        "*") are left unchanged - AWS accepts day names directly with no
        reordering needed.

        Args:
            day_of_week: The cron expression's day-of-week field

        Returns:
            str: The same field, numeric values remapped to AWS numbering
        """

        def remap_token(token: str) -> str:
            if "-" in token:
                start, end = token.split("-", 1)
                if start.isdigit() and end.isdigit():
                    return f"{(int(start) % 7) + 1}-{(int(end) % 7) + 1}"
                return token
            if token.isdigit():
                return str((int(token) % 7) + 1)
            return token

        if "," in day_of_week:
            return ",".join(remap_token(t) for t in day_of_week.split(","))
        return remap_token(day_of_week)

    def _convert_cron_to_utc(self, cron_expression: str, source_timezone: str) -> str:
        """
        Convert a cron expression from a source timezone to UTC

        Args:
            cron_expression: Cron expression to convert
            source_timezone: Source timezone

        Returns:
            str: Cron expression in UTC

        Note:
            Handles the common case (a single literal minute + hour, e.g.
            "30 19 * * 1-5") with full minute-granularity precision - this
            matters for half-hour/45-minute offset zones like India (UTC+5:30)
            or Nepal (UTC+5:45), which a naive integer-hour shift gets wrong.
            Hour ranges/lists ("9-17", "9,13,17") fall back to a simplified
            whole-hour shift, same as before. Does not account for DST
            transitions in either case.
        """
        # Parse cron expression
        parts = cron_expression.split(" ")
        if len(parts) != 5:
            # Invalid cron, return as is
            return cron_expression

        minute, hour, day_of_month, month, day_of_week = parts

        # Get timezone offset
        source_tz = tz.gettz(source_timezone)
        utc_tz = tz.gettz("UTC")

        # Calculate offset in hours
        now = datetime.datetime.now(source_tz)
        offset_seconds = source_tz.utcoffset(now).total_seconds()
        offset_hours = int(offset_seconds / 3600)

        # Adjust hour
        if hour == "*":
            # Can't adjust wildcards
            return cron_expression

        # Precise path: a single literal minute + hour (the common case) gets
        # a full minute-granularity offset instead of a truncated whole-hour
        # shift, so half-hour/45-minute offset zones convert correctly.
        if (
            minute.isdigit()
            and hour.isdigit()
            and "," not in minute
            and "-" not in minute
        ):
            total_minutes = int(hour) * 60 + int(minute)
            offset_minutes = int(offset_seconds / 60)
            new_total_minutes = (total_minutes - offset_minutes) % (24 * 60)
            new_hour, new_minute = divmod(new_total_minutes, 60)
            return f"{new_minute} {new_hour} {day_of_month} {month} {day_of_week}"

        # Check if hour contains multiple values
        if "," in hour:
            # Handle comma-separated hours
            hour_parts = hour.split(",")
            new_hours = []

            for h in hour_parts:
                if "-" in h:
                    # Handle ranges
                    start, end = map(int, h.split("-"))
                    new_start = (start - offset_hours) % 24
                    new_end = (end - offset_hours) % 24

                    # Handle case where range crosses midnight
                    if new_start > new_end:
                        # Split into two ranges
                        new_hours.append(f"{new_start}-23")
                        new_hours.append(f"0-{new_end}")
                    else:
                        new_hours.append(f"{new_start}-{new_end}")
                else:
                    # Single hour
                    new_hour = (int(h) - offset_hours) % 24
                    new_hours.append(str(new_hour))

            hour = ",".join(new_hours)
        elif "-" in hour:
            # Handle range
            start, end = map(int, hour.split("-"))
            new_start = (start - offset_hours) % 24
            new_end = (end - offset_hours) % 24

            # Handle case where range crosses midnight
            if new_start > new_end:
                # Split into two ranges
                hour = f"{new_start}-23,0-{new_end}"
            else:
                hour = f"{new_start}-{new_end}"
        else:
            # Single hour
            hour = str((int(hour) - offset_hours) % 24)

        # Reconstruct cron expression
        return f"{minute} {hour} {day_of_month} {month} {day_of_week}"

    def is_exception_date(
        self, schedule: Dict[str, Any], date: datetime.date = None
    ) -> bool:
        """
        Check if a date is an exception for a schedule

        Args:
            schedule: Schedule object
            date: Date to check (defaults to today)

        Returns:
            bool: True if date is an exception, False otherwise
        """
        if date is None:
            # Default to today
            date = datetime.date.today()

        # Convert date to string in YYYY-MM-DD format
        date_str = date.strftime("%Y-%m-%d")

        # Check exceptions list
        exceptions = schedule.get("exceptions", [])
        return date_str in exceptions
