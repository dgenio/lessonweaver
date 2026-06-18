"""PR-ready local file changes for reviewed lesson artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .export import (
    export_eval_spec_markdown,
    export_guardrail_rule_markdown,
    export_workflow_recommendation_markdown,
)
from .filemerge import diff_managed_file, merge_managed_block
from .models import LessonCandidate, LessonStatus, RecommendedActionType
from .privacy import SimpleRedactor


@dataclass(slots=True)
class FileChange:
    path: Path
    existing: str
    merged: str
    diff: str
    changed: bool


def _metadata_block(candidate: LessonCandidate) -> str:
    evidence = " / ".join([*candidate.evidence_trace_ids, *candidate.evidence_event_ids])
    lines = [
        "## Review metadata",
        f"- Candidate: {candidate.id}",
        f"- Action type: {candidate.recommended_action_type.value}",
        f"- Scope: {candidate.scope.value}",
        f"- Risk: {candidate.risk_level.value}",
        f"- Confidence: {candidate.confidence:.2f}",
        f"- Evidence IDs: {evidence or 'none'}",
    ]
    if candidate.owner:
        lines.append(f"- Owner: {candidate.owner}")
    if candidate.approved_by:
        lines.append(f"- Approved by: {candidate.approved_by}")
    if candidate.expires_at is not None:
        lines.append(f"- Expires at: {candidate.expires_at.isoformat()}")
    return "\n".join(lines)


def _artifact_content(candidate: LessonCandidate, *, redact: bool = True) -> str:
    if candidate.status is not LessonStatus.APPROVED:
        raise ValueError(
            f"candidate '{candidate.id}' is not approved (status: {candidate.status.value})"
        )
    redactor = SimpleRedactor() if redact else None
    if candidate.recommended_action_type is RecommendedActionType.EVAL:
        artifact = export_eval_spec_markdown(candidate, redactor=redactor)
    elif candidate.recommended_action_type is RecommendedActionType.GUARDRAIL:
        artifact = export_guardrail_rule_markdown(candidate, redactor=redactor)
    elif candidate.recommended_action_type is RecommendedActionType.WORKFLOW_CHANGE:
        artifact = export_workflow_recommendation_markdown(candidate, redactor=redactor)
    else:
        raise ValueError(
            f"candidate '{candidate.id}' cannot be rendered as a coding-agent file change "
            f"(action type: {candidate.recommended_action_type.value})"
        )
    return f"{_metadata_block(candidate)}\n\n{artifact}".strip() + "\n"


def plan_coding_agent_change(
    candidate: LessonCandidate, path: str | Path, *, redact: bool = True
) -> FileChange:
    """Plan an idempotent coding-agent instruction file change for a candidate."""
    target = Path(path)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    merged = merge_managed_block(
        existing, _artifact_content(candidate, redact=redact), candidate.id
    )
    changed = merged != existing
    diff = diff_managed_file(existing, merged, str(target)) if changed else ""
    return FileChange(path=target, existing=existing, merged=merged, diff=diff, changed=changed)


def apply_file_change(change: FileChange) -> bool:
    """Write a planned file change. Returns whether a write occurred."""
    if not change.changed:
        return False
    change.path.parent.mkdir(parents=True, exist_ok=True)
    change.path.write_text(change.merged, encoding="utf-8")
    return True
