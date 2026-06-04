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
