"""Tests for the pre-mining trace sanitizer (#46)."""

from __future__ import annotations

from lessonweaver.models import TraceBundle, TraceEvent, TraceEventType
from lessonweaver.sanitization import SanitizationRule, TraceSanitizer


def _bundle(content: str | None) -> TraceBundle:
    return TraceBundle(
        trace_id="t1",
        source="unit-test",
        task="x",
        events=[TraceEvent(id="e1", type=TraceEventType.USER_MESSAGE, content=content)],
        outcome="success",
    )


def test_default_rules_redact_email_bearer_and_key() -> None:
    text = (
        "Contact a.user@example.com with Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ "
        "and key -----BEGIN RSA PRIVATE KEY-----"
    )
    out = TraceSanitizer().sanitize(_bundle(text)).events[0].content
    assert out == (
        "Contact [REDACTED by email] with [REDACTED by bearer_token] "
        "and key [REDACTED by private_key]"
    )


def test_private_key_redacts_full_block() -> None:
    text = (
        "key:\n-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIBOgIBAAJBAKj34GkxFhD90vcNLYL\nq9p2x6Z3\n"
        "-----END RSA PRIVATE KEY-----\nok"
    )
    out = TraceSanitizer().sanitize(_bundle(text)).events[0].content
    assert out == "key:\n[REDACTED by private_key]\nok"


def test_default_rules_redact_aws_access_key_ids() -> None:
    text = "aws_access_key_id=AKIAIOSFODNN7EXAMPLE"
    out = TraceSanitizer().sanitize(_bundle(text)).events[0].content
    assert out == "aws_access_key_id=[REDACTED by aws_access_key_id]"


def test_default_rules_redact_aws_secret_access_keys() -> None:
    text = "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    out = TraceSanitizer().sanitize(_bundle(text)).events[0].content
    assert out == "aws_secret_access_key=[REDACTED by aws_secret_access_key]"


def test_default_rules_redact_generic_key_value_secrets() -> None:
    text = "api_key=sk_live_1234567890abcdef token: ghp_1234567890abcdef password='hunter2'"
    out = TraceSanitizer().sanitize(_bundle(text)).events[0].content
    assert out == (
        "api_key=[REDACTED by generic_secret] token: [REDACTED by generic_secret] "
        "password=[REDACTED by generic_secret]"
    )


def test_default_rules_redact_jwts() -> None:
    text = (
        "jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    out = TraceSanitizer().sanitize(_bundle(text)).events[0].content
    assert out == "jwt [REDACTED by jwt]"


def test_sanitize_returns_new_bundle_and_leaves_input_unchanged() -> None:
    original = _bundle("ping me at a.user@example.com")
    sanitized = TraceSanitizer().sanitize(original)
    assert sanitized is not original
    assert sanitized.events[0] is not original.events[0]
    assert original.events[0].content == "ping me at a.user@example.com"
    assert sanitized.events[0].content == "ping me at [REDACTED by email]"


def test_none_content_is_preserved() -> None:
    sanitized = TraceSanitizer().sanitize(_bundle(None))
    assert sanitized.events[0].content is None


def test_clean_content_is_untouched() -> None:
    text = (
        "nothing sensitive here; token budget is 2000, aws region is us-east-1, "
        "and password policy requires rotation"
    )
    sanitized = TraceSanitizer().sanitize(_bundle(text))
    assert sanitized.events[0].content == text


def test_custom_rules_only() -> None:
    rule = SanitizationRule(name="ticket", pattern=r"TICKET-\d+", replacement="[TICKET]")
    sanitized = TraceSanitizer(rules=[rule]).sanitize(_bundle("see TICKET-42 and a@b.co"))
    # Custom-only ruleset must not apply the default email rule.
    assert sanitized.events[0].content == "see [TICKET] and a@b.co"
