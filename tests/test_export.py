import json
from datetime import datetime, timezone

from lessonweaver.export import (
    export_copilot_instruction_fragment,
    export_operational_lesson_markdown,
    export_skillcard_json,
    export_skillcard_markdown,
)
from lessonweaver.models import (
    LessonStatus,
    OperationalLesson,
    RecommendedActionType,
    RiskLevel,
    Scope,
    SkillCard,
)
from lessonweaver.privacy import SimpleRedactor

NOW = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)


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
        created_at=NOW,
        updated_at=NOW,
    )


def test_export_skillcard_markdown_snapshot() -> None:
    rendered = export_skillcard_markdown(_make_skill())
    assert rendered == (
        "# PR Diff First\n"
        "\n"
        "## Description\n"
        "Inspect diff before review.\n"
        "\n"
        "## Use when\n"
        "- Reviewing PRs\n"
        "\n"
        "## Do not use when\n"
        "- No code changes\n"
        "\n"
        "## Instructions\n"
        "- Inspect changed files first\n"
        "\n"
        "## Anti-patterns\n"
        "- Approve from title only\n"
        "\n"
        "## Evidence\n"
        "- trace: trace-gh-pr-review-001\n"
        "\n"
        "## Governance\n"
        "- Confidence: 0.80\n"
        "- Risk: medium\n"
        "- Scope: project\n"
        "- Version: 0.1.0\n"
        "- Status: draft\n"
        "- Sensitivity: internal\n"
    )


def test_export_skillcard_markdown_suppresses_empty_sections() -> None:
    skill = _make_skill()
    skill.does_not_apply_when = []
    skill.anti_patterns = []
    skill.evidence_trace_ids = []
    rendered = export_skillcard_markdown(skill)
    assert "## Do not use when" not in rendered
    assert "## Anti-patterns" not in rendered
    assert "## Evidence" not in rendered


def test_export_skillcard_json() -> None:
    rendered = export_skillcard_json(_make_skill())
    data = json.loads(rendered)
    assert data["name"] == "PR Diff First"
    assert data["risk_level"] == "medium"
    assert data["scope"] == "project"
    assert data["sensitivity"] == "internal"


def test_export_copilot_instruction_fragment() -> None:
    rendered = export_copilot_instruction_fragment(_make_skill())
    assert "Skill: PR Diff First" in rendered
    assert "Use when:" in rendered
    assert "Reviewing PRs" in rendered


def test_export_operational_lesson_markdown() -> None:
    lesson = OperationalLesson(
        lesson_id="lesson-1",
        candidate_id="candidate-1",
        title="Policy Version Check",
        summary="Verify the current policy before answering.",
        instructions=["Check the active policy version."],
        applies_when=["Answering policy questions"],
        does_not_apply_when=["No policy data is involved"],
        anti_patterns=[],
        risk_level=RiskLevel.HIGH,
        scope=Scope.PROJECT,
        recommended_action_type=RecommendedActionType.SKILL,
        evidence_trace_ids=["trace-chatbot-policy-001"],
        evidence_event_ids=["p3"],
        confidence=0.82,
        status=LessonStatus.APPROVED,
        created_at=NOW,
    )
    rendered = export_operational_lesson_markdown(lesson)
    assert "# Operational Lesson: Policy Version Check" in rendered
    assert "- trace: trace-chatbot-policy-001" in rendered
    assert "- Action type: skill" in rendered


def test_export_redactor_integration() -> None:
    skill = _make_skill()
    skill.description = "Contact admin@example.com with api_key: sk-test-value"
    rendered = export_skillcard_markdown(skill, redactor=SimpleRedactor())
    assert "admin@example.com" not in rendered
    assert "api_key" not in rendered
    assert "[REDACTED]" in rendered
