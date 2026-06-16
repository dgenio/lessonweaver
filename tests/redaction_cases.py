"""Shared redaction fixtures for export and trace sanitization tests."""

from __future__ import annotations

import pytest

PRIVATE_KEY_BLOCK = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIBOgIBAAJBAKj34GkxFhD90vcNLYL\n"
    "q9p2x6Z3\n"
    "-----END RSA PRIVATE KEY-----"
)

SENSITIVE_CASES = [
    ("email", "Email admin@example.com", "Email [REDACTED by email]"),
    (
        "bearer token",
        "Auth Bearer abcdefghijklmnopqrstuvwxyz123456",
        "Auth [REDACTED by bearer_token]",
    ),
    ("api key", "api_key: sk-abc123", "[REDACTED by api_key]"),
    (
        "composed assignment marker",
        "api_key: admin@example.com",
        "api_key: [REDACTED by email]",
    ),
    ("aws key", "AKIAABCDEFGHIJKLMNOP", "[REDACTED by aws_access_key_id]"),
    (
        "jwt",
        "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        "jwt [REDACTED by jwt]",
    ),
    ("generic token", "token = super-secret-value", "[REDACTED by generic_token_assignment]"),
    ("private key", f"key:\n{PRIVATE_KEY_BLOCK}\nok", "key:\n[REDACTED by private_key]\nok"),
]

SAFE_CASES = [
    "No sensitive pattern here.",
    "Token budget is a planning term, not a secret.",
    "Contact the admin team without embedding an address.",
]


SENSITIVE_CASES_PARAM = pytest.mark.parametrize(
    ("_case_name", "raw", "expected"),
    SENSITIVE_CASES,
    ids=[case[0] for case in SENSITIVE_CASES],
)
