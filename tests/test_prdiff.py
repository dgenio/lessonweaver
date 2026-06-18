from pathlib import Path

from lessonweaver.models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    RiskLevel,
    Scope,
)
from lessonweaver.prdiff import apply_file_change, plan_coding_agent_change


def _candidate(
    candidate_id: str = "cand-1",
    action_type: RecommendedActionType = RecommendedActionType.GUARDRAIL,
) -> LessonCandidate:
    return LessonCandidate(
        id=candidate_id,
        summary="Inspect diffs before PR review",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="Agent approved a PR without inspecting the diff.",
        proposed_lesson="Inspect changed files before drawing review conclusions.",
        confidence=0.72,
        recommended_action_type=action_type,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        status=LessonStatus.APPROVED,
        owner="team-ai",
        approved_by="reviewer",
    )


def test_plan_coding_agent_change_previews_new_file_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"

    change = plan_coding_agent_change(_candidate(), target)

    assert change.changed is True
    assert change.path == target
    assert not target.exists()
    assert f"+++ b/{target}" in change.diff
    assert "# Guardrail: Inspect diffs before PR review" in change.merged
    assert "Evidence IDs: trace-1 / event-1" in change.merged
    assert "Owner: team-ai" in change.merged


def test_apply_file_change_writes_and_replanning_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    candidate = _candidate()

    first = plan_coding_agent_change(candidate, target)
    apply_file_change(first)
    second = plan_coding_agent_change(candidate, target)
    apply_file_change(second)

    content = target.read_text(encoding="utf-8")
    assert second.changed is False
    assert second.diff == ""
    assert content.count("lessonweaver:begin skill_id=cand-1") == 1


def test_plan_coding_agent_change_preserves_manual_content(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("# House rules\n\nKeep PRs small.\n", encoding="utf-8")

    change = plan_coding_agent_change(_candidate(), target)
    apply_file_change(change)

    content = target.read_text(encoding="utf-8")
    assert "Keep PRs small." in content
    assert "lessonweaver:begin skill_id=cand-1" in content
