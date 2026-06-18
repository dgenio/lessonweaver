"""Bundle reviewed eval, guardrail, and workflow recommendations."""

from __future__ import annotations

import json

from .export import (
    Redactor,
    export_eval_spec_markdown,
    export_guardrail_rule_markdown,
    export_workflow_recommendation_markdown,
)
from .models import LessonCandidate, LessonStatus, RecommendedActionType

_EXPORTERS = {
    RecommendedActionType.EVAL: ("evals", export_eval_spec_markdown),
    RecommendedActionType.GUARDRAIL: ("guardrails", export_guardrail_rule_markdown),
    RecommendedActionType.WORKFLOW_CHANGE: ("workflows", export_workflow_recommendation_markdown),
}


def export_eval_companion_pack(
    candidates: list[LessonCandidate],
    *,
    redactor: Redactor | None = None,
) -> dict[str, str]:
    """Export reviewed non-skill candidates as an eval companion pack.

    The pack is intentionally file-content only: callers decide where to write
    it and which eval or guardrail runner consumes it. lessonweaver preserves
    governance metadata and trace evidence; it does not execute these artifacts.
    """

    artifacts: dict[str, str] = {}
    metadata: list[dict[str, object]] = []
    for candidate in candidates:
        _validate_candidate(candidate)
        directory, exporter = _EXPORTERS[candidate.recommended_action_type]
        candidate_id = _redact_text(candidate.id, redactor)
        _validate_candidate_id(candidate_id)
        path = f"{directory}/{candidate_id}.md"
        if path in artifacts:
            raise ValueError(f"duplicate eval companion artifact path: {path!r}")
        artifacts[path] = exporter(candidate, redactor=redactor)
        metadata.append(_metadata(candidate, candidate_id, path, redactor))

    artifacts["README.md"] = _readme(metadata)
    artifacts["metadata.json"] = json.dumps(
        {"artifacts": metadata},
        indent=2,
        sort_keys=True,
    )
    return artifacts


def _validate_candidate(candidate: LessonCandidate) -> None:
    if candidate.status is not LessonStatus.APPROVED:
        raise ValueError(
            f"candidate {candidate.id!r} must be approved before eval companion export"
        )
    if candidate.recommended_action_type not in _EXPORTERS:
        raise ValueError(
            f"candidate {candidate.id!r} has action type "
            f"{candidate.recommended_action_type.value!r}, which is not an eval companion artifact"
        )


def _validate_candidate_id(candidate_id: str) -> None:
    if (
        not candidate_id
        or "/" in candidate_id
        or "\\" in candidate_id
        or ".." in candidate_id
        or "\x00" in candidate_id
    ):
        raise ValueError(f"unsafe candidate id for eval companion export: {candidate_id!r}")


def _redact_text(value: str, redactor: Redactor | None) -> str:
    return redactor.redact(value) if redactor is not None else value


def _redact_optional_text(value: str | None, redactor: Redactor | None) -> str | None:
    if value is None:
        return None
    return _redact_text(value, redactor)


def _redact_list(values: list[str], redactor: Redactor | None) -> list[str]:
    return [_redact_text(value, redactor) for value in values]


def _metadata(
    candidate: LessonCandidate,
    candidate_id: str,
    path: str,
    redactor: Redactor | None,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "path": path,
        "action_type": candidate.recommended_action_type.value,
        "status": candidate.status.value,
        "approved_by": _redact_optional_text(candidate.approved_by, redactor),
        "risk_level": candidate.risk_level.value,
        "scope": candidate.scope.value,
        "confidence": candidate.confidence,
        "evidence_trace_ids": _redact_list(candidate.evidence_trace_ids, redactor),
        "evidence_event_ids": _redact_list(candidate.evidence_event_ids, redactor),
    }


def _readme(metadata: list[dict[str, object]]) -> str:
    lines = [
        "# LessonWeaver eval companion pack",
        "",
        "This pack contains reviewed artifacts derived from trace evidence. It can feed an "
        "eval framework, guardrail system, or workflow backlog, but lessonweaver does not "
        "execute evals or score model output.",
        "",
        "## Artifacts",
        "",
    ]
    for item in metadata:
        lines.append(
            f"- `{item['path']}`: {item['action_type']} from candidate `{item['candidate_id']}`"
        )
    return "\n".join(lines).strip() + "\n"
