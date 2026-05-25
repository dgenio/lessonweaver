import json

from lessonweaver.export import (
    export_copilot_instruction_fragment,
    export_skillcard_json,
    export_skillcard_markdown,
)
from lessonweaver.models import RiskLevel, Scope, SkillCard


def _make_skill() -> SkillCard:
    return SkillCard(
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


def test_export_skillcard_markdown() -> None:
    rendered = export_skillcard_markdown(_make_skill())
    assert "# PR Diff First" in rendered
    assert "## Instructions" in rendered
    assert "trace-gh-pr-review-001" in rendered


def test_export_skillcard_json() -> None:
    rendered = export_skillcard_json(_make_skill())
    data = json.loads(rendered)
    assert data["name"] == "PR Diff First"
    assert data["risk_level"] == "medium"
    assert data["scope"] == "project"


def test_export_copilot_instruction_fragment() -> None:
    rendered = export_copilot_instruction_fragment(_make_skill())
    assert "Skill: PR Diff First" in rendered
    assert "Use when:" in rendered
    assert "Reviewing PRs" in rendered
