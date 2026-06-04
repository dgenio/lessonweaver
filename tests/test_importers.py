"""Tests for the TraceImporter protocol and built-in importers (#52, #82)."""

from __future__ import annotations

import pytest

from lessonweaver.importers import (
    FAILURE_CASE_PROVENANCE_KEY,
    DictTraceImporter,
    FailureCaseImporter,
    TraceImporter,
    candidates_from_failure_case,
)
from lessonweaver.models import TraceBundle, TraceEventType

CANONICAL_TRACE = {
    "trace_id": "trace-1",
    "source": "unit-test",
    "task": "Do work",
    "events": [{"id": "e1", "type": "user_message"}],
    "outcome": "success",
}

FAILURE_CASE = {
    "schema": "weaver-spec/failure-case@1",
    "failure_id": "fc-0001",
    "task": "Decide whether to deploy",
    "source": "fuzz-replay",
    "replay": {"ref": "replays/fc-0001.json", "reproducible": True},
    "failure": {"summary": "Stale artifact used as evidence.", "severity": "high"},
    "correction": {"summary": "Required a fresh check first."},
}


def test_builtin_importers_satisfy_protocol() -> None:
    # TraceImporter is runtime_checkable, so isinstance verifies the contract.
    assert isinstance(DictTraceImporter(), TraceImporter)
    assert isinstance(FailureCaseImporter(), TraceImporter)


# --- DictTraceImporter ---------------------------------------------------------


def test_dict_importer_can_import_canonical_only() -> None:
    importer = DictTraceImporter()
    assert importer.can_import(CANONICAL_TRACE) is True
    assert importer.can_import({"failure_id": "x", "failure": {}}) is False
    assert importer.can_import({"trace_id": "x"}) is False  # no events list


def test_dict_importer_matches_from_dict() -> None:
    assert DictTraceImporter().import_trace(CANONICAL_TRACE) == TraceBundle.from_dict(
        CANONICAL_TRACE
    )


def test_dict_importer_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError, match="missing required field: source"):
        DictTraceImporter().import_trace({"trace_id": "x", "events": []})


# --- FailureCaseImporter -------------------------------------------------------


def test_failure_case_can_import() -> None:
    importer = FailureCaseImporter()
    assert importer.can_import(FAILURE_CASE) is True  # schema marker
    assert importer.can_import({"failure_id": "x", "failure": {}}) is True  # structural
    assert importer.can_import(CANONICAL_TRACE) is False
    assert importer.can_import({"failure": {}}) is False  # no id


def test_failure_case_maps_to_bundle_with_correction() -> None:
    bundle = FailureCaseImporter().import_trace(FAILURE_CASE)
    assert bundle.trace_id == "fc-0001"
    assert bundle.source == "fuzz-replay"
    assert bundle.outcome == "corrected_by_human"
    assert [e.type for e in bundle.events] == [
        TraceEventType.EVALUATION_RESULT,
        TraceEventType.HUMAN_CORRECTION,
    ]
    assert bundle.events[0].status == "failed"
    provenance = bundle.metadata[FAILURE_CASE_PROVENANCE_KEY]
    assert provenance["failure_id"] == "fc-0001"
    assert provenance["severity"] == "high"
    assert provenance["replay_ref"] == "replays/fc-0001.json"
    assert provenance["reproducible"] is True


def test_failure_case_without_correction_is_failure_outcome() -> None:
    bundle = FailureCaseImporter().import_trace(
        {"failure_id": "fc-2", "failure": {"summary": "boom"}}
    )
    assert bundle.outcome == "failure"
    assert [e.type for e in bundle.events] == [TraceEventType.EVALUATION_RESULT]


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"task": "x"}, "Unrecognized failure case"),
        ({"failure_id": "", "failure": {"summary": "x"}}, "non-empty 'failure_id'"),
        ({"failure_id": "x", "failure": "not-an-object"}, "missing a 'failure' object"),
    ],
)
def test_failure_case_invalid_payloads(payload: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        FailureCaseImporter().import_trace(payload)


def test_candidates_from_failure_case_stamps_provenance() -> None:
    candidates = candidates_from_failure_case(FAILURE_CASE)
    # A failed eval + a human correction each yield a conservative candidate.
    assert len(candidates) == 2
    ids = {c.id for c in candidates}
    assert ids == {"fc-0001-failed-eval", "fc-0001-human-correction"}
    for candidate in candidates:
        assert candidate.metadata[FAILURE_CASE_PROVENANCE_KEY]["failure_id"] == "fc-0001"
