"""Property-based coverage for serialization and export boundaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from lessonweaver.filemerge import merge_managed_block
from lessonweaver.models import (
    RiskLevel,
    Scope,
    SensitivityLevel,
    SkillCard,
    SkillStatus,
    TraceBundle,
    TraceEvent,
    TraceEventType,
)
from lessonweaver.sanitization import TraceSanitizer
from lessonweaver.traces import load_trace_bundle

UTC = timezone.utc
NOW = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)

json_scalar = st.none() | st.booleans() | st.integers() | st.text()
json_value: st.SearchStrategy[Any] = st.recursive(
    json_scalar,
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=20), children, max_size=4)
    ),
    max_leaves=12,
)
text = st.text(max_size=80)
metadata = st.dictionaries(st.text(min_size=1, max_size=20), json_value, max_size=4)


@settings(
    max_examples=75,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    trace_id=text.filter(bool),
    source=text.filter(bool),
    task=text,
    outcome=text,
    event_ids=st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=5, unique=True),
    contents=st.lists(st.none() | text, min_size=1, max_size=5),
    statuses=st.lists(st.none() | text, min_size=1, max_size=5),
    successes=st.lists(st.none() | st.booleans(), min_size=1, max_size=5),
    event_metadata=st.lists(metadata, min_size=1, max_size=5),
    bundle_metadata=metadata,
)
def test_trace_bundle_round_trips_through_dict(
    trace_id: str,
    source: str,
    task: str,
    outcome: str,
    event_ids: list[str],
    contents: list[str | None],
    statuses: list[str | None],
    successes: list[bool | None],
    event_metadata: list[dict[str, Any]],
    bundle_metadata: dict[str, Any],
) -> None:
    events = [
        TraceEvent(
            id=event_id,
            type=list(TraceEventType)[index % len(TraceEventType)],
            content=contents[index % len(contents)],
            status=statuses[index % len(statuses)],
            success=successes[index % len(successes)],
            metadata=event_metadata[index % len(event_metadata)],
        )
        for index, event_id in enumerate(event_ids)
    ]
    bundle = TraceBundle(
        trace_id=trace_id,
        source=source,
        task=task,
        events=events,
        outcome=outcome,
        metadata=bundle_metadata,
    )

    assert TraceBundle.from_dict(bundle.to_dict()) == bundle


@settings(max_examples=75, derandomize=True)
@given(
    skill_id=text.filter(bool),
    name=text.filter(bool),
    description=text,
    applies_when=st.lists(text, max_size=4),
    does_not_apply_when=st.lists(text, max_size=4),
    instructions=st.lists(text, max_size=4),
    anti_patterns=st.lists(text, max_size=4),
    evidence_trace_ids=st.lists(text, max_size=4),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    risk_level=st.sampled_from(list(RiskLevel)),
    scope=st.sampled_from(list(Scope)),
    status=st.sampled_from(list(SkillStatus)),
    sensitivity=st.sampled_from(list(SensitivityLevel)),
    version=text.filter(bool),
    owner=st.none() | text,
    approved_by=st.none() | text,
    skill_metadata=metadata,
)
def test_skill_card_round_trips_through_dict(
    skill_id: str,
    name: str,
    description: str,
    applies_when: list[str],
    does_not_apply_when: list[str],
    instructions: list[str],
    anti_patterns: list[str],
    evidence_trace_ids: list[str],
    confidence: float,
    risk_level: RiskLevel,
    scope: Scope,
    status: SkillStatus,
    sensitivity: SensitivityLevel,
    version: str,
    owner: str | None,
    approved_by: str | None,
    skill_metadata: dict[str, Any],
) -> None:
    skill = SkillCard(
        id=skill_id,
        name=name,
        description=description,
        applies_when=applies_when,
        does_not_apply_when=does_not_apply_when,
        instructions=instructions,
        anti_patterns=anti_patterns,
        evidence_trace_ids=evidence_trace_ids,
        confidence=confidence,
        risk_level=risk_level,
        scope=scope,
        version=version,
        status=status,
        sensitivity=sensitivity,
        owner=owner,
        approved_by=approved_by,
        created_at=NOW,
        updated_at=NOW,
        metadata=skill_metadata,
    )

    assert SkillCard.from_dict(skill.to_dict()) == skill


@settings(
    max_examples=100,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(payload=json_value)
def test_load_trace_bundle_only_raises_value_error_for_json_payloads(
    payload: Any, tmp_path: Path
) -> None:
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_trace_bundle(path)
    except ValueError:
        return
    except Exception as exc:
        pytest.fail(f"load_trace_bundle leaked {type(exc).__name__}: {exc}")


@settings(max_examples=75, derandomize=True)
@given(bundle_metadata=metadata, event_metadata=metadata, content=text)
def test_trace_sanitizer_is_immutable_and_idempotent(
    bundle_metadata: dict[str, Any], event_metadata: dict[str, Any], content: str
) -> None:
    original = TraceBundle(
        trace_id="trace-1",
        source="property-test",
        task="sanitize",
        events=[
            TraceEvent(
                id="event-1",
                type=TraceEventType.USER_MESSAGE,
                content=f"{content} contact user@example.com",
                metadata=event_metadata,
            )
        ],
        outcome="success",
        metadata=bundle_metadata,
    )
    original_payload = original.to_dict()
    sanitizer = TraceSanitizer()

    once = sanitizer.sanitize(original)
    twice = sanitizer.sanitize(once)

    assert original.to_dict() == original_payload
    assert once == twice


@settings(max_examples=75, derandomize=True)
@given(
    existing=text,
    content=text,
    skill_id=st.from_regex(r"[A-Za-z0-9_.-]{1,32}", fullmatch=True),
)
def test_managed_block_merge_is_idempotent(existing: str, content: str, skill_id: str) -> None:
    once = merge_managed_block(existing, content, skill_id)
    twice = merge_managed_block(once, content, skill_id)

    assert once == twice
