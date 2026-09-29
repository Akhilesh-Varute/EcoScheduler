"""
Tests for the consecutive-failure tracking / auto-disable behavior in the
EventBridge-triggered (handle_schedule_event) path of the EC2 start/stop
Lambda handlers. See ec2_connector.py's classify_error() for how a result's
"errorCategory" is decided; these tests cover what start.py/stop.py then do
with it.
"""

from unittest.mock import MagicMock

import functions.ec2.start as start_module
import functions.ec2.stop as stop_module


def _make_common_mocks(monkeypatch, module, schedule, ec2_result):
    """
    Patch DynamoDBTables/ScheduleModel/AuditLogModel/SchedulerManager/EC2Connector
    inside `module` (functions.ec2.start or functions.ec2.stop) so
    handle_schedule_event runs without touching real AWS/DynamoDB. Returns the
    mock ScheduleModel and AuditLogModel instances so tests can assert on them.
    """
    mock_tables = MagicMock()
    mock_tables.get_tables.return_value = {"schedules": object(), "auditLogs": object(), "savings": object()}
    monkeypatch.setattr(module, "DynamoDBTables", MagicMock(return_value=mock_tables))

    mock_schedule_model = MagicMock()
    mock_schedule_model.get_schedule.return_value = schedule
    monkeypatch.setattr(module, "ScheduleModel", MagicMock(return_value=mock_schedule_model))

    mock_audit_model = MagicMock()
    monkeypatch.setattr(module, "AuditLogModel", MagicMock(return_value=mock_audit_model))

    mock_scheduler = MagicMock()
    mock_scheduler.is_exception_date.return_value = False
    monkeypatch.setattr(module, "SchedulerManager", MagicMock(return_value=mock_scheduler))

    mock_ec2 = MagicMock()
    if module is start_module:
        mock_ec2.start_instances.return_value = ec2_result
    else:
        mock_ec2.stop_instances.return_value = ec2_result
        mock_ec2.describe_instances.return_value = {"success": True, "instances": []}
    monkeypatch.setattr(module, "EC2Connector", MagicMock(return_value=mock_ec2))

    if hasattr(module, "SavingsModel"):
        monkeypatch.setattr(module, "SavingsModel", MagicMock(return_value=MagicMock()))

    return mock_schedule_model, mock_audit_model


BASE_SCHEDULE = {
    "scheduleId": "sched-1",
    "enabled": True,
    "dryRun": False,
    "consecutiveFailures": 0,
}

BASE_EVENT = {
    "scheduleId": "sched-1",
    "accountId": "111111111111",
    "instanceIds": ["i-abc"],
}


class TestStartScheduleEventSuccessResetsCounter:
    def test_success_resets_consecutive_failures_to_zero(self, monkeypatch):
        schedule = dict(BASE_SCHEDULE, consecutiveFailures=2)
        schedule_model, audit_model = _make_common_mocks(
            monkeypatch,
            start_module,
            schedule,
            {"success": True, "message": "Started 1 instances", "startingInstances": []},
        )

        result = start_module.handle_schedule_event(dict(BASE_EVENT), None)

        assert result["success"] is True
        update_args = schedule_model.update_schedule.call_args
        assert update_args[0][1]["consecutiveFailures"] == 0


class TestStartScheduleEventPermanentFailureDisablesImmediately:
    def test_permanent_failure_disables_on_first_occurrence(self, monkeypatch):
        schedule = dict(BASE_SCHEDULE, consecutiveFailures=0)
        schedule_model, audit_model = _make_common_mocks(
            monkeypatch,
            start_module,
            schedule,
            {
                "success": False,
                "message": "Error starting instances: not authorized",
                "error": "AccessDenied",
                "errorCategory": "permanent",
                "attempts": 1,
            },
        )

        result = start_module.handle_schedule_event(dict(BASE_EVENT), None)

        assert result["success"] is False
        assert result["scheduleDisabled"] is True
        assert result["consecutiveFailures"] == 1

        update_args = schedule_model.update_schedule.call_args[0][1]
        assert update_args["enabled"] is False
        assert "disabledReason" in update_args
        assert update_args["consecutiveFailures"] == 1

        # A distinct audit entry should record the auto-disable, in addition
        # to the ordinary failure entry.
        actions = [c.kwargs.get("action") for c in audit_model.record_action.call_args_list]
        assert "start" in actions
        assert "schedule_auto_disabled" in actions


class TestStartScheduleEventTransientFailureBelowThreshold:
    def test_transient_failure_does_not_disable_below_threshold(self, monkeypatch):
        schedule = dict(BASE_SCHEDULE, consecutiveFailures=1)
        schedule_model, audit_model = _make_common_mocks(
            monkeypatch,
            start_module,
            schedule,
            {
                "success": False,
                "message": "Error starting instances: throttled",
                "error": "Throttling",
                "errorCategory": "transient",
                "attempts": 3,
            },
        )

        result = start_module.handle_schedule_event(dict(BASE_EVENT), None)

        assert result["success"] is False
        assert result["scheduleDisabled"] is False
        assert result["consecutiveFailures"] == 2

        update_args = schedule_model.update_schedule.call_args[0][1]
        assert "enabled" not in update_args

        actions = [c.kwargs.get("action") for c in audit_model.record_action.call_args_list]
        assert "schedule_auto_disabled" not in actions


class TestStartScheduleEventTransientFailureAtThreshold:
    def test_transient_failure_disables_once_threshold_reached(self, monkeypatch):
        # 4 prior consecutive failures + this one = 5, the threshold.
        schedule = dict(BASE_SCHEDULE, consecutiveFailures=4)
        schedule_model, audit_model = _make_common_mocks(
            monkeypatch,
            start_module,
            schedule,
            {
                "success": False,
                "message": "Error starting instances: throttled",
                "error": "Throttling",
                "errorCategory": "transient",
                "attempts": 3,
            },
        )

        result = start_module.handle_schedule_event(dict(BASE_EVENT), None)

        assert result["scheduleDisabled"] is True
        assert result["consecutiveFailures"] == 5

        update_args = schedule_model.update_schedule.call_args[0][1]
        assert update_args["enabled"] is False


class TestStopScheduleEventMirrorsStart:
    def test_permanent_failure_disables_immediately(self, monkeypatch):
        schedule = dict(BASE_SCHEDULE, consecutiveFailures=0)
        schedule_model, audit_model = _make_common_mocks(
            monkeypatch,
            stop_module,
            schedule,
            {
                "success": False,
                "message": "Error stopping instances: not authorized",
                "error": "AccessDenied",
                "errorCategory": "permanent",
                "attempts": 1,
            },
        )

        result = stop_module.handle_schedule_event(dict(BASE_EVENT), None)

        assert result["scheduleDisabled"] is True
        update_args = schedule_model.update_schedule.call_args[0][1]
        assert update_args["enabled"] is False

    def test_success_resets_consecutive_failures(self, monkeypatch):
        schedule = dict(BASE_SCHEDULE, consecutiveFailures=3)
        schedule_model, audit_model = _make_common_mocks(
            monkeypatch,
            stop_module,
            schedule,
            {"success": True, "message": "Stopped 1 instances", "stoppingInstances": []},
        )

        result = stop_module.handle_schedule_event(dict(BASE_EVENT), None)

        assert result["success"] is True
        update_args = schedule_model.update_schedule.call_args_list[0][0][1]
        assert update_args["consecutiveFailures"] == 0
