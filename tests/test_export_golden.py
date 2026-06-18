"""Checked-in golden snapshots for every public exporter."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lessonweaver.export import (
    export_agents_md_fragment,
    export_claude_md_snippet,
    export_claude_rule_fragment,
    export_claude_skill_fragment,
    export_claude_skill_md,
    export_codex_skill_directory,
    export_copilot_instruction_fragment,
    export_copilot_path_instruction,
    export_copilot_repo_instruction,
    export_eval_spec_markdown,
    export_guardrail_rule_markdown,
    export_operational_lesson_markdown,
    export_runtime_prompt_snippet,
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

NOW = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
GOLDEN_ROOT = Path(__file__).parent / "golden" / "exports"


def _skill() -> SkillCard:
    return SkillCard(
        id="skill-canonical-review",
        name="Review Diff Before Approval",
        description="Inspect changed files before approving a pull request.",
        applies_when=["Reviewing code changes", "Summarizing pull request risk"],
        does_not_apply_when=["No repository diff is available"],
        instructions=[
            "Read the changed files before making a recommendation.",
            "Call out missing tests when behavior changes.",
        ],
        anti_patterns=["Approve based only on the pull request title"],
        evidence_trace_ids=["trace-pr-review-001"],
        confidence=0.87,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        version="1.2.3",
        created_at=NOW,
        updated_at=NOW,
    )


def _candidate(action_type: RecommendedActionType) -> LessonCandidate:
    return LessonCandidate(
        id="candidate-review-diff",
        summary="Inspect diffs before review approval",
        evidence_trace_ids=["trace-pr-review-001"],
        evidence_event_ids=["event-review-001"],
        observed_problem="The agent approved a pull request without reading the diff.",
        proposed_lesson="Always inspect changed files before approving a pull request.",
        confidence=0.74,
        recommended_action_type=action_type,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        status=LessonStatus.APPROVED,
        created_at=NOW,
        updated_at=NOW,
    )


def _lesson() -> OperationalLesson:
    return OperationalLesson(
        lesson_id="lesson-review-diff",
        candidate_id="candidate-review-diff",
        title="Review Diff Before Approval",
        summary="Inspect changed files before approving a pull request.",
        instructions=["Read changed files before making a recommendation."],
        applies_when=["Reviewing pull requests"],
        does_not_apply_when=["No code changed"],
        anti_patterns=["Approve from metadata alone"],
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        recommended_action_type=RecommendedActionType.SKILL,
        evidence_trace_ids=["trace-pr-review-001"],
        evidence_event_ids=["event-review-001"],
        confidence=0.8,
        status=LessonStatus.APPROVED,
        created_at=NOW,
    )


def _codex_skill_md() -> str:
    return export_codex_skill_directory(_skill())["SKILL.md"]


def _codex_metadata() -> str:
    return export_codex_skill_directory(_skill())["metadata.json"]


EXPORT_CASES: dict[str, Callable[[], str]] = {
    "skill/markdown.md": lambda: export_skillcard_markdown(_skill()),
    "skill/json.json": lambda: export_skillcard_json(_skill()),
    "skill/copilot-fragment.md": lambda: export_copilot_instruction_fragment(_skill()),
    "skill/copilot-repo.md": lambda: export_copilot_repo_instruction(_skill()),
    "skill/copilot-path.md": lambda: export_copilot_path_instruction(_skill(), "src/**/*.py"),
    "skill/claude-fragment.md": lambda: export_claude_skill_fragment(_skill()),
    "skill/claude-skill.md": lambda: export_claude_skill_md(_skill()),
    "skill/claude-rule.md": lambda: export_claude_rule_fragment(_skill()),
    "skill/claude-md.md": lambda: export_claude_md_snippet(_skill()),
    "skill/agents-md.md": lambda: export_agents_md_fragment(_skill()),
    "skill/runtime-snippet.txt": lambda: export_runtime_prompt_snippet(_skill()),
    "skill/codex/SKILL.md": _codex_skill_md,
    "skill/codex/metadata.json": _codex_metadata,
    "lesson/markdown.md": lambda: export_operational_lesson_markdown(_lesson()),
    "lesson/eval.md": lambda: export_eval_spec_markdown(_candidate(RecommendedActionType.EVAL)),
    "lesson/guardrail.md": lambda: export_guardrail_rule_markdown(
        _candidate(RecommendedActionType.GUARDRAIL)
    ),
    "lesson/workflow.md": lambda: export_workflow_recommendation_markdown(
        _candidate(RecommendedActionType.WORKFLOW_CHANGE)
    ),
}


@pytest.mark.parametrize("relative_path, render", EXPORT_CASES.items())
def test_export_output_matches_checked_in_golden(
    relative_path: str,
    render: Callable[[], str],
    pytestconfig: pytest.Config,
) -> None:
    path = GOLDEN_ROOT / relative_path
    rendered = render()
    if relative_path.endswith(".json"):
        json.loads(rendered)

    if pytestconfig.getoption("--update-golden"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")

    assert path.read_text(encoding="utf-8") == rendered
