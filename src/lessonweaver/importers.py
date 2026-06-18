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

from typing import Any, ClassVar, Protocol, runtime_checkable

from .detection import LessonDetector
from .models import LessonCandidate, TraceBundle, TraceEvent, TraceEventType
from .sanitization import TraceSanitizer
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


class OpenCodeTraceImporter:
    """Importer for dependency-free OpenCode plugin/tool event payloads.

    The importer accepts a small structural shape rather than importing OpenCode:
    a session id plus an ordered ``events`` list. Unknown top-level and event
    fields are preserved under ``metadata`` so reviewers can trace normalized
    evidence back to the original plugin payload.
    """

    _TYPE_MAP: ClassVar[dict[str, TraceEventType]] = {
        "assistant": TraceEventType.ASSISTANT_MESSAGE,
        "assistant_message": TraceEventType.ASSISTANT_MESSAGE,
        "correction": TraceEventType.HUMAN_CORRECTION,
        "error": TraceEventType.ERROR,
        "human_correction": TraceEventType.HUMAN_CORRECTION,
        "model_call": TraceEventType.MODEL_CALL,
        "tool_call": TraceEventType.TOOL_CALL,
        "tool_result": TraceEventType.TOOL_RESULT,
        "user": TraceEventType.USER_MESSAGE,
        "user_message": TraceEventType.USER_MESSAGE,
    }
    _TOP_LEVEL_KEYS: ClassVar[set[str]] = {
        "events",
        "outcome",
        "schema",
        "session_id",
        "source",
        "task",
        "trace_id",
    }
    _EVENT_KEYS: ClassVar[set[str]] = {
        "content",
        "id",
        "message",
        "output",
        "status",
        "success",
        "type",
    }

    def __init__(self, *, sanitize: bool = True) -> None:
        self.sanitize = sanitize

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        if "opencode" in str(source.get("schema", "")).lower():
            return isinstance(source.get("events"), list)
        return str(source.get("source", "")).lower() == "opencode" and isinstance(
            source.get("events"), list
        )

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        if not self.can_import(source):
            raise ValueError(
                "Unrecognized OpenCode payload: expected source='opencode' or an "
                "OpenCode schema with an 'events' list."
            )
        trace_id = str(source.get("session_id") or source.get("trace_id") or "").strip()
        if not trace_id:
            raise ValueError("OpenCode payload missing a non-empty 'session_id'.")

        raw_events = source.get("events")
        if not isinstance(raw_events, list):
            raise ValueError("OpenCode payload missing an 'events' list.")

        events: list[TraceEvent] = []
        for index, raw_event in enumerate(raw_events, start=1):
            if not isinstance(raw_event, dict):
                raise ValueError(f"OpenCode event {index} must be an event object.")
            events.append(self._event_from_dict(trace_id, index, raw_event))
        self._propagate_tool_results(events)

        outcome = str(source.get("outcome") or self._infer_outcome(events))
        bundle = TraceBundle(
            trace_id=trace_id,
            source="opencode",
            task=str(source.get("task") or "OpenCode session"),
            events=events,
            outcome=outcome,
            metadata={"opencode": self._metadata(source, self._TOP_LEVEL_KEYS)},
        )
        if self.sanitize:
            return TraceSanitizer().sanitize(bundle)
        return bundle

    def _event_from_dict(self, trace_id: str, index: int, raw_event: dict[str, Any]) -> TraceEvent:
        raw_type = str(raw_event.get("type") or "workflow_step").lower()
        event_type = self._TYPE_MAP.get(raw_type, TraceEventType.WORKFLOW_STEP)
        return TraceEvent(
            id=str(raw_event.get("id") or f"{trace_id}-event-{index}"),
            type=event_type,
            content=self._content(raw_event),
            status=self._status(raw_event, event_type),
            success=self._success(raw_event),
            metadata=self._metadata(raw_event, self._EVENT_KEYS) | {"opencode_type": raw_type},
        )

    def _content(self, raw_event: dict[str, Any]) -> str:
        for key in ("message", "content", "output"):
            value = raw_event.get(key)
            if value is not None:
                return str(value)
        return ""

    def _status(self, raw_event: dict[str, Any], event_type: TraceEventType) -> str | None:
        if raw_event.get("status") is not None:
            return str(raw_event["status"])
        if event_type is TraceEventType.TOOL_RESULT and raw_event.get("success") is False:
            return "failed"
        return None

    def _success(self, raw_event: dict[str, Any]) -> bool | None:
        success = raw_event.get("success")
        return bool(success) if success is not None else None

    def _metadata(self, source: dict[str, Any], known_keys: set[str]) -> dict[str, Any]:
        return {key: value for key, value in source.items() if key not in known_keys}

    def _propagate_tool_results(self, events: list[TraceEvent]) -> None:
        calls_by_id = {
            event.id: event for event in events if event.type is TraceEventType.TOOL_CALL
        }
        last_call: TraceEvent | None = None
        for event in events:
            if event.type is TraceEventType.TOOL_CALL:
                last_call = event
                continue
            if event.type is not TraceEventType.TOOL_RESULT:
                continue

            linked_call = self._linked_tool_call(event, calls_by_id) or last_call
            if linked_call is None:
                continue
            if event.success is False or event.status == "failed":
                linked_call.success = False
                linked_call.status = "failed"
            elif event.success is True:
                linked_call.success = True
                linked_call.status = linked_call.status or event.status

    def _linked_tool_call(
        self, event: TraceEvent, calls_by_id: dict[str, TraceEvent]
    ) -> TraceEvent | None:
        for key in ("tool_call_id", "tool_use_id", "call_id"):
            value = event.metadata.get(key)
            if isinstance(value, str) and value in calls_by_id:
                return calls_by_id[value]
        return None

    def _infer_outcome(self, events: list[TraceEvent]) -> str:
        if any(event.type is TraceEventType.HUMAN_CORRECTION for event in events):
            return "corrected_by_human"
        if any(event.type is TraceEventType.ERROR or event.status == "failed" for event in events):
            return "failure"
        return "success"


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
