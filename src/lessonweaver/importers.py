"""Trace import protocol and built-in importers.

This module formalizes how an external payload becomes a :class:`TraceBundle`
(issue #52). Two dependency-free importers ship in the core:

* :class:`DictTraceImporter` — the canonical lessonweaver JSON trace shape, the
  format :func:`lessonweaver.traces.load_trace_bundle` reads. This makes the
  existing loader a special case of the :class:`TraceImporter` protocol.
* :class:`FailureCaseImporter` — a governed path that turns a replayable
  *failure case* artifact into a trace bundle so the normal
  ``detect -> review -> approve -> export`` loop applies to it (issue #82).
* :class:`VibeguardReportImporter` — a first-class, dependency-free importer
  for VibeGuard ArtifactSafetyReport/native report JSON that preserves finding
  provenance and produces candidates only for repeated categories (issue #132).

Lightweight example adapters for sibling single-run outputs still live in
``examples/interop_adapters/``. See ``docs/adapters.md`` for the normalization
contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .detection import LessonDetector
from .models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    RiskLevel,
    Scope,
    TraceBundle,
    TraceEvent,
    TraceEventType,
)
from .traces import validate_trace_dict

# Provenance key stamped onto a TraceBundle (and propagated onto candidates) so a
# reviewer can always trace a lesson back to the failure case it came from.
FAILURE_CASE_PROVENANCE_KEY = "failure_case"
VIBEGUARD_PROVENANCE_KEY = "vibeguard"

_SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


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


@dataclass(slots=True)
class VibeguardImportResult:
    """Summary returned when importing one or more VibeGuard reports."""

    candidates: list[LessonCandidate]
    one_off_findings: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "one_off_findings": self.one_off_findings,
        }


class VibeguardReportImporter:
    """Importer for VibeGuard ArtifactSafetyReport-style JSON payloads.

    The importer accepts the Weaver Stack ``ArtifactSafetyReport`` shape used by
    VibeGuard's ``--weaver`` output, plus native VibeGuard-style reports that
    carry a top-level ``findings`` list. It keeps the mapping deterministic and
    dependency-free: no VibeGuard package import is required.
    """

    _SCHEMA_MARKERS = ("artifact-safety-report", "artifactsafetyreport")

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        schema = str(source.get("schema") or source.get("type") or "").lower()
        if any(marker in schema for marker in self._SCHEMA_MARKERS):
            return True
        if str(source.get("tool", "")).lower() == "vibeguard" and "findings" in source:
            return True
        return "findings" in source and ("report_id" in source or "source_refs" in source)

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        if not self.can_import(source):
            raise ValueError("Unrecognized VibeGuard report: expected a report with findings.")
        findings = _vibeguard_findings(source)
        if not findings:
            raise ValueError("VibeGuard report contains no findings.")

        report_id = _vibeguard_report_id(source)
        events = [
            TraceEvent(
                id=finding["finding_id"],
                type=TraceEventType.EVALUATION_RESULT,
                content=finding.get("message") or finding.get("remediation") or finding["category"],
                status="failed",
                metadata=finding,
            )
            for finding in findings
        ]
        return TraceBundle(
            trace_id=report_id,
            source="vibeguard",
            task=str(source.get("task") or "Review VibeGuard artifact safety findings"),
            events=events,
            outcome="failure",
            metadata={
                VIBEGUARD_PROVENANCE_KEY: {
                    "report_id": report_id,
                    "source_refs": _source_refs(source),
                }
            },
        )


def candidates_from_vibeguard_reports(sources: list[dict[str, Any]]) -> VibeguardImportResult:
    """Create review candidates from repeated VibeGuard finding categories.

    Findings are deduplicated by fingerprint within a report/PR context. A
    category becomes a candidate only when it appears across at least two
    distinct contexts; one-off categories are returned in the summary but are
    not promoted to lesson candidates.
    """

    importer = VibeguardReportImporter()
    by_category: dict[str, list[dict[str, Any]]] = {}
    seen_in_context: set[tuple[str, str]] = set()

    for source in sources:
        importer.import_trace(source)  # validates the report shape.
        report_id = _vibeguard_report_id(source)
        context_id = _vibeguard_context_id(source)
        for finding in _vibeguard_findings(source):
            fingerprint = finding["fingerprint"]
            dedupe_key = (context_id, fingerprint)
            if dedupe_key in seen_in_context:
                continue
            seen_in_context.add(dedupe_key)
            enriched = dict(finding)
            enriched["report_id"] = report_id
            enriched["context_id"] = context_id
            enriched["source_refs"] = _combine_source_refs(
                _source_refs(source), finding.get("source_refs", [])
            )
            by_category.setdefault(enriched["category"], []).append(enriched)

    candidates: list[LessonCandidate] = []
    one_off_findings: list[dict[str, Any]] = []
    for category, findings in by_category.items():
        context_ids = {finding["context_id"] for finding in findings}
        if len(context_ids) < 2:
            one_off_findings.append(_one_off_summary(category, findings))
            continue
        candidates.append(_vibeguard_candidate(category, findings, context_ids))

    return VibeguardImportResult(candidates=candidates, one_off_findings=one_off_findings)


def _vibeguard_report_id(source: dict[str, Any]) -> str:
    return str(source.get("report_id") or source.get("id") or "vibeguard-report").strip()


def _vibeguard_context_id(source: dict[str, Any]) -> str:
    for ref in _source_refs(source):
        if ref.get("type") in {"pull_request", "pr", "merge_request"} and ref.get("id"):
            return str(ref["id"])
    context = source.get("pr") or source.get("pull_request") or source.get("context")
    if isinstance(context, dict):
        for key in ("id", "number", "url"):
            if context.get(key) is not None:
                return str(context[key])
    return _vibeguard_report_id(source)


def _vibeguard_findings(source: dict[str, Any]) -> list[dict[str, Any]]:
    raw_findings = source.get("findings")
    if not isinstance(raw_findings, list):
        raise ValueError("VibeGuard report missing a 'findings' list.")

    findings: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_findings, start=1):
        if not isinstance(raw, dict):
            raise ValueError("VibeGuard finding must be a JSON object.")
        finding_id = str(raw.get("finding_id") or raw.get("id") or "").strip()
        if not finding_id:
            raise ValueError("VibeGuard finding missing a non-empty 'finding_id' (or 'id').")
        category = str(raw.get("category") or raw.get("rule") or "uncategorized").strip()
        fingerprint = str(raw.get("fingerprint") or finding_id or f"finding-{index}").strip()
        findings.append(
            {
                "finding_id": finding_id,
                "rule": raw.get("rule") or raw.get("rule_id"),
                "category": category,
                "severity": str(raw.get("severity") or "medium").lower(),
                "path": raw.get("path") or raw.get("file"),
                "fingerprint": fingerprint,
                "remediation": raw.get("remediation") or raw.get("recommendation"),
                "message": raw.get("message") or raw.get("summary"),
                "source_refs": _source_refs(raw),
            }
        )
    return findings


def _source_refs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    refs = payload.get("source_refs") or payload.get("sourceRefs") or []
    if not isinstance(refs, list):
        return []
    return [dict(ref) for ref in refs if isinstance(ref, dict)]


def _combine_source_refs(
    report_refs: list[dict[str, Any]], finding_refs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    for ref in [*report_refs, *finding_refs]:
        key = tuple(sorted(ref.items()))
        if key not in seen:
            seen.add(key)
            combined.append(ref)
    return combined


def _one_off_summary(category: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "category": category,
        "finding_count": len(findings),
        "context_ids": sorted({finding["context_id"] for finding in findings}),
        "findings": findings,
        "reason": "category did not recur across distinct PR/report contexts",
    }


def _vibeguard_candidate(
    category: str,
    findings: list[dict[str, Any]],
    context_ids: set[str],
) -> LessonCandidate:
    worst = max(_SEVERITY_ORDER.get(str(finding["severity"]).lower(), 2) for finding in findings)
    risk = RiskLevel.HIGH if worst >= _SEVERITY_ORDER["high"] else RiskLevel.MEDIUM
    report_ids = sorted({finding["report_id"] for finding in findings})
    event_ids = [finding["finding_id"] for finding in findings]
    category_label = category.replace("_", " ")
    return LessonCandidate(
        id=f"vibeguard-{_slug(category)}-recurring",
        summary=f"Recurring VibeGuard {category_label} findings across reviewed PRs.",
        evidence_trace_ids=report_ids,
        evidence_event_ids=event_ids,
        observed_problem=(
            f"VibeGuard reported {len(findings)} deduplicated {category_label} finding(s) "
            f"across {len(context_ids)} distinct PR/report contexts."
        ),
        proposed_lesson=(
            f"Add a reviewed guardrail or workflow check for recurring VibeGuard "
            f"{category_label} findings before merging agent-generated changes."
        ),
        confidence=0.7,
        recommended_action_type=RecommendedActionType.GUARDRAIL,
        risk_level=risk,
        scope=Scope.PROJECT,
        evidence_strength=0.75,
        evidence_summary=(
            "Repeated VibeGuard findings across distinct contexts are stronger evidence than "
            "a one-off report; duplicate fingerprints inside a single context are counted once."
        ),
        status=LessonStatus.NEEDS_REVIEW,
        metadata={
            VIBEGUARD_PROVENANCE_KEY: {
                "category": category,
                "occurrence_count": len(findings),
                "distinct_context_count": len(context_ids),
                "context_ids": sorted(context_ids),
                "findings": findings,
            }
        },
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "finding"
