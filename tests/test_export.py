import json
from datetime import datetime, timezone

from lessonweaver.export import (
    export_agents_md_fragment,
    export_claude_md_snippet,
    export_claude_rule_fragment,
    export_claude_skill_md,
    export_codex_skill_directory,
    export_copilot_instruction_fragment,
    export_copilot_path_instruction,
    export_copilot_repo_instruction,
    export_dox_agents_md,
    export_eval_spec_markdown,
    export_guardrail_rule_markdown,
    export_operational_lesson_markdown,
    export_skillcard_json,
    export_skillcard_markdown,
    export_workflow_recommendation_markdown,
)
from lessonweaver.models import (
    LessonCandidate,
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


def _make_candidate(
    action_type: RecommendedActionType = RecommendedActionType.EVAL,
) -> LessonCandidate:
    return LessonCandidate(
        id="cand-1",
        summary="Inspect diffs before PR review",
        evidence_trace_ids=["trace-gh-pr-review-001"],
        evidence_event_ids=["e1"],
        observed_problem="Agent approved a PR without inspecting the diff.",
        proposed_lesson="Inspect changed files before drawing review conclusions.",
        confidence=0.62,
        recommended_action_type=action_type,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        status=LessonStatus.APPROVED,
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
    assert "sk-test-value" not in rendered
    assert "[REDACTED by email]" in rendered
    assert "[REDACTED by api_key]" in rendered


def test_export_agents_md_fragment_snapshot() -> None:
    rendered = export_agents_md_fragment(_make_skill())
    assert rendered == (
        "<!-- lessonweaver skill_id=skill-1 confidence=0.80 -->\n"
        "### PR Diff First\n"
        "\n"
        "**When to apply:** Reviewing PRs\n"
        "**Do not apply when:** No code changes\n"
        "\n"
        "- Inspect changed files first\n"
    )


def test_export_agents_md_fragment_suppresses_empty_negative() -> None:
    skill = _make_skill()
    skill.does_not_apply_when = []
    rendered = export_agents_md_fragment(skill)
    assert "Do not apply when" not in rendered


def test_export_dox_agents_md_profile_snapshot() -> None:
    rendered = export_dox_agents_md(_make_skill())
    assert rendered == (
        "<!-- lessonweaver profile=dox-agents-md skill_id=skill-1 "
        "version=0.1.0 confidence=0.80 -->\n"
        "# PR Diff First\n"
        "\n"
        "## Purpose\n"
        "Inspect diff before review.\n"
        "\n"
        "## Ownership\n"
        "- Source: lessonweaver reviewed skill `skill-1`\n"
        "- Scope: project\n"
        "- Risk: medium\n"
        "- Status: draft\n"
        "- Human review: required before export; do not auto-activate unreviewed lessons.\n"
        "\n"
        "## Local Contracts\n"
        "- Apply when: Reviewing PRs\n"
        "- Do not apply when: No code changes\n"
        "\n"
        "## Work Guidance\n"
        "- Inspect changed files first\n"
        "\n"
        "## Verification\n"
        "- Avoid: Approve from title only\n"
        "- Evidence trace: trace-gh-pr-review-001\n"
        "\n"
        "## Child Instruction Index\n"
        "- Add child `AGENTS.md` files for narrower directory contracts when this guidance "
        "does not apply repo-wide.\n"
    )


def test_export_copilot_repo_instruction_snapshot() -> None:
    rendered = export_copilot_repo_instruction(_make_skill())
    assert rendered == (
        "<!-- lessonweaver skill_id=skill-1 version=0.1.0 -->\n"
        "## PR Diff First\n"
        "\n"
        "Inspect diff before review.\n"
        "\n"
        "**Apply when:** Reviewing PRs\n"
        "**Do not apply when:** No code changes\n"
        "\n"
        "**Instructions:**\n"
        "- Inspect changed files first\n"
    )


def test_export_copilot_path_instruction_glob_in_frontmatter() -> None:
    rendered = export_copilot_path_instruction(_make_skill(), "**/*.py")
    assert rendered.startswith('---\napplyTo: "**/*.py"\n---\n')
    assert "## When to apply" in rendered
    assert "## When not to apply" in rendered
    assert "## Required behaviors" in rendered


def test_export_copilot_path_instruction_default_glob_and_suppression() -> None:
    skill = _make_skill()
    skill.does_not_apply_when = []
    rendered = export_copilot_path_instruction(skill)
    assert 'applyTo: "**"' in rendered
    assert "## When not to apply" not in rendered


def test_export_copilot_path_instruction_escapes_unsafe_glob() -> None:
    rendered = export_copilot_path_instruction(_make_skill(), 'src/"weird"/**')
    assert 'applyTo: "src/\\"weird\\"/**"' in rendered


def test_export_claude_skill_md_snapshot() -> None:
    rendered = export_claude_skill_md(_make_skill())
    assert rendered == (
        "# PR Diff First\n"
        "\n"
        "Inspect diff before review.\n"
        "\n"
        "## When to use\n"
        "- Reviewing PRs\n"
        "\n"
        "## When NOT to use\n"
        "- No code changes\n"
        "\n"
        "## Instructions\n"
        "- Inspect changed files first\n"
        "\n"
        "## Anti-patterns\n"
        "- Approve from title only\n"
        "\n"
        "## Metadata\n"
        "- Confidence: 0.80\n"
        "- Risk: medium\n"
        "- Evidence: trace-gh-pr-review-001\n"
    )


def test_export_claude_skill_md_suppresses_empty_sections() -> None:
    skill = _make_skill()
    skill.anti_patterns = []
    skill.evidence_trace_ids = []
    rendered = export_claude_skill_md(skill)
    assert "## Anti-patterns" not in rendered
    assert "Evidence:" not in rendered
    assert "## Metadata" in rendered


def test_export_claude_rule_fragment() -> None:
    rendered = export_claude_rule_fragment(_make_skill())
    assert rendered == (
        "# Rule: PR Diff First\n"
        "\n"
        "**Applies when:** Reviewing PRs\n"
        "\n"
        "**Do:** Inspect changed files first\n"
        "\n"
        "**Avoid:** Approve from title only"
    )


def test_export_claude_md_snippet() -> None:
    rendered = export_claude_md_snippet(_make_skill())
    assert rendered == (
        "## Operational guidance: PR Diff First\n"
        "\n"
        "Inspect diff before review.\n"
        "\n"
        "When: Reviewing PRs. Required: Inspect changed files first."
    )


def test_export_codex_skill_directory() -> None:
    directory = export_codex_skill_directory(_make_skill())
    assert set(directory) == {"SKILL.md", "metadata.json"}
    assert directory["SKILL.md"].startswith(
        '---\nname: "PR Diff First"\ndescription: "Inspect diff before review."\n---\n'
    )
    assert "## Instructions\n- Inspect changed files first" in directory["SKILL.md"]
    metadata = json.loads(directory["metadata.json"])
    assert metadata["id"] == "skill-1"
    assert metadata["version"] == "0.1.0"
    assert metadata["risk_level"] == "medium"
    assert metadata["confidence"] == 0.8
    assert metadata["evidence_trace_ids"] == ["trace-gh-pr-review-001"]


def test_export_eval_spec_markdown() -> None:
    rendered = export_eval_spec_markdown(_make_candidate())
    assert rendered.startswith("# Eval: Inspect diffs before PR review\n")
    assert "## Test condition\nInspect changed files before drawing review conclusions." in rendered
    assert "- trace: trace-gh-pr-review-001" in rendered


def test_export_guardrail_rule_markdown() -> None:
    rendered = export_guardrail_rule_markdown(_make_candidate(RecommendedActionType.GUARDRAIL))
    assert rendered.startswith("# Guardrail: Inspect diffs before PR review\n")
    assert "## Trigger condition\nAgent approved a PR without inspecting the diff." in rendered
    assert "## Blocked behavior" in rendered
    assert "- trace: trace-gh-pr-review-001" in rendered


def test_export_workflow_recommendation_markdown() -> None:
    rendered = export_workflow_recommendation_markdown(
        _make_candidate(RecommendedActionType.WORKFLOW_CHANGE)
    )
    assert rendered.startswith("# Workflow recommendation: Inspect diffs before PR review\n")
    assert "## Recommended workflow change\n" in rendered
    assert "- trace: trace-gh-pr-review-001" in rendered


def test_export_lesson_redactor_integration() -> None:
    candidate = _make_candidate(RecommendedActionType.GUARDRAIL)
    candidate.observed_problem = "Leaked admin@example.com during review."
    rendered = export_guardrail_rule_markdown(candidate, redactor=SimpleRedactor())
    assert "admin@example.com" not in rendered
    assert "[REDACTED by email]" in rendered
