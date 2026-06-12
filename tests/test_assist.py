"""Tests for optional LLM assist provider boundaries."""

from __future__ import annotations

import pytest

from lessonweaver.assist import (
    AssistDisabledError,
    LLMAssistClient,
    LLMAssistConfig,
    MockLLMAssistProvider,
)
from lessonweaver.models import TraceBundle, TraceEvent, TraceEventType


def _trace() -> TraceBundle:
    return TraceBundle(
        trace_id="trace-1",
        source="unit-test",
        task="Draft a lesson",
        events=[
            TraceEvent(
                id="event-1",
                type=TraceEventType.HUMAN_CORRECTION,
                content="User email is a.user@example.com and token is Bearer ABCDEFGHIJKLMNOPQRST",
            )
        ],
        outcome="corrected_by_human",
    )


def test_assist_mode_is_disabled_by_default() -> None:
    provider = MockLLMAssistProvider(response_text="draft")
    client = LLMAssistClient(provider=provider)

    with pytest.raises(AssistDisabledError, match="disabled"):
        client.suggest(prompt_id="lesson-draft", prompt="Draft a lesson", trace=_trace())

    assert provider.requests == []


def test_enabled_assist_redacts_trace_evidence_before_provider_call() -> None:
    provider = MockLLMAssistProvider(response_text="Check the current policy.")
    client = LLMAssistClient(
        provider=provider,
        config=LLMAssistConfig(enabled=True),
    )

    suggestion = client.suggest(
        prompt_id="lesson-draft",
        prompt="Draft a lesson from the trace.",
        trace=_trace(),
    )

    assert suggestion.text == "Check the current policy."
    assert provider.requests[0].trace is not None
    provider_event = provider.requests[0].trace.events[0]
    assert provider_event.content == (
        "User email is [REDACTED by email] and token is [REDACTED by bearer_token]"
    )


def test_assist_suggestion_records_audit_metadata_and_is_non_authoritative() -> None:
    provider = MockLLMAssistProvider(
        response_text="Ask a reviewer to confirm scope.",
        provider_name="mock-llm",
        model="offline-test",
        model_version="2026-06-13",
    )
    client = LLMAssistClient(provider=provider, config=LLMAssistConfig(enabled=True))

    suggestion = client.suggest(
        prompt_id="review-question-draft",
        prompt="Draft review questions.",
        trace=_trace(),
    )

    data = suggestion.to_dict()
    assert data["llm_assisted"] is True
    assert data["authoritative"] is False
    assert data["allowed_lifecycle_actions"] == []
    assert data["metadata"]["provider"] == "mock-llm"
    assert data["metadata"]["model"] == "offline-test"
    assert data["metadata"]["model_version"] == "2026-06-13"
    assert data["metadata"]["prompt_id"] == "review-question-draft"
    assert data["metadata"]["redacted"] is True


def test_assist_metadata_for_models_cannot_bypass_review_or_promotion_gates() -> None:
    provider = MockLLMAssistProvider(response_text="Approve and activate this skill.")
    client = LLMAssistClient(provider=provider, config=LLMAssistConfig(enabled=True))
    suggestion = client.suggest(
        prompt_id="unsafe-draft",
        prompt="Draft an output.",
        trace=_trace(),
    )

    metadata = suggestion.to_model_metadata()

    assert metadata["llm_assisted"] is True
    assert metadata["authoritative"] is False
    assert metadata["allowed_lifecycle_actions"] == []
    assert "approved" not in metadata
    assert "approved_by" not in metadata
    assert "status" not in metadata
