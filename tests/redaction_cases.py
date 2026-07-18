"""Shared redaction fixtures for export and trace sanitization tests."""

from __future__ import annotations

import pytest

from lessonweaver.sanitization import redaction_marker

PRIVATE_KEY_BLOCK = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIBOgIBAAJBAKj34GkxFhD90vcNLYL\n"
    "q9p2x6Z3\n"
    "-----END RSA PRIVATE KEY-----"
)

SENSITIVE_CASES = [
    ("email", "Email admin@example.com", f"Email {redaction_marker('email')}"),
    (
        "bearer token",
        "Auth Bearer abcdefghijklmnopqrstuvwxyz123456",
        f"Auth {redaction_marker('bearer_token')}",
    ),
    ("api key", "api_key: sk-abc123", redaction_marker("api_key")),
    (
        "composed assignment marker",
        "api_key: admin@example.com",
        f"api_key: {redaction_marker('email')}",
    ),
    ("aws key", "AKIAABCDEFGHIJKLMNOP", redaction_marker("aws_access_key_id")),
    (
        "jwt",
        "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        f"jwt {redaction_marker('jwt')}",
    ),
    ("generic token", "token = super-secret-value", redaction_marker("generic_token_assignment")),
    (
        "private key",
        f"key:\n{PRIVATE_KEY_BLOCK}\nok",
        f"key:\n{redaction_marker('private_key')}\nok",
    ),
]

SAFE_CASES = [
    "No sensitive pattern here.",
    "Token budget is a planning term, not a secret.",
    "secret: it was the butler in the library.",
    "token: budget is a planning term, not a credential.",
    "Contact the admin team without embedding an address.",
]


SENSITIVE_CASES_PARAM = pytest.mark.parametrize(
    ("case_name", "raw", "expected"),
    SENSITIVE_CASES,
    ids=[case[0] for case in SENSITIVE_CASES],
)
