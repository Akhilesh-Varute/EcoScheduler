import time as time_module
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from common.ec2_connector import EC2Connector, classify_error

FAKE_CREDENTIALS = {
    "aws_access_key_id": "fake-key",
    "aws_secret_access_key": "fake-secret",
    "aws_session_token": "fake-token",
    "expiration": int(time_module.time()) + 3600,
}


def make_client_error(code, message="boom", operation="StartInstances"):
    return ClientError({"Error": {"Code": code, "Message": message}}, operation)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    # Don't actually sleep through the retry backoff in tests.
    monkeypatch.setattr("common.ec2_connector.time.sleep", lambda *_: None)


@pytest.fixture
def connector(monkeypatch):
    monkeypatch.setattr(
        "common.ec2_connector.assume_role", lambda **kwargs: dict(FAKE_CREDENTIALS)
    )
    with patch("common.ec2_connector.boto3.client") as mock_boto_client:
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        c = EC2Connector(account_id="111111111111", region="us-east-1")
        c.mock_ec2_client = mock_ec2
        yield c


class TestClassifyError:
    def test_permanent_codes(self):
        assert classify_error("AccessDenied") == "permanent"
        assert classify_error("UnauthorizedOperation") == "permanent"
        assert classify_error("InvalidInstanceID.NotFound") == "permanent"

    def test_transient_codes(self):
        assert classify_error("Throttling") == "transient"
        assert classify_error("RequestLimitExceeded") == "transient"
        assert classify_error("ServiceUnavailable") == "transient"

    def test_unknown_code_is_neither(self):
        assert classify_error("SomethingWeirdAndNew") == "unknown"


class TestStartInstances:
    def test_success_on_first_try(self, connector):
        connector.mock_ec2_client.start_instances.return_value = {
            "StartingInstances": [{"InstanceId": "i-abc"}]
        }
        result = connector.start_instances(["i-abc"])
        assert result["success"] is True
        assert result["startingInstances"] == [{"InstanceId": "i-abc"}]
        assert connector.mock_ec2_client.start_instances.call_count == 1

    def test_permanent_error_is_not_retried(self, connector):
        connector.mock_ec2_client.start_instances.side_effect = make_client_error(
            "AccessDenied"
        )
        result = connector.start_instances(["i-abc"])
        assert result["success"] is False
        assert result["errorCategory"] == "permanent"
        assert result["attempts"] == 1
        assert connector.mock_ec2_client.start_instances.call_count == 1

    def test_transient_error_is_retried_and_recovers(self, connector):
        connector.mock_ec2_client.start_instances.side_effect = [
            make_client_error("Throttling"),
            {"StartingInstances": [{"InstanceId": "i-abc"}]},
        ]
        result = connector.start_instances(["i-abc"])
        assert result["success"] is True
        assert connector.mock_ec2_client.start_instances.call_count == 2

    def test_transient_error_gives_up_after_max_attempts(self, connector):
        connector.mock_ec2_client.start_instances.side_effect = make_client_error(
            "Throttling"
        )
        result = connector.start_instances(["i-abc"])
        assert result["success"] is False
        assert result["errorCategory"] == "transient"
        assert result["attempts"] == 3
        assert connector.mock_ec2_client.start_instances.call_count == 3

    def test_unknown_error_is_not_retried(self, connector):
        connector.mock_ec2_client.start_instances.side_effect = make_client_error(
            "SomeNewErrorCodeWeHaveNeverSeen"
        )
        result = connector.start_instances(["i-abc"])
        assert result["success"] is False
        assert result["errorCategory"] == "unknown"
        assert result["attempts"] == 1


class TestStopInstances:
    def test_success(self, connector):
        connector.mock_ec2_client.stop_instances.return_value = {
            "StoppingInstances": [{"InstanceId": "i-abc"}]
        }
        result = connector.stop_instances(["i-abc"])
        assert result["success"] is True
        assert result["stoppingInstances"] == [{"InstanceId": "i-abc"}]

    def test_permanent_error_is_not_retried(self, connector):
        connector.mock_ec2_client.stop_instances.side_effect = make_client_error(
            "AccessDenied"
        )
        result = connector.stop_instances(["i-abc"])
        assert result["success"] is False
        assert result["errorCategory"] == "permanent"
        assert connector.mock_ec2_client.stop_instances.call_count == 1

    def test_transient_error_is_retried(self, connector):
        connector.mock_ec2_client.stop_instances.side_effect = [
            make_client_error("ServiceUnavailable"),
            {"StoppingInstances": [{"InstanceId": "i-abc"}]},
        ]
        result = connector.stop_instances(["i-abc"])
        assert result["success"] is True
        assert connector.mock_ec2_client.stop_instances.call_count == 2


class TestCredentialsFailure:
    def test_permanent_assume_role_failure_short_circuits(self, monkeypatch):
        def raise_access_denied(**kwargs):
            raise make_client_error("AccessDenied", operation="AssumeRole")

        monkeypatch.setattr("common.ec2_connector.assume_role", raise_access_denied)

        with patch("common.ec2_connector.boto3.client") as mock_boto_client:
            connector = EC2Connector(account_id="222222222222")
            result = connector.start_instances(["i-abc"])

        assert result["success"] is False
        assert result["errorCategory"] == "permanent"
        # We should never even reach boto3.client("ec2", ...) if we can't
        # get cross-account credentials in the first place.
        mock_boto_client.assert_not_called()

    def test_transient_assume_role_failure_retries_then_succeeds(self, monkeypatch):
        calls = {"n": 0}

        def flaky_assume_role(**kwargs):
            calls["n"] += 1
            if calls["n"] < 2:
                raise make_client_error("ThrottlingException", operation="AssumeRole")
            return dict(FAKE_CREDENTIALS)

        monkeypatch.setattr("common.ec2_connector.assume_role", flaky_assume_role)

        with patch("common.ec2_connector.boto3.client") as mock_boto_client:
            mock_ec2 = MagicMock()
            mock_boto_client.return_value = mock_ec2
            mock_ec2.start_instances.return_value = {"StartingInstances": []}

            connector = EC2Connector(account_id="333333333333")
            result = connector.start_instances(["i-abc"])

        assert result["success"] is True
        assert calls["n"] == 2
