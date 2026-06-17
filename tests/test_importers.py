"""Tests for the TraceImporter protocol and built-in importers (#52, #82)."""

from __future__ import annotations

import pytest

from lessonweaver.detection import LessonDetector
from lessonweaver.importers import (
    FAILURE_CASE_PROVENANCE_KEY,
    DictTraceImporter,
    FailureCaseImporter,
    OpenTelemetryImporter,
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


# --- OpenTelemetryImporter ----------------------------------------------------


OTEL_TRACE = {
    "resourceSpans": [
        {
            "resource": {
                "attributes": [
                    {"key": "agent.name", "value": {"stringValue": "lesson-bot"}},
                    {"key": "agent.version", "value": {"stringValue": "1.2.0"}},
                    {"key": "agent.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [
                {
                    "spans": [
                        {
                            "traceId": "trace-otel-1",
                            "spanId": "span-llm",
                            "name": "llm.chat",
                            "attributes": [
                                {
                                    "key": "gen_ai.request.model",
                                    "value": {"stringValue": "gpt-4.1"},
                                },
                                {"key": "gen_ai.usage.input_tokens", "value": {"intValue": "12"}},
                                {"key": "authorization", "value": {"stringValue": "Bearer secret"}},
                            ],
                            "events": [
                                {
                                    "name": "human_feedback",
                                    "attributes": [
                                        {
                                            "key": "feedback.comment",
                                            "value": {"stringValue": "Use cited sources."},
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "traceId": "trace-otel-1",
                            "spanId": "span-tool",
                            "name": "tool.call",
                            "attributes": [
                                {"key": "tool.name", "value": {"stringValue": "github.search"}},
                                {
                                    "key": "tool.arguments_shape",
                                    "value": {"stringValue": "query:string"},
                                },
                                {
                                    "key": "tool.result_shape",
                                    "value": {"stringValue": "items:list"},
                                },
                            ],
                        },
                        {
                            "traceId": "trace-otel-1",
                            "spanId": "span-retrieval",
                            "name": "retrieval.search",
                            "attributes": [
                                {
                                    "key": "retrieval.query",
                                    "value": {"stringValue": "policy rollout"},
                                },
                                {"key": "retrieval.documents_count", "value": {"intValue": 3}},
                            ],
                        },
                        {
                            "traceId": "trace-otel-1",
                            "spanId": "span-handoff",
                            "name": "agent.handoff",
                            "attributes": [
                                {"key": "agent.handoff.from", "value": {"stringValue": "planner"}},
                                {"key": "agent.handoff.to", "value": {"stringValue": "executor"}},
                            ],
                        },
                        {
                            "traceId": "trace-otel-1",
                            "spanId": "span-guardrail",
                            "name": "guardrail.check",
                            "attributes": [
                                {"key": "guardrail.name", "value": {"stringValue": "pii"}},
                                {"key": "guardrail.result", "value": {"stringValue": "blocked"}},
                            ],
                        },
                    ]
                }
            ],
        }
    ]
}


def test_opentelemetry_importer_maps_agent_spans_and_redacts_sensitive_attributes() -> None:
    bundle = OpenTelemetryImporter().import_trace(OTEL_TRACE)

    assert bundle.trace_id == "trace-otel-1"
    assert bundle.source == "opentelemetry"
    assert bundle.metadata["otel"]["agent"] == {
        "framework": "langgraph",
        "name": "lesson-bot",
        "version": "1.2.0",
    }
    assert [event.type for event in bundle.events] == [
        TraceEventType.MODEL_CALL,
        TraceEventType.HUMAN_CORRECTION,
        TraceEventType.TOOL_CALL,
        TraceEventType.TOOL_CALL,
        TraceEventType.WORKFLOW_STEP,
        TraceEventType.EVALUATION_RESULT,
    ]
    llm = bundle.events[0]
    assert llm.metadata["model"] == "gpt-4.1"
    assert llm.metadata["token_usage"]["input"] == 12
    assert llm.metadata["span_attributes"]["authorization"] == "[REDACTED]"
    assert bundle.events[2].metadata["tool_name"] == "github.search"
    assert bundle.events[3].metadata["retrieval"]["query"] == "policy rollout"
    assert bundle.events[4].content == "handoff planner -> executor"
    assert bundle.events[5].status == "failed"


def test_opentelemetry_importer_accepts_jsonl_spans() -> None:
    jsonl = "\n".join(
        [
            '{"traceId":"trace-jsonl","spanId":"s1","name":"llm.chat","attributes":{"gen_ai.request.model":"gpt-4.1"}}',
            '{"traceId":"trace-jsonl","spanId":"s2","name":"tool.call","attributes":{"tool.name":"shell"}}',
        ]
    )

    bundle = OpenTelemetryImporter().import_jsonl_lines(jsonl.splitlines())

    assert bundle.trace_id == "trace-jsonl"
    assert [event.type for event in bundle.events] == [
        TraceEventType.MODEL_CALL,
        TraceEventType.TOOL_CALL,
    ]


def test_opentelemetry_importer_recognizes_otlp_error_status_enum() -> None:
    bundle = OpenTelemetryImporter().import_trace(
        {
            "spans": [
                {
                    "traceId": "trace-error-enum",
                    "spanId": "s1",
                    "name": "tool.call",
                    "attributes": {"tool.name": "api"},
                    "status": {"code": "STATUS_CODE_ERROR"},
                }
            ]
        }
    )

    assert bundle.events[0].status == "error"
    assert bundle.events[0].success is False
    assert bundle.outcome == "failure"


def test_opentelemetry_importer_ignores_ordinary_human_span_events() -> None:
    bundle = OpenTelemetryImporter().import_trace(
        {
            "spans": [
                {
                    "traceId": "trace-human-input",
                    "spanId": "s1",
                    "name": "llm.chat",
                    "events": [
                        {
                            "name": "human_input",
                            "attributes": {"content": "Please continue."},
                        }
                    ],
                }
            ]
        }
    )

    assert [event.type for event in bundle.events] == [TraceEventType.MODEL_CALL]
    assert LessonDetector().detect(bundle) == []


def test_opentelemetry_importer_tolerates_missing_optional_fields_with_warnings() -> None:
    bundle = OpenTelemetryImporter().import_trace({"spans": [{"spanId": "s1", "name": "llm"}]})

    assert bundle.trace_id == "otel-trace"
    assert bundle.events[0].id == "s1"
    assert "missing traceId" in bundle.metadata["otel"]["warnings"][0]


def test_opentelemetry_importer_rejects_malformed_traces() -> None:
    with pytest.raises(ValueError, match="no spans"):
        OpenTelemetryImporter().import_trace({"resourceSpans": []})
