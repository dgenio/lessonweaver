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
from .sanitization import TraceSanitizer
from .traces import validate_trace_dict

# Provenance key stamped onto a TraceBundle (and propagated onto candidates) so a
# reviewer can always trace a lesson back to the failure case it came from.
FAILURE_CASE_PROVENANCE_KEY = "failure_case"
CLAUDE_CODE_PROVENANCE_KEY = "claude_code"


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


class ClaudeCodeTraceImporter:
    """Importer for Claude Code hook/transcript-style event payloads.

    The importer accepts dependency-free JSON captured by hooks or transcript
    exporters. It intentionally maps only stable, common concepts: messages,
    tool calls/results, errors, retries, human corrections, and final answers.
    Source-specific or unknown record fields are preserved under
    ``TraceEvent.metadata["claude_code"]``.
    """

    _SCHEMA_MARKER = "claude-code"

    _TYPE_MAP: dict[str, TraceEventType] = {
        "assistant": TraceEventType.ASSISTANT_MESSAGE,
        "assistant_message": TraceEventType.ASSISTANT_MESSAGE,
        "correction": TraceEventType.HUMAN_CORRECTION,
        "error": TraceEventType.ERROR,
        "eval": TraceEventType.EVALUATION_RESULT,
        "evaluation_result": TraceEventType.EVALUATION_RESULT,
        "exception": TraceEventType.ERROR,
        "final": TraceEventType.FINAL_ANSWER,
        "final_answer": TraceEventType.FINAL_ANSWER,
        "human_correction": TraceEventType.HUMAN_CORRECTION,
        "llm_call": TraceEventType.MODEL_CALL,
        "model": TraceEventType.MODEL_CALL,
        "model_call": TraceEventType.MODEL_CALL,
        "retry": TraceEventType.RETRY,
        "review_comment": TraceEventType.HUMAN_CORRECTION,
        "step": TraceEventType.WORKFLOW_STEP,
        "tool": TraceEventType.TOOL_CALL,
        "tool_call": TraceEventType.TOOL_CALL,
        "tool_response": TraceEventType.TOOL_RESULT,
        "tool_result": TraceEventType.TOOL_RESULT,
        "tool_use": TraceEventType.TOOL_CALL,
        "user": TraceEventType.USER_MESSAGE,
        "user_message": TraceEventType.USER_MESSAGE,
        "workflow_step": TraceEventType.WORKFLOW_STEP,
    }

    _KNOWN_EVENT_KEYS = {
        "content",
        "event",
        "id",
        "input",
        "is_error",
        "message",
        "name",
        "path",
        "role",
        "status",
        "success",
        "tool_name",
        "tool_use_id",
        "type",
        "uuid",
    }

    def __init__(self, sanitizer: TraceSanitizer | None = None) -> None:
        self.sanitizer = sanitizer if sanitizer is not None else TraceSanitizer()

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        if self._SCHEMA_MARKER in str(source.get("schema", "")):
            return True
        if str(source.get("source", "")).lower() == "claude_code" and self._has_events_key(source):
            return True
        return bool(source.get("session_id") and self._has_events_key(source))

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        if not self.can_import(source):
            raise ValueError(
                "Unrecognized Claude Code trace: expected a schema naming "
                "'claude-code', source='claude_code', or a session_id with events."
            )

        session_id = str(source.get("session_id") or source.get("trace_id") or "").strip()
        if not session_id:
            raise ValueError("Claude Code trace missing a non-empty 'session_id'.")

        raw_events = self._raw_events(source)
        if not isinstance(raw_events, list) or not raw_events:
            raise ValueError(
                "Claude Code trace requires a non-empty 'events' or 'transcript' list."
            )

        events = [self._map_event(session_id, item, index) for index, item in enumerate(raw_events)]
        outcome = self._outcome(source, events)
        bundle = TraceBundle(
            trace_id=session_id,
            source="claude_code",
            task=str(
                source.get("task") or source.get("prompt") or f"Claude Code session {session_id}"
            ),
            events=events,
            outcome=str(source.get("outcome") or outcome),
            metadata={
                CLAUDE_CODE_PROVENANCE_KEY: {
                    "session_id": session_id,
                    "cwd": source.get("cwd"),
                    "schema": source.get("schema"),
                }
            },
        )
        return self.sanitizer.sanitize(bundle)

    @staticmethod
    def _raw_events(source: dict[str, Any]) -> Any:
        return source.get("events", source.get("transcript"))

    @staticmethod
    def _has_events_key(source: dict[str, Any]) -> bool:
        return "events" in source or "transcript" in source

    def _map_event(self, session_id: str, raw_event: Any, index: int) -> TraceEvent:
        if not isinstance(raw_event, dict):
            raise ValueError(f"Claude Code event[{index}] must be an object.")

        event_type = self._event_type(raw_event)
        event_id = str(
            raw_event.get("id") or raw_event.get("uuid") or f"{session_id}-event-{index + 1}"
        )
        success = self._success(raw_event)
        status = self._status(raw_event, success)

        metadata: dict[str, Any] = {}
        tool_name = raw_event.get("tool_name") or raw_event.get("name")
        if tool_name:
            metadata["tool_name"] = str(tool_name)
        if raw_event.get("tool_use_id"):
            metadata["tool_use_id"] = str(raw_event["tool_use_id"])
        if raw_event.get("path"):
            metadata["path"] = str(raw_event["path"])

        input_path = raw_event.get("input")
        if isinstance(input_path, dict) and input_path.get("file_path"):
            metadata.setdefault("path", str(input_path["file_path"]))

        extras = {
            key: value for key, value in raw_event.items() if key not in self._KNOWN_EVENT_KEYS
        }
        if extras:
            metadata[CLAUDE_CODE_PROVENANCE_KEY] = dict(extras)

        return TraceEvent(
            id=event_id,
            type=event_type,
            content=self._content(raw_event),
            status=status,
            success=success,
            metadata=metadata,
        )

    def _event_type(self, raw_event: dict[str, Any]) -> TraceEventType:
        raw_type = str(
            raw_event.get("type") or raw_event.get("event") or raw_event.get("role") or ""
        )
        normalized = raw_type.strip().lower().replace("-", "_").replace(" ", "_")
        return self._TYPE_MAP.get(normalized, TraceEventType.WORKFLOW_STEP)

    @staticmethod
    def _content(raw_event: dict[str, Any]) -> str | None:
        for key in ("content", "message"):
            value = raw_event.get(key)
            if value not in (None, ""):
                return str(value)
        value = raw_event.get("input")
        if value not in (None, ""):
            if isinstance(value, dict):
                return json.dumps(value, sort_keys=True)
            return str(value)
        return None

    @staticmethod
    def _success(raw_event: dict[str, Any]) -> bool | None:
        if "success" in raw_event:
            return bool(raw_event["success"])
        if "is_error" in raw_event:
            return not bool(raw_event["is_error"])
        return None

    @staticmethod
    def _status(raw_event: dict[str, Any], success: bool | None) -> str | None:
        if raw_event.get("status") not in (None, ""):
            return str(raw_event["status"])
        if success is False:
            return "failed"
        if success is True:
            return "succeeded"
        return None

    @staticmethod
    def _outcome(source: dict[str, Any], events: list[TraceEvent]) -> str:
        if source.get("outcome"):
            return str(source["outcome"])
        if any(event.type is TraceEventType.HUMAN_CORRECTION for event in events):
            return "corrected_by_human"
        if any(event.status == "failed" or event.success is False for event in events):
            return "failure"
        return "success"


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
