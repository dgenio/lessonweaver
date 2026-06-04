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
    sanitized = TraceSanitizer().sanitize(_bundle("nothing sensitive here"))
    assert sanitized.events[0].content == "nothing sensitive here"


def test_custom_rules_only() -> None:
    rule = SanitizationRule(name="ticket", pattern=r"TICKET-\d+", replacement="[TICKET]")
    sanitized = TraceSanitizer(rules=[rule]).sanitize(_bundle("see TICKET-42 and a@b.co"))
    # Custom-only ruleset must not apply the default email rule.
    assert sanitized.events[0].content == "see [TICKET] and a@b.co"
