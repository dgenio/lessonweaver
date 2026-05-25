"""Guided MCQ interview helpers for lesson candidates."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from .models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    ReviewOption,
    ReviewQuestion,
    RiskLevel,
    Scope,
)


class LessonInterviewer:
    """Generates multiple-choice review questions for a candidate lesson."""

    def build_questions(self, candidate: LessonCandidate) -> list[ReviewQuestion]:
        return [
            ReviewQuestion(
                id="scope",
                question="Where should this lesson apply?",
                options=[
                    ReviewOption("project", "A", "Only this project", {"scope": Scope.PROJECT.value}),
                    ReviewOption("team", "B", "Team repositories", {"scope": Scope.TEAM.value}),
                    ReviewOption("organization", "C", "Organization-wide", {"scope": Scope.ORGANIZATION.value}),
                    ReviewOption("global", "D", "All agent environments", {"scope": Scope.GLOBAL.value}),
                    ReviewOption("other", "E", "Other (free text)", {}),
                ],
                recommended_option_id="project",
                rationale="Evidence currently comes from a single trace, so project scope is safest.",
                allow_free_text=True,
            ),
            ReviewQuestion(
                id="action_type",
                question="Which artifact should this lesson become?",
                options=[
                    ReviewOption("skill", "A", "Skill card", {"recommended_action_type": RecommendedActionType.SKILL.value}),
                    ReviewOption(
                        "instruction_patch",
                        "B",
                        "Instruction patch",
                        {"recommended_action_type": RecommendedActionType.INSTRUCTION_PATCH.value},
                    ),
                    ReviewOption("eval", "C", "Eval spec", {"recommended_action_type": RecommendedActionType.EVAL.value}),
                    ReviewOption(
                        "guardrail",
                        "D",
                        "Guardrail rule",
                        {"recommended_action_type": RecommendedActionType.GUARDRAIL.value},
                    ),
                    ReviewOption("other", "E", "Other (free text)", {}),
                ],
                recommended_option_id=(
                    candidate.recommended_action_type.value
                    if candidate.recommended_action_type.value in {"skill", "instruction_patch", "eval", "guardrail"}
                    else "skill"
                ),
                rationale="Match artifact type to observed operational failure mode.",
                allow_free_text=True,
            ),
            ReviewQuestion(
                id="risk_level",
                question="What is the risk level if this lesson is ignored?",
                options=[
                    ReviewOption("low", "A", "Low impact", {"risk_level": RiskLevel.LOW.value}),
                    ReviewOption("medium", "B", "Moderate impact", {"risk_level": RiskLevel.MEDIUM.value}),
                    ReviewOption("high", "C", "High impact", {"risk_level": RiskLevel.HIGH.value}),
                    ReviewOption("other", "D", "Other (free text)", {}),
                ],
                recommended_option_id=candidate.risk_level.value,
                rationale="Risk should align with evidence severity and blast radius.",
                allow_free_text=True,
            ),
            ReviewQuestion(
                id="applicability",
                question="When should this lesson apply?",
                options=[
                    ReviewOption("always", "A", "Always for similar tasks", {}),
                    ReviewOption("high_risk", "B", "Only high-risk or user-visible tasks", {}),
                    ReviewOption("specific_tools", "C", "Only when specific tools/data sources are used", {}),
                    ReviewOption("other", "D", "Other (free text)", {}),
                ],
                recommended_option_id="high_risk",
                rationale="Conservative scoping reduces over-generalization from limited evidence.",
                allow_free_text=True,
            ),
            ReviewQuestion(
                id="negative_conditions",
                question="When should this lesson not be applied?",
                options=[
                    ReviewOption("none", "A", "No known exclusions", {}),
                    ReviewOption("different_domain", "B", "Do not apply in unrelated domains", {}),
                    ReviewOption("conflicting_policy", "C", "Do not apply when policy conflicts", {}),
                    ReviewOption("other", "D", "Other (free text)", {}),
                ],
                recommended_option_id="different_domain",
                rationale="Most lessons are context-specific and should include explicit non-applicability bounds.",
                allow_free_text=True,
            ),
            ReviewQuestion(
                id="decision",
                question="What is the review decision?",
                options=[
                    ReviewOption("approve", "A", "Approve lesson", {"status": LessonStatus.APPROVED.value}),
                    ReviewOption("needs_review", "B", "Needs more review", {"status": LessonStatus.NEEDS_REVIEW.value}),
                    ReviewOption("reject", "C", "Reject lesson", {"status": LessonStatus.REJECTED.value}),
                    ReviewOption("other", "D", "Other (free text)", {}),
                ],
                recommended_option_id="needs_review",
                rationale="A candidate should typically receive additional review before activation.",
                allow_free_text=True,
            ),
        ]


def apply_review_answer(candidate: LessonCandidate, option: ReviewOption) -> LessonCandidate:
    """Apply an option effect map onto candidate fields when keys are valid."""
    allowed_fields = {field.name for field in fields(candidate)}
    for key, value in option.effect.items():
        if key not in allowed_fields:
            continue
        if key == "scope":
            setattr(candidate, key, Scope(str(value)))
        elif key == "recommended_action_type":
            setattr(candidate, key, RecommendedActionType(str(value)))
        elif key == "risk_level":
            setattr(candidate, key, RiskLevel(str(value)))
        elif key == "status":
            setattr(candidate, key, LessonStatus(str(value)))
        else:
            setattr(candidate, key, value)
    return candidate
