from datetime import datetime, timezone

import pytest

from lessonweaver.eval_companion import export_eval_companion_pack
from lessonweaver.models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    RiskLevel,
    Scope,
)
from lessonweaver.privacy import SimpleRedactor
from lessonweaver.sanitization import redaction_marker

NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _candidate(
    candidate_id: str,
    action_type: RecommendedActionType,
    *,
    status: LessonStatus = LessonStatus.APPROVED,
) -> LessonCandidate:
    return LessonCandidate(
        id=candidate_id,
        summary=f"{action_type.value} candidate",
        evidence_trace_ids=[f"trace-{candidate_id}"],
        evidence_event_ids=[f"event-{candidate_id}"],
        observed_problem="The agent repeated a reviewed failure.",
        proposed_lesson="Add a falsifiable check for the failure pattern.",
        confidence=0.74,
        recommended_action_type=action_type,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        status=status,
        approved_by="reviewer",
        created_at=NOW,
        updated_at=NOW,
    )


def test_eval_companion_pack_exports_eval_guardrail_and_workflow_artifacts() -> None:
    pack = export_eval_companion_pack(
        [
            _candidate("eval-1", RecommendedActionType.EVAL),
            _candidate("guardrail-1", RecommendedActionType.GUARDRAIL),
            _candidate("workflow-1", RecommendedActionType.WORKFLOW_CHANGE),
        ]
    )

    assert set(pack) == {
        "README.md",
        "evals/eval-1.md",
        "guardrails/guardrail-1.md",
        "workflows/workflow-1.md",
        "metadata.json",
    }
    assert "# LessonWeaver eval companion pack" in pack["README.md"]
    assert "does not execute evals" in pack["README.md"]
    assert pack["evals/eval-1.md"].startswith("# Eval: eval candidate\n")
    assert pack["guardrails/guardrail-1.md"].startswith("# Guardrail: guardrail candidate\n")
    assert pack["workflows/workflow-1.md"].startswith(
        "# Workflow recommendation: workflow_change candidate\n"
    )


def test_eval_companion_pack_metadata_preserves_governance_and_evidence() -> None:
    pack = export_eval_companion_pack([_candidate("eval-1", RecommendedActionType.EVAL)])

    metadata = pack["metadata.json"]

    assert '"candidate_id": "eval-1"' in metadata
    assert '"action_type": "eval"' in metadata
    assert '"status": "approved"' in metadata
    assert '"approved_by": "reviewer"' in metadata
    assert '"risk_level": "medium"' in metadata
    assert '"scope": "project"' in metadata
    assert '"evidence_trace_ids": [' in metadata
    assert '"trace-eval-1"' in metadata
    assert '"evidence_event_ids": [' in metadata
    assert '"event-eval-1"' in metadata


def test_eval_companion_pack_rejects_unreviewed_or_skill_candidates() -> None:
    with pytest.raises(ValueError, match="approved"):
        export_eval_companion_pack(
            [_candidate("draft-1", RecommendedActionType.EVAL, status=LessonStatus.CANDIDATE)]
        )
    with pytest.raises(ValueError, match="eval companion"):
        export_eval_companion_pack([_candidate("skill-1", RecommendedActionType.SKILL)])


def test_eval_companion_pack_rejects_unsafe_candidate_ids() -> None:
    with pytest.raises(ValueError, match="unsafe candidate id"):
        export_eval_companion_pack([_candidate("../outside", RecommendedActionType.EVAL)])


def test_eval_companion_pack_redacts_metadata_readme_and_paths() -> None:
    candidate = _candidate("eval-admin@example.com", RecommendedActionType.EVAL)
    candidate.approved_by = "reviewer@example.com"
    candidate.evidence_trace_ids = ["trace-Bearer abcdefghijklmnopqrstuvwxyz123456"]
    candidate.evidence_event_ids = ["event-admin@example.com"]

    pack = export_eval_companion_pack([candidate], redactor=SimpleRedactor())

    serialized = "\n".join([*pack.keys(), pack["README.md"], pack["metadata.json"]])
    assert "admin@example.com" not in serialized
    assert "reviewer@example.com" not in serialized
    assert "Bearer abcdefghijklmnopqrstuvwxyz123456" not in serialized
    assert redaction_marker("email") in serialized
    assert f"evals/{redaction_marker('email')}.md" in pack


def test_eval_companion_pack_rejects_redacted_path_collisions() -> None:
    with pytest.raises(ValueError, match="duplicate eval companion artifact path"):
        export_eval_companion_pack(
            [
                _candidate("admin@example.com", RecommendedActionType.EVAL),
                _candidate("reviewer@example.com", RecommendedActionType.EVAL),
            ],
            redactor=SimpleRedactor(),
        )
