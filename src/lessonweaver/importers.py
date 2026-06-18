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


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


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


class LangfuseTraceImporter:
    """Importer for exported Langfuse trace/observation/score JSON."""

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        if "langfuse" in str(source.get("schema", "")).lower():
            return True
        return str(source.get("source", "")).lower() == "langfuse" and (
            "trace" in source or "observations" in source
        )

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        if not self.can_import(source):
            raise ValueError("Unrecognized Langfuse export payload.")
        trace = source.get("trace")
        trace_data = trace if isinstance(trace, dict) else {}
        trace_id = str(
            trace_data.get("id") or source.get("trace_id") or source.get("id") or ""
        ).strip()
        if not trace_id:
            raise ValueError("Langfuse export missing a trace id.")

        observations = source.get("observations", [])
        if not isinstance(observations, list):
            raise ValueError("Langfuse export 'observations' must be a list.")
        scores = source.get("scores", [])
        if not isinstance(scores, list):
            raise ValueError("Langfuse export 'scores' must be a list.")

        events: list[TraceEvent] = []
        trace_input = trace_data.get("input") or source.get("input")
        if trace_input is not None:
            events.append(
                TraceEvent(
                    id=f"{trace_id}-input",
                    type=TraceEventType.USER_MESSAGE,
                    content=_stringify(trace_input),
                )
            )
        for index, observation in enumerate(observations, start=1):
            if not isinstance(observation, dict):
                raise ValueError(f"Langfuse observation {index} must be an object.")
            events.append(_langfuse_observation_event(trace_id, index, observation))
        for index, score in enumerate(scores, start=1):
            if not isinstance(score, dict):
                raise ValueError(f"Langfuse score {index} must be an object.")
            events.extend(_score_events("langfuse", trace_id, index, score))

        return TraceBundle(
            trace_id=trace_id,
            source="langfuse",
            task=str(trace_data.get("name") or source.get("name") or "Langfuse trace"),
            events=events,
            outcome=_outcome_from_events(events),
            metadata={"langfuse": {"trace": _dict_or_empty(trace_data.get("metadata"))}},
        )


class LangSmithTraceImporter:
    """Importer for exported LangSmith run JSON."""

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        if "langsmith" in str(source.get("schema", "")).lower():
            return True
        return str(source.get("source", "")).lower() == "langsmith" and "runs" in source

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        if not self.can_import(source):
            raise ValueError("Unrecognized LangSmith run export payload.")
        runs = source.get("runs")
        if not isinstance(runs, list):
            raise ValueError("LangSmith export 'runs' must be a list.")
        if not runs:
            raise ValueError("LangSmith export requires at least one run.")

        run_objects: list[dict[str, Any]] = []
        for index, run in enumerate(runs, start=1):
            if not isinstance(run, dict):
                raise ValueError(f"LangSmith run {index} must be an object.")
            run_objects.append(run)
        run_objects.sort(
            key=lambda item: str(item.get("dotted_order") or item.get("start_time") or "")
        )

        root = run_objects[0]
        trace_id = str(
            root.get("trace_id") or root.get("id") or source.get("trace_id") or ""
        ).strip()
        if not trace_id:
            raise ValueError("LangSmith export missing a trace id.")

        events = [
            _langsmith_run_event(trace_id, index, run)
            for index, run in enumerate(run_objects, start=1)
        ]
        feedback_items = source.get("feedback", [])
        if not isinstance(feedback_items, list):
            raise ValueError("LangSmith export 'feedback' must be a list.")
        for index, feedback in enumerate(feedback_items, start=1):
            if not isinstance(feedback, dict):
                raise ValueError(f"LangSmith feedback {index} must be an object.")
            events.extend(_score_events("langsmith", trace_id, index, feedback))

        return TraceBundle(
            trace_id=trace_id,
            source="langsmith",
            task=str(root.get("name") or "LangSmith run"),
            events=events,
            outcome=_outcome_from_events(events),
            metadata={"langsmith": {"run_count": len(run_objects)}},
        )


def _langfuse_observation_event(
    trace_id: str, index: int, observation: dict[str, Any]
) -> TraceEvent:
    observation_type = str(observation.get("type") or "").upper()
    level = str(observation.get("level") or "").upper()
    status_message = observation.get("status_message")
    event_type = (
        TraceEventType.MODEL_CALL if observation_type == "GENERATION" else TraceEventType.TOOL_CALL
    )
    status = None
    if level == "ERROR" or status_message:
        event_type = TraceEventType.ERROR
        status = "failed"
    content = (
        status_message
        or observation.get("output")
        or observation.get("input")
        or observation.get("name")
    )
    return TraceEvent(
        id=str(observation.get("id") or f"{trace_id}-observation-{index}"),
        type=event_type,
        content=_stringify(content),
        status=status,
        success=False if status == "failed" else None,
        metadata={
            "langfuse": {
                "observation_type": observation_type or None,
                **_dict_or_empty(observation.get("metadata")),
            }
        },
    )


def _langsmith_run_event(trace_id: str, index: int, run: dict[str, Any]) -> TraceEvent:
    run_type = str(run.get("run_type") or "").lower()
    status = str(run.get("status") or "").lower()
    error = run.get("error")
    event_type = TraceEventType.WORKFLOW_STEP
    if run_type == "llm":
        event_type = TraceEventType.MODEL_CALL
    elif run_type == "tool":
        event_type = TraceEventType.TOOL_CALL
    if error or status == "error":
        event_type = TraceEventType.ERROR
    content = error or run.get("outputs") or run.get("inputs") or run.get("name")
    return TraceEvent(
        id=str(run.get("id") or f"{trace_id}-run-{index}"),
        type=event_type,
        content=_stringify(content),
        status="failed" if event_type is TraceEventType.ERROR else None,
        success=False if event_type is TraceEventType.ERROR else None,
        metadata={
            "langsmith": {
                "run_type": run_type or None,
                "extra": _dict_or_empty(run.get("extra")),
            }
        },
    )


def _score_events(
    platform: str, trace_id: str, index: int, score: dict[str, Any]
) -> list[TraceEvent]:
    value = score.get("value", score.get("score"))
    comment = score.get("comment")
    name = str(score.get("name") or score.get("key") or "feedback")
    events = [
        TraceEvent(
            id=str(score.get("id") or f"{trace_id}-{platform}-score-{index}"),
            type=TraceEventType.EVALUATION_RESULT,
            content=_stringify({"name": name, "value": value, "comment": comment}),
            status="failed" if _is_negative_score(value) else "passed",
            success=not _is_negative_score(value),
            metadata={platform: {key: value for key, value in score.items() if key != "comment"}},
        )
    ]
    if comment:
        events.append(
            TraceEvent(
                id=f"{trace_id}-{platform}-feedback-{index}",
                type=TraceEventType.HUMAN_CORRECTION,
                content=str(comment),
                metadata={platform: {"score_name": name}},
            )
        )
    return events


def _is_negative_score(value: Any) -> bool:
    if isinstance(value, bool):
        return value is False
    if isinstance(value, int | float):
        return value <= 0
    if isinstance(value, str):
        return value.lower() in {"0", "false", "fail", "failed", "negative"}
    return False


def _outcome_from_events(events: list[TraceEvent]) -> str:
    if any(event.type is TraceEventType.ERROR for event in events):
        return "failure"
    if any(event.status == "failed" for event in events):
        return "failure"
    return "success"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


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
