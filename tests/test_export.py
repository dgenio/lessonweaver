from lessonweaver.export import export_skillcard_markdown
from lessonweaver.models import RiskLevel, Scope, SkillCard


def test_export_skillcard_markdown() -> None:
    skill = SkillCard(
        id="skill-1",
        name="PR Diff First",
        description="Inspect diff before review.",
        applies_when=["Reviewing PRs"],
        does_not_apply_when=["No code changes"],
        instructions=["Inspect changed files first"],
        anti_patterns=["Approve from title only"],
        evidence_trace_ids=["trace-gh-pr-review-001"],
        confidence=0.8,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        version="0.1.0",
    )
    rendered = export_skillcard_markdown(skill)
    assert "# PR Diff First" in rendered
    assert "## Instructions" in rendered
    assert "trace-gh-pr-review-001" in rendered
