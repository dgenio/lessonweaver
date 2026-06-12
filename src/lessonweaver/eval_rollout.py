"""Eval-before-rollout helpers for reviewed agent artifacts."""

from __future__ import annotations

from dataclasses import replace

from .governance import promote_skill
from .models import LessonCandidate, SkillCard, SkillStatus
from .validation import SkillEvalResult, ValidationExample, ValidationSuite, run_validation_suite


def generate_eval_suite_for_skill(skill: SkillCard) -> ValidationSuite:
    """Generate a minimal positive/negative retrieval suite for a skill."""
    positive_task = skill.applies_when[0] if skill.applies_when else skill.description
    negative_task = skill.does_not_apply_when[0] if skill.does_not_apply_when else "Unrelated task"
    return ValidationSuite(
        suite_id=f"rollout-eval-{skill.id}",
        skill_id=skill.id,
        examples=[
            ValidationExample(
                example_id="positive-should-load",
                task=positive_task,
                should_load=True,
                expected_skill_id=skill.id,
                notes="Generated positive rollout check.",
            ),
            ValidationExample(
                example_id="negative-should-not-load",
                task=negative_task,
                should_load=False,
                expected_skill_id=skill.id,
                notes="Generated negative rollout precision check.",
            ),
        ],
    )


def generate_eval_suite_for_candidate(
    candidate: LessonCandidate,
    *,
    skill_id: str | None = None,
) -> ValidationSuite:
    """Generate a minimal eval suite for a reviewed candidate's future skill."""
    expected_skill_id = skill_id or f"skill-{candidate.id}"
    negative_task = candidate.metadata.get("negative_eval_task", "Unrelated task")
    return ValidationSuite(
        suite_id=f"rollout-eval-{candidate.id}",
        skill_id=expected_skill_id,
        examples=[
            ValidationExample(
                example_id="positive-should-load",
                task=candidate.proposed_lesson or candidate.summary,
                should_load=True,
                expected_skill_id=expected_skill_id,
                notes="Generated positive rollout check.",
            ),
            ValidationExample(
                example_id="negative-should-not-load",
                task=str(negative_task),
                should_load=False,
                expected_skill_id=expected_skill_id,
                notes="Generated negative rollout precision check.",
            ),
        ],
    )


def validate_artifact_for_rollout(
    skill: SkillCard,
    suite: ValidationSuite,
    *,
    skills: list[SkillCard] | None = None,
) -> SkillEvalResult:
    """Validate a skill with a suite before rollout or promotion."""
    validation_skills = skills or [skill]
    return run_validation_suite(suite, validation_skills)


def promote_artifact_with_eval(
    skill: SkillCard,
    target: SkillStatus,
    *,
    suite: ValidationSuite | None = None,
    require_eval_pass: bool = False,
    allow_eval_fail: bool = False,
    skills: list[SkillCard] | None = None,
) -> SkillCard:
    """Promote a skill, optionally requiring an eval suite to pass first."""
    eval_result: SkillEvalResult | None = None
    if require_eval_pass:
        if suite is None:
            raise ValueError("--eval-suite is required when --require-eval-pass is set")
        eval_result = validate_artifact_for_rollout(skill, suite, skills=skills)
        if eval_result.failed and not allow_eval_fail:
            raise ValueError(
                f"eval suite failed: {eval_result.failed} failing example(s); "
                "pass --allow-eval-fail to record an override"
            )

    promoted = promote_skill(skill, target)
    if eval_result is None:
        return promoted

    metadata = dict(promoted.metadata)
    metadata["eval_before_rollout"] = {
        "suite_id": eval_result.suite_id,
        "passed": eval_result.failed == 0,
        "failed": eval_result.failed,
        "pass_rate": eval_result.pass_rate,
        "override": bool(eval_result.failed and allow_eval_fail),
    }
    return replace(promoted, metadata=metadata)
