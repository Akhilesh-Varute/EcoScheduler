import re

from common.db_models import PBKDF2_ITERATIONS, hash_password, verify_password


class TestHashPassword:
    def test_format_is_self_describing(self):
        hashed = hash_password("correct horse battery staple")
        parts = hashed.split("$")
        assert len(parts) == 4
        algorithm, iterations, salt, digest = parts
        assert algorithm == "pbkdf2_sha256"
        assert int(iterations) == PBKDF2_ITERATIONS
        assert re.fullmatch(r"[0-9a-f]{32}", salt)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)

    def test_same_password_hashed_twice_has_different_salt(self):
        first = hash_password("same-password")
        second = hash_password("same-password")
        assert first != second


class TestVerifyPassword:
    def test_correct_password_verifies(self):
        hashed = hash_password("s3cr3t!")
        assert verify_password("s3cr3t!", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("s3cr3t!")
        assert verify_password("wrong-password", hashed) is False

    def test_empty_password_against_real_hash_fails(self):
        hashed = hash_password("s3cr3t!")
        assert verify_password("", hashed) is False

    def test_tampered_hash_fails(self):
        hashed = hash_password("s3cr3t!")
        algorithm, iterations, salt, digest = hashed.split("$")
        tampered_digest = ("0" if digest[0] != "0" else "1") + digest[1:]
        tampered = f"{algorithm}${iterations}${salt}${tampered_digest}"
        assert verify_password("s3cr3t!", tampered) is False

    def test_unknown_algorithm_prefix_rejected(self):
        assert verify_password("anything", "bcrypt$10$salt$hash") is False

    def test_malformed_stored_value_returns_false_not_exception(self):
        assert verify_password("anything", "not-a-valid-stored-hash") is False
        assert verify_password("anything", "") is False
