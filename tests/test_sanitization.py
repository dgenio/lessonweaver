"""Tests for the pre-mining trace sanitizer (#46)."""

from __future__ import annotations

import pytest
from redaction_cases import SAFE_CASES, SENSITIVE_CASES_PARAM

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
    assert sanitized.events[0].content == "ping me at [REDACTED by email]"


def test_sanitize_scrubs_task_and_metadata_without_mutating_input() -> None:
    original = TraceBundle(
        trace_id="t1",
        source="unit-test",
        task="Investigate a.user@example.com",
        events=[
            TraceEvent(
                id="e1",
                type=TraceEventType.USER_MESSAGE,
                content="nothing sensitive here",
                metadata={"contact": "a.user@example.com"},
            )
        ],
        outcome="success",
        metadata={
            "token": "Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "nested": ["a.user@example.com", {"key": "-----BEGIN RSA PRIVATE KEY-----"}],
            "count": 1,
        },
    )

    sanitized = TraceSanitizer().sanitize(original)

    assert original.task == "Investigate a.user@example.com"
    assert original.metadata["token"] == "Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    assert original.events[0].metadata["contact"] == "a.user@example.com"
    assert sanitized.task == "Investigate [REDACTED by email]"
    assert sanitized.metadata == {
        "token": "[REDACTED by bearer_token]",
        "nested": ["[REDACTED by email]", {"key": "[REDACTED by private_key]"}],
        "count": 1,
    }
    assert sanitized.events[0].metadata == {"contact": "[REDACTED by email]"}


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
