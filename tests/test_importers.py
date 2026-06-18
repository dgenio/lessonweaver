"""Tests for the TraceImporter protocol and built-in importers (#52, #82)."""

from __future__ import annotations

from copy import deepcopy

import pytest

from lessonweaver.importers import (
    FAILURE_CASE_PROVENANCE_KEY,
    DictTraceImporter,
    FailureCaseImporter,
    LangfuseTraceImporter,
    LangSmithTraceImporter,
    TraceImporter,
    candidates_from_failure_case,
)
from lessonweaver.models import TraceBundle, TraceEventType
from lessonweaver.traces import validate_trace_dict

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
    assert isinstance(LangfuseTraceImporter(), TraceImporter)
    assert isinstance(LangSmithTraceImporter(), TraceImporter)


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


# --- LangfuseTraceImporter ----------------------------------------------------


LANGFUSE_EXPORT = {
    "source": "langfuse",
    "trace": {
        "id": "lf-trace-1",
        "name": "Handle refund request",
        "input": {"message": "Can I get a refund?"},
        "metadata": {"tenant": "acme"},
    },
    "observations": [
        {
            "id": "obs-1",
            "type": "GENERATION",
            "name": "answer",
            "input": {"messages": [{"role": "user", "content": "refund?"}]},
            "output": {"content": "Old policy answer"},
            "level": "DEFAULT",
            "metadata": {"model": "demo"},
        },
        {
            "id": "obs-2",
            "type": "SPAN",
            "name": "policy.lookup",
            "input": {"version": "old"},
            "output": {"status": "stale"},
            "level": "ERROR",
            "status_message": "Used stale policy.",
        },
    ],
    "scores": [
        {
            "id": "score-1",
            "name": "human_review",
            "value": 0,
            "comment": "Reviewer corrected the stale policy answer.",
        }
    ],
}


def test_langfuse_importer_can_import_only_langfuse_payloads() -> None:
    importer = LangfuseTraceImporter()
    assert importer.can_import(LANGFUSE_EXPORT) is True
    assert importer.can_import({"schema": "langfuse/export@1", "observations": []}) is True
    assert importer.can_import(CANONICAL_TRACE) is False
    assert importer.can_import({"source": "langsmith", "runs": []}) is False


def test_langfuse_importer_normalizes_export_to_valid_trace() -> None:
    bundle = LangfuseTraceImporter().import_trace(LANGFUSE_EXPORT)

    assert bundle.trace_id == "lf-trace-1"
    assert bundle.source == "langfuse"
    assert bundle.task == "Handle refund request"
    assert bundle.outcome == "failure"
    assert [event.type for event in bundle.events] == [
        TraceEventType.USER_MESSAGE,
        TraceEventType.MODEL_CALL,
        TraceEventType.ERROR,
        TraceEventType.EVALUATION_RESULT,
        TraceEventType.HUMAN_CORRECTION,
    ]
    assert bundle.events[2].status == "failed"
    assert bundle.events[4].content == "Reviewer corrected the stale policy answer."
    assert validate_trace_dict(bundle.to_dict()) == []


def test_langfuse_importer_preserves_unmapped_metadata() -> None:
    bundle = LangfuseTraceImporter().import_trace(LANGFUSE_EXPORT)

    assert bundle.metadata["langfuse"]["trace"]["tenant"] == "acme"
    assert bundle.events[1].metadata["langfuse"]["model"] == "demo"
    assert bundle.events[2].metadata["langfuse"]["observation_type"] == "SPAN"


def test_langfuse_importer_treats_null_metadata_as_empty() -> None:
    payload = deepcopy(LANGFUSE_EXPORT)
    payload["trace"]["metadata"] = None
    payload["observations"][0]["metadata"] = None

    bundle = LangfuseTraceImporter().import_trace(payload)

    assert bundle.metadata["langfuse"]["trace"] == {}
    assert bundle.events[1].metadata["langfuse"] == {"observation_type": "GENERATION"}


def test_langfuse_importer_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="trace id"):
        LangfuseTraceImporter().import_trace({"source": "langfuse", "observations": []})


# --- LangSmithTraceImporter ---------------------------------------------------


LANGSMITH_EXPORT = {
    "source": "langsmith",
    "runs": [
        {
            "id": "run-root",
            "trace_id": "ls-trace-1",
            "name": "Refund agent",
            "run_type": "chain",
            "inputs": {"question": "Can I get a refund?"},
            "outputs": {"answer": "Old policy answer"},
            "status": "success",
            "extra": {"metadata": {"tenant": "acme"}},
            "dotted_order": "20260612Zrun-root",
        },
        {
            "id": "run-tool",
            "trace_id": "ls-trace-1",
            "name": "policy_lookup",
            "run_type": "tool",
            "inputs": {"version": "old"},
            "outputs": {"status": "stale"},
            "error": "Used stale policy.",
            "status": "error",
            "dotted_order": "20260612Zrun-root.20260612Zrun-tool",
        },
    ],
    "feedback": [
        {
            "run_id": "run-root",
            "key": "human_review",
            "score": 0,
            "comment": "Human reviewer required checking the current policy.",
        }
    ],
}


def test_langsmith_importer_can_import_only_langsmith_payloads() -> None:
    importer = LangSmithTraceImporter()
    assert importer.can_import(LANGSMITH_EXPORT) is True
    assert importer.can_import({"schema": "langsmith/run-export@1", "runs": []}) is True
    assert importer.can_import(CANONICAL_TRACE) is False
    assert importer.can_import(LANGFUSE_EXPORT) is False


def test_langsmith_importer_normalizes_export_to_valid_trace() -> None:
    bundle = LangSmithTraceImporter().import_trace(LANGSMITH_EXPORT)

    assert bundle.trace_id == "ls-trace-1"
    assert bundle.source == "langsmith"
    assert bundle.task == "Refund agent"
    assert bundle.outcome == "failure"
    assert [event.type for event in bundle.events] == [
        TraceEventType.WORKFLOW_STEP,
        TraceEventType.ERROR,
        TraceEventType.EVALUATION_RESULT,
        TraceEventType.HUMAN_CORRECTION,
    ]
    assert bundle.events[1].content == "Used stale policy."
    assert bundle.events[3].content == "Human reviewer required checking the current policy."
    assert validate_trace_dict(bundle.to_dict()) == []


def test_langsmith_importer_preserves_run_metadata() -> None:
    bundle = LangSmithTraceImporter().import_trace(LANGSMITH_EXPORT)

    assert bundle.metadata["langsmith"]["run_count"] == 2
    assert bundle.events[0].metadata["langsmith"]["run_type"] == "chain"
    assert bundle.events[0].metadata["langsmith"]["extra"]["metadata"]["tenant"] == "acme"


def test_langsmith_importer_treats_null_extra_as_empty() -> None:
    payload = deepcopy(LANGSMITH_EXPORT)
    payload["runs"][0]["extra"] = None

    bundle = LangSmithTraceImporter().import_trace(payload)

    assert bundle.events[0].metadata["langsmith"]["extra"] == {}


def test_langsmith_importer_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="runs"):
        LangSmithTraceImporter().import_trace({"source": "langsmith", "runs": "bad"})
