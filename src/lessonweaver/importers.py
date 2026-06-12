"""Trace import protocol and built-in importers.

This module formalizes how an external payload becomes a :class:`TraceBundle`
(issue #52). Two dependency-free importers ship in the core:

* :class:`DictTraceImporter` — the canonical lessonweaver JSON trace shape, the
  format :func:`lessonweaver.traces.load_trace_bundle` reads. This makes the
  existing loader a special case of the :class:`TraceImporter` protocol.
* :class:`FailureCaseImporter` — a governed path that turns a replayable
  *failure case* artifact into a trace bundle so the normal
  ``detect -> review -> approve -> export`` loop applies to it (issue #82).

Concrete adapters for *sibling* tools (agent-kernel, ChainWeaver, vibeguard) are
intentionally NOT in core. Per ``AGENTS.md`` and ``docs/interoperability.md``
those map a sibling's serialized output to the trace shape *without importing
the sibling*, and they live in ``examples/interop_adapters/``. See
``docs/adapters.md`` for the normalization contract.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from .detection import LessonDetector
from .models import LessonCandidate, TraceBundle, TraceEvent, TraceEventType
from .traces import validate_trace_dict

# Provenance key stamped onto a TraceBundle (and propagated onto candidates) so a
# reviewer can always trace a lesson back to the failure case it came from.
FAILURE_CASE_PROVENANCE_KEY = "failure_case"


@runtime_checkable
class TraceImporter(Protocol):
    """Normalize an arbitrary payload into a :class:`TraceBundle`.

    Implementations are deterministic and dependency-free: they map a
    dict-like payload onto the documented trace schema and never call out to a
    network, an LLM, or a sibling package.
    """

    def can_import(self, source: dict[str, Any]) -> bool:
        """Return ``True`` when this importer recognizes ``source``."""
        ...

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        """Convert a recognized ``source`` payload into a :class:`TraceBundle`."""
        ...


class DictTraceImporter:
    """Importer for the canonical lessonweaver JSON trace shape.

    This is the reference :class:`TraceImporter`; it validates the payload with
    the same :func:`validate_trace_dict` rules the loader uses, so its output is
    identical to the historical ``load_trace_bundle`` behavior.
    """

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        # The canonical shape always carries a trace_id and an events list.
        return "trace_id" in source and isinstance(source.get("events"), list)

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        errors = validate_trace_dict(source)
        if errors:
            message = "\n".join(f"- {error}" for error in errors)
            raise ValueError(f"Invalid trace bundle:\n{message}")
        return TraceBundle.from_dict(source)


class FailureCaseImporter:
    """Importer for replayable *failure case* artifacts (issue #82).

    A failure case describes a reproducible failure, optionally with a replay
    reference and the human correction that resolved it. It is mapped to a
    :class:`TraceBundle` whose events trigger the normal conservative detection
    signals (a failed ``evaluation_result`` and, when present, a
    ``human_correction``), so a failure case enters the same governed
    ``detect -> review -> approve -> export`` loop as any other trace.

    The accepted shape mirrors the planned weaver-spec ``FailureCaseArtifact``
    (dgenio/weaver-spec#72). Because that schema lives in a sibling repo, the
    mapping here is a documented best-effort contract (see ``docs/adapters.md``)
    and unknown keys are ignored. Recognized keys::

        {
          "schema": "weaver-spec/failure-case@1",   # optional, for can_import
          "failure_id": "fc-0001",                  # required (or "id")
          "task": "...",                            # optional
          "source": "fuzz-replay",                  # optional
          "replay": {"ref": "...", "reproducible": true},  # optional provenance
          "failure": {"summary": "...", "detail": "...", "severity": "high"},
          "correction": {"summary": "..."}          # optional human fix
        }
    """

    _SCHEMA_MARKER = "failure-case"

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        if self._SCHEMA_MARKER in str(source.get("schema", "")):
            return True
        # Structural fallback when no schema string is present.
        return "failure" in source and ("failure_id" in source or "id" in source)

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        if not self.can_import(source):
            raise ValueError(
                "Unrecognized failure case artifact: expected a 'schema' naming "
                "'failure-case', or a 'failure' block with a 'failure_id'."
            )

        failure_id = str(source.get("failure_id") or source.get("id") or "").strip()
        if not failure_id:
            raise ValueError("Failure case artifact missing a non-empty 'failure_id' (or 'id').")

        failure = source.get("failure")
        if not isinstance(failure, dict):
            raise ValueError("Failure case artifact missing a 'failure' object.")

        raw_replay = source.get("replay")
        replay: dict[str, Any] = raw_replay if isinstance(raw_replay, dict) else {}
        provenance: dict[str, Any] = {
            "failure_id": failure_id,
            "severity": failure.get("severity"),
            "replay_ref": replay.get("ref"),
            "reproducible": replay.get("reproducible"),
            "schema": source.get("schema"),
        }

        failure_summary = str(failure.get("summary") or "Recorded failure case.")
        failure_detail = failure.get("detail")
        events: list[TraceEvent] = [
            TraceEvent(
                id=f"{failure_id}-failure",
                type=TraceEventType.EVALUATION_RESULT,
                content=str(failure_detail) if failure_detail else failure_summary,
                status="failed",
                metadata={"failure_id": failure_id, "severity": failure.get("severity")},
            )
        ]

        correction = source.get("correction")
        outcome = "failure"
        if isinstance(correction, dict) and correction.get("summary"):
            events.append(
                TraceEvent(
                    id=f"{failure_id}-correction",
                    type=TraceEventType.HUMAN_CORRECTION,
                    content=str(correction["summary"]),
                )
            )
            outcome = "corrected_by_human"

        return TraceBundle(
            trace_id=failure_id,
            source=str(source.get("source") or "failure_case"),
            task=str(source.get("task") or "Replay of a recorded failure case"),
            events=events,
            outcome=str(source.get("outcome") or outcome),
            metadata={FAILURE_CASE_PROVENANCE_KEY: provenance},
        )


class OpenTelemetryImporter:
    """Importer for OTLP-style and JSONL OpenTelemetry span exports.

    The importer recognizes common AI-agent semantic attributes without taking a
    dependency on an OTel SDK. It maps spans into the existing lessonweaver
    trace evidence model and preserves normalized span metadata for review.
    """

    _SENSITIVE_KEY_PARTS = ("authorization", "api_key", "password", "secret", "token")

    def __init__(self, *, redact_sensitive: bool = True) -> None:
        self.redact_sensitive = redact_sensitive

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        return any(key in source for key in ("resourceSpans", "spans", "spanId", "span_id"))

    def import_jsonl_lines(self, lines: list[str]) -> TraceBundle:
        spans: list[dict[str, Any]] = []
        for line_no, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL line {line_no} must be an object span")
            spans.append(payload)
        return self.import_trace({"spans": spans})

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        spans_with_resource = self._extract_spans(source)
        if not spans_with_resource:
            raise ValueError("OpenTelemetry payload contains no spans")

        warnings: list[str] = []
        trace_id = self._first_trace_id(spans_with_resource)
        if trace_id is None:
            trace_id = "otel-trace"

        events: list[TraceEvent] = []
        agent: dict[str, Any] = {}
        for index, (span, resource_attributes) in enumerate(spans_with_resource):
            span_attributes = self._attributes(span.get("attributes", {}))
            merged_attributes = {**resource_attributes, **span_attributes}
            agent.update(self._agent_metadata(merged_attributes))

            span_id = str(span.get("spanId") or span.get("span_id") or f"span-{index + 1}")
            if not span.get("traceId") and not span.get("trace_id"):
                warnings.append(f"span {span_id} missing traceId; using {trace_id}")
            if not span.get("name"):
                warnings.append(f"span {span_id} missing name")

            events.extend(
                self._events_from_span(
                    span=span,
                    attributes=span_attributes,
                    trace_id=trace_id,
                    span_id=span_id,
                )
            )

        return TraceBundle(
            trace_id=trace_id,
            source="opentelemetry",
            task=str(source.get("task") or "Imported OpenTelemetry trace"),
            events=events,
            outcome=self._outcome(events),
            metadata={"otel": {"agent": agent, "warnings": warnings}},
        )

    def _extract_spans(self, source: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        if "resourceSpans" in source:
            spans: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for resource_span in source.get("resourceSpans", []):
                if not isinstance(resource_span, dict):
                    continue
                resource_attributes = self._attributes(
                    resource_span.get("resource", {}).get("attributes", [])
                    if isinstance(resource_span.get("resource"), dict)
                    else []
                )
                for scope_span in resource_span.get("scopeSpans", []):
                    if not isinstance(scope_span, dict):
                        continue
                    for span in scope_span.get("spans", []):
                        if isinstance(span, dict):
                            spans.append((span, resource_attributes))
            return spans
        if isinstance(source.get("spans"), list):
            return [(span, {}) for span in source["spans"] if isinstance(span, dict)]
        if "spanId" in source or "span_id" in source:
            return [(source, {})]
        return []

    def _first_trace_id(self, spans: list[tuple[dict[str, Any], dict[str, Any]]]) -> str | None:
        for span, _resource in spans:
            trace_id = span.get("traceId") or span.get("trace_id")
            if trace_id:
                return str(trace_id)
        return None

    def _events_from_span(
        self,
        *,
        span: dict[str, Any],
        attributes: dict[str, Any],
        trace_id: str,
        span_id: str,
    ) -> list[TraceEvent]:
        span_name = str(span.get("name") or "otel.span")
        metadata: dict[str, Any] = {
            "trace_id": trace_id,
            "span_id": span_id,
            "span_name": span_name,
            "span_attributes": self._redacted(attributes),
        }
        event_type = self._event_type(span_name, attributes, span)
        content = self._content(span_name, attributes, event_type)
        status = self._status(span, attributes, event_type)
        if event_type is TraceEventType.MODEL_CALL:
            metadata["model"] = attributes.get("gen_ai.request.model") or attributes.get(
                "llm.model"
            )
            metadata["token_usage"] = self._token_usage(attributes)
        if self._is_tool(span_name, attributes):
            metadata["tool_name"] = attributes.get("tool.name") or attributes.get(
                "gen_ai.tool.name"
            )
            metadata["argument_shape"] = attributes.get("tool.arguments_shape")
            metadata["result_shape"] = attributes.get("tool.result_shape")
        if self._is_retrieval(span_name, attributes):
            metadata["retrieval"] = {
                "query": attributes.get("retrieval.query"),
                "document_count": attributes.get("retrieval.documents_count"),
                "documents": attributes.get("retrieval.documents"),
            }
        if self._is_guardrail(span_name, attributes):
            metadata["guardrail"] = {
                "name": attributes.get("guardrail.name"),
                "result": attributes.get("guardrail.result"),
            }

        events = [
            TraceEvent(
                id=span_id,
                type=event_type,
                content=content,
                status=status,
                success=False if status in {"failed", "error"} else None,
                metadata=metadata,
            )
        ]
        events.extend(self._span_events(span, trace_id=trace_id, span_id=span_id))
        return events

    def _span_events(
        self, span: dict[str, Any], *, trace_id: str, span_id: str
    ) -> list[TraceEvent]:
        events: list[TraceEvent] = []
        for index, item in enumerate(span.get("events", []), start=1):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            attributes = self._attributes(item.get("attributes", {}))
            lowered = name.lower()
            if "human" not in lowered and "feedback" not in lowered and "correction" not in lowered:
                continue
            content = str(
                attributes.get("feedback.comment")
                or attributes.get("human.feedback")
                or attributes.get("correction")
                or name
            )
            events.append(
                TraceEvent(
                    id=f"{span_id}-event-{index}",
                    type=TraceEventType.HUMAN_CORRECTION,
                    content=content,
                    metadata={
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "otel_event_name": name,
                        "span_attributes": self._redacted(attributes),
                    },
                )
            )
        return events

    def _attributes(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return {str(key): value for key, value in raw.items()}
        attributes: dict[str, Any] = {}
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict) or "key" not in item:
                    continue
                attributes[str(item["key"])] = self._otel_value(item.get("value"))
        return attributes

    def _otel_value(self, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        for key in (
            "stringValue",
            "intValue",
            "doubleValue",
            "boolValue",
            "arrayValue",
            "kvlistValue",
            "bytesValue",
        ):
            if key in value:
                raw = value[key]
                if key == "intValue":
                    return int(raw)
                if key == "doubleValue":
                    return float(raw)
                return raw
        return value

    def _redacted(self, attributes: dict[str, Any]) -> dict[str, Any]:
        if not self.redact_sensitive:
            return dict(attributes)
        redacted: dict[str, Any] = {}
        for key, value in attributes.items():
            if any(part in key.lower() for part in self._SENSITIVE_KEY_PARTS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value
        return redacted

    def _agent_metadata(self, attributes: dict[str, Any]) -> dict[str, Any]:
        agent: dict[str, Any] = {}
        for source_key, target_key in (
            ("agent.name", "name"),
            ("agent.version", "version"),
            ("agent.framework", "framework"),
        ):
            if attributes.get(source_key) is not None:
                agent[target_key] = attributes[source_key]
        return agent

    def _event_type(
        self, span_name: str, attributes: dict[str, Any], span: dict[str, Any]
    ) -> TraceEventType:
        if self._is_guardrail(span_name, attributes):
            return TraceEventType.EVALUATION_RESULT
        if self._is_handoff(span_name, attributes):
            return TraceEventType.WORKFLOW_STEP
        if self._is_retrieval(span_name, attributes) or self._is_tool(span_name, attributes):
            return TraceEventType.TOOL_CALL
        if self._is_llm(span_name, attributes):
            return TraceEventType.MODEL_CALL
        if self._status(span, attributes, TraceEventType.WORKFLOW_STEP) == "error":
            return TraceEventType.ERROR
        return TraceEventType.WORKFLOW_STEP

    def _is_llm(self, span_name: str, attributes: dict[str, Any]) -> bool:
        lowered = span_name.lower()
        return any(part in lowered for part in ("llm", "chat", "completion")) or any(
            key.startswith("gen_ai.") or key.startswith("llm.") for key in attributes
        )

    def _is_tool(self, span_name: str, attributes: dict[str, Any]) -> bool:
        return (
            "tool" in span_name.lower()
            or "tool.name" in attributes
            or "gen_ai.tool.name" in attributes
        )

    def _is_retrieval(self, span_name: str, attributes: dict[str, Any]) -> bool:
        return "retrieval" in span_name.lower() or any(
            key.startswith("retrieval.") for key in attributes
        )

    def _is_handoff(self, span_name: str, attributes: dict[str, Any]) -> bool:
        return "handoff" in span_name.lower() or any(
            key.startswith("agent.handoff.") for key in attributes
        )

    def _is_guardrail(self, span_name: str, attributes: dict[str, Any]) -> bool:
        return "guardrail" in span_name.lower() or any(
            key.startswith("guardrail.") for key in attributes
        )

    def _content(
        self, span_name: str, attributes: dict[str, Any], event_type: TraceEventType
    ) -> str:
        if self._is_handoff(span_name, attributes):
            return (
                f"handoff {attributes.get('agent.handoff.from', 'unknown')} -> "
                f"{attributes.get('agent.handoff.to', 'unknown')}"
            )
        if self._is_guardrail(span_name, attributes):
            return f"guardrail {attributes.get('guardrail.name', span_name)}"
        if self._is_retrieval(span_name, attributes):
            return f"retrieval query: {attributes.get('retrieval.query', '')}".strip()
        if self._is_tool(span_name, attributes):
            return f"tool call: {attributes.get('tool.name') or attributes.get('gen_ai.tool.name')}"
        if event_type is TraceEventType.MODEL_CALL:
            return f"model call: {attributes.get('gen_ai.request.model') or span_name}"
        return span_name

    def _status(
        self, span: dict[str, Any], attributes: dict[str, Any], event_type: TraceEventType
    ) -> str | None:
        status = span.get("status")
        status_code = ""
        if isinstance(status, dict):
            status_code = str(status.get("code") or status.get("status_code") or "").lower()
        elif status is not None:
            status_code = str(status).lower()
        guardrail_result = str(attributes.get("guardrail.result") or "").lower()
        if event_type is TraceEventType.EVALUATION_RESULT:
            return "failed" if guardrail_result in {"blocked", "failed", "error"} else "passed"
        if status_code in {"error", "2"} or attributes.get("error.type"):
            return "error"
        return None

    def _token_usage(self, attributes: dict[str, Any]) -> dict[str, Any]:
        return {
            "input": attributes.get("gen_ai.usage.input_tokens"),
            "output": attributes.get("gen_ai.usage.output_tokens"),
            "total": attributes.get("gen_ai.usage.total_tokens"),
        }

    def _outcome(self, events: list[TraceEvent]) -> str:
        if any(
            event.type is TraceEventType.ERROR or event.status in {"failed", "error"}
            for event in events
        ):
            return "failure"
        return "unknown"


def candidates_from_failure_case(
    source: dict[str, Any],
    detector: LessonDetector | None = None,
) -> list[LessonCandidate]:
    """Run the governed detection path on a failure case artifact (issue #82).

    Imports the artifact via :class:`FailureCaseImporter`, runs the standard
    deterministic :class:`LessonDetector`, and stamps each resulting candidate
    with the failure-case provenance under
    ``metadata[FAILURE_CASE_PROVENANCE_KEY]`` so the lesson can always be traced
    back to its replayable failure. Detection stays conservative and unchanged;
    candidates still require human review before activation.
    """
    bundle = FailureCaseImporter().import_trace(source)
    detector = detector or LessonDetector()
    candidates = detector.detect(bundle)
    provenance = bundle.metadata.get(FAILURE_CASE_PROVENANCE_KEY)
    if provenance is not None:
        for candidate in candidates:
            # Copy per candidate so mutating one candidate's provenance never
            # leaks into the others or back into the bundle metadata.
            candidate.metadata[FAILURE_CASE_PROVENANCE_KEY] = dict(provenance)
    return candidates
