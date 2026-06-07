"""Tests for explainable load diagnostics."""

from lessonweaver.diagnostics import explain_load
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.retrieval import RetrievalQuery


def _skill(
    skill_id: str,
    *,
    name: str = "PR Diff First",
    applies_when: list[str] | None = None,
    status: SkillStatus = SkillStatus.ACTIVE,
    risk_level: RiskLevel = RiskLevel.LOW,
) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name=name,
        description="Inspect changed files before reviewing pull requests.",
        applies_when=applies_when or ["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Inspect changed files first"],
        anti_patterns=["title-only approval"],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=risk_level,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=status,
    )


def _query(task: str = "Review this pull request", **kwargs: object) -> RetrievalQuery:
    return RetrievalQuery(task=task, **kwargs)  # type: ignore[arg-type]


def test_explain_load_reports_loaded_skill_with_reason_and_budget() -> None:
    diag = explain_load([_skill("skill-1")], _query())
    assert [item.skill_id for item in diag.loaded] == ["skill-1"]
    assert diag.loaded[0].score > 0
    assert "matched tokens" in diag.loaded[0].match_reason
    assert diag.budget.used_chars > 0
    assert diag.budget.remaining_chars == diag.budget.budget_chars - diag.budget.used_chars


def test_explain_load_skips_non_active_skill() -> None:
    diag = explain_load([_skill("skill-1", status=SkillStatus.DRAFT)], _query())
    assert diag.loaded == []
    skipped = {item.skill_id: item.reason for item in diag.skipped}
    assert skipped["skill-1"] == "status_not_active"


def test_explain_load_skips_irrelevant_skill() -> None:
    diag = explain_load(
        [_skill("skill-1", applies_when=["writing database migrations"])],
        _query("Summarize meeting notes"),
    )
    assert diag.loaded == []
    skipped = {item.skill_id: item.reason for item in diag.skipped}
    assert skipped["skill-1"] == "no_match"


def test_explain_load_skips_skill_above_risk_ceiling() -> None:
    diag = explain_load([_skill("skill-1", risk_level=RiskLevel.HIGH)], _query(risk_level="low"))
    skipped = {item.skill_id: item.reason for item in diag.skipped}
    assert skipped["skill-1"] == "risk_above_threshold"


def test_explain_load_marks_budget_dropped_skill() -> None:
    diag = explain_load([_skill("skill-1")], _query(), budget_chars=5)
    assert diag.loaded == []
    skipped = {item.skill_id: item.reason for item in diag.skipped}
    assert skipped["skill-1"] == "omitted_budget"


def test_explain_load_flags_overlap_among_loaded_skills() -> None:
    skills = [
        _skill("skill-1", name="Diff First"),
        _skill("skill-2", name="Inspect Diffs"),
    ]
    diag = explain_load(skills, _query())
    assert {item.skill_id for item in diag.loaded} == {"skill-1", "skill-2"}
    assert any(finding.finding_type == "overlap" for finding in diag.overlaps)


def test_explain_load_includes_snippet_only_when_requested() -> None:
    skills = [_skill("skill-1")]
    assert explain_load(skills, _query()).snippet == ""
    assert explain_load(skills, _query(), include_snippet=True).snippet != ""
