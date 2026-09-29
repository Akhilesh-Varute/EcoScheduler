import time

import jwt
import pytest

from common.auth import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    ROLES,
    decode_token,
    generate_token,
    get_current_user,
    get_token_from_header,
    has_permission,
    require_permission,
)


class TestRoles:
    def test_admin_can_start_and_stop_instances(self):
        assert "start_instances" in ROLES["admin"]["permissions"]
        assert "stop_instances" in ROLES["admin"]["permissions"]

    def test_developer_can_start_and_stop_instances(self):
        assert "start_instances" in ROLES["developer"]["permissions"]
        assert "stop_instances" in ROLES["developer"]["permissions"]

    def test_finance_cannot_start_or_stop_instances(self):
        assert "start_instances" not in ROLES["finance"]["permissions"]
        assert "stop_instances" not in ROLES["finance"]["permissions"]

    def test_finance_cannot_manage_users_schedules_or_accounts(self):
        finance_perms = ROLES["finance"]["permissions"]
        assert "manage_users" not in finance_perms
        assert "create_schedule" not in finance_perms
        assert "manage_accounts" not in finance_perms

    def test_developer_cannot_manage_users_or_accounts(self):
        developer_perms = ROLES["developer"]["permissions"]
        assert "manage_users" not in developer_perms
        assert "manage_accounts" not in developer_perms

    def test_only_admin_can_manage_users_and_accounts(self):
        assert "manage_users" in ROLES["admin"]["permissions"]
        assert "manage_accounts" in ROLES["admin"]["permissions"]
        for role in ("developer", "finance"):
            assert "manage_users" not in ROLES[role]["permissions"]
            assert "manage_accounts" not in ROLES[role]["permissions"]


class TestGenerateAndDecodeToken:
    def test_round_trip_preserves_claims(self):
        token = generate_token("user-1", "a@example.com", "admin", ["111111111111"])
        claims = decode_token(token)
        assert claims["sub"] == "user-1"
        assert claims["email"] == "a@example.com"
        assert claims["role"] == "admin"
        assert claims["aws_accounts"] == ["111111111111"]
        assert claims["permissions"] == ROLES["admin"]["permissions"]

    def test_invalid_role_falls_back_to_developer(self):
        token = generate_token("user-2", "b@example.com", "superuser", [])
        claims = decode_token(token)
        assert claims["role"] == "developer"
        assert claims["permissions"] == ROLES["developer"]["permissions"]

    def test_decode_rejects_tampered_signature(self):
        token = generate_token("user-3", "c@example.com", "finance", [])
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(tampered)

    def test_decode_rejects_expired_token(self):
        payload = {
            "sub": "user-4",
            "email": "d@example.com",
            "role": "admin",
            "permissions": ROLES["admin"]["permissions"],
            "aws_accounts": [],
            "iat": int(time.time()) - 100,
            "exp": int(time.time()) - 1,
        }
        expired = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Token has expired"):
            decode_token(expired)

    def test_decode_rejects_token_signed_with_wrong_secret(self):
        payload = {
            "sub": "user-5",
            "email": "e@example.com",
            "role": "admin",
            "permissions": ROLES["admin"]["permissions"],
            "aws_accounts": [],
            "iat": int(time.time()),
            "exp": int(time.time()) + 1000,
        }
        forged = jwt.encode(payload, "not-the-real-secret", algorithm=JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(forged)


class TestHasPermission:
    def test_true_when_permission_present(self):
        claims = {"permissions": ["view_savings", "export_reports"]}
        assert has_permission(claims, "view_savings") is True

    def test_false_when_permission_absent(self):
        claims = {"permissions": ["view_savings"]}
        assert has_permission(claims, "manage_users") is False

    def test_false_when_no_permissions_key(self):
        assert has_permission({}, "view_savings") is False


class TestGetTokenFromHeader:
    def test_extracts_bearer_token(self):
        event = {"headers": {"Authorization": "Bearer abc.def.ghi"}}
        assert get_token_from_header(event) == "abc.def.ghi"

    def test_returns_none_without_bearer_prefix(self):
        event = {"headers": {"Authorization": "abc.def.ghi"}}
        assert get_token_from_header(event) is None

    def test_returns_none_when_no_headers(self):
        assert get_token_from_header({}) is None

    def test_returns_none_when_headers_is_none(self):
        assert get_token_from_header({"headers": None}) is None


class TestGetCurrentUser:
    def test_reads_from_authorizer_context_first(self):
        event = {
            "requestContext": {
                "authorizer": {
                    "userId": "u1",
                    "email": "a@example.com",
                    "role": "admin",
                    "permissions": '["manage_users"]',
                    "awsAccounts": '["111111111111"]',
                }
            }
        }
        user = get_current_user(event)
        assert user["userId"] == "u1"
        assert user["permissions"] == ["manage_users"]
        assert user["awsAccounts"] == ["111111111111"]

    def test_falls_back_to_decoding_bearer_token(self):
        token = generate_token("u2", "b@example.com", "finance", [])
        event = {"headers": {"Authorization": f"Bearer {token}"}}
        user = get_current_user(event)
        assert user["userId"] == "u2"
        assert user["role"] == "finance"

    def test_returns_none_when_nothing_present(self):
        assert get_current_user({}) is None

    def test_returns_none_for_invalid_token(self):
        event = {"headers": {"Authorization": "Bearer not-a-real-token"}}
        assert get_current_user(event) is None


class TestRequirePermissionDecorator:
    def test_calls_wrapped_function_when_permission_present(self):
        @require_permission("view_savings")
        def handler(event, context):
            return {"statusCode": 200, "body": "ok"}

        token = generate_token("u3", "c@example.com", "finance", [])
        event = {"headers": {"Authorization": f"Bearer {token}"}}
        result = handler(event, None)
        assert result == {"statusCode": 200, "body": "ok"}

    def test_returns_403_when_permission_missing(self):
        @require_permission("manage_users")
        def handler(event, context):
            return {"statusCode": 200, "body": "ok"}

        token = generate_token("u4", "d@example.com", "finance", [])
        event = {"headers": {"Authorization": f"Bearer {token}"}}
        result = handler(event, None)
        assert result["statusCode"] == 403

    def test_returns_401_when_unauthenticated(self):
        @require_permission("view_savings")
        def handler(event, context):
            return {"statusCode": 200, "body": "ok"}

        result = handler({}, None)
        assert result["statusCode"] == 401
