"""Tests for the pre-mining trace sanitizer (#46)."""

from __future__ import annotations

import pytest
from redaction_cases import SAFE_CASES, SENSITIVE_CASES_PARAM

from lessonweaver.models import TraceBundle, TraceEvent, TraceEventType
from lessonweaver.sanitization import SanitizationRule, TraceSanitizer, redaction_marker


def _bundle(content: str | None) -> TraceBundle:
    return TraceBundle(
        trace_id="t1",
        source="unit-test",
        task="x",
        events=[TraceEvent(id="e1", type=TraceEventType.USER_MESSAGE, content=content)],
        outcome="success",
    )


@SENSITIVE_CASES_PARAM
def test_default_rules_use_shared_sensitive_cases(case_name: str, raw: str, expected: str) -> None:
    assert case_name
    assert TraceSanitizer().sanitize(_bundle(raw)).events[0].content == expected


def test_sanitize_returns_new_bundle_and_leaves_input_unchanged() -> None:
    original = _bundle("ping me at a.user@example.com")
    sanitized = TraceSanitizer().sanitize(original)
    assert sanitized is not original
    assert sanitized.events[0] is not original.events[0]
    assert original.events[0].content == "ping me at a.user@example.com"
    assert sanitized.events[0].content == f"ping me at {redaction_marker('email')}"


def test_redaction_marker_format_is_stable() -> None:
    # Lock the emitted marker format: many tests derive their expected strings
    # from this helper, so a change here is intentional and must be reviewed.
    assert redaction_marker("email") == "[REDACTED by email]"
    assert redaction_marker("api_key") == "[REDACTED by api_key]"


def test_none_content_is_preserved() -> None:
    sanitized = TraceSanitizer().sanitize(_bundle(None))
    assert sanitized.events[0].content is None


def test_clean_content_is_untouched() -> None:
    sanitized = TraceSanitizer().sanitize(_bundle("nothing sensitive here"))
    assert sanitized.events[0].content == "nothing sensitive here"


@pytest.mark.parametrize("text", SAFE_CASES)
def test_safe_content_is_untouched(text: str) -> None:
    sanitized = TraceSanitizer().sanitize(_bundle(text))
    assert sanitized.events[0].content == text


def test_custom_rules_only() -> None:
    rule = SanitizationRule(name="ticket", pattern=r"TICKET-\d+", replacement="[TICKET]")
    sanitized = TraceSanitizer(rules=[rule]).sanitize(_bundle("see TICKET-42 and a@b.co"))
    # Custom-only ruleset must not apply the default email rule.
    assert sanitized.events[0].content == "see [TICKET] and a@b.co"
