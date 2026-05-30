"""Guided MCQ interview helpers for lesson candidates."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from .models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    ReviewAnswer,
    ReviewOption,
    ReviewQuestion,
    ReviewSession,
    RiskLevel,
    Scope,
)

# Base questions that no longer apply once a reviewer rejects the lesson.
_SKIP_ON_REJECT = ("scope", "applicability", "negative_conditions")


class LessonInterviewer:
    """Generates multiple-choice review questions for a candidate lesson."""

    def build_questions(self, candidate: LessonCandidate) -> list[ReviewQuestion]:
        return [
            ReviewQuestion(
                id="scope",
                question="Where should this lesson apply?",
                options=[
                    ReviewOption("user", "A", "Only this user", {"scope": Scope.USER.value}),
                    ReviewOption(
                        "project", "B", "Only this project", {"scope": Scope.PROJECT.value}
                    ),
                    ReviewOption("team", "C", "Team repositories", {"scope": Scope.TEAM.value}),
                    ReviewOption(
                        "organization",
                        "D",
                        "Organization-wide",
                        {"scope": Scope.ORGANIZATION.value},
                    ),
                    ReviewOption(
                        "global", "E", "All agent environments", {"scope": Scope.GLOBAL.value}
                    ),
                    ReviewOption("other", "F", "Other (free text)", {}),
                ],
                recommended_option_id=candidate.scope.value,
                rationale=(
                    "Evidence currently comes from a single trace, so the detected scope is "
                    "preserved as recommendation."
                ),
                allow_free_text=True,
            ),
            ReviewQuestion(
                id="action_type",
                question="Which artifact should this lesson become?",
                options=[
                    ReviewOption(
                        "skill",
                        "A",
                        "Skill card",
                        {"recommended_action_type": RecommendedActionType.SKILL.value},
                    ),
                    ReviewOption(
                        "instruction_patch",
                        "B",
                        "Instruction patch",
                        {"recommended_action_type": RecommendedActionType.INSTRUCTION_PATCH.value},
                    ),
                    ReviewOption(
                        "eval",
                        "C",
                        "Eval spec",
                        {"recommended_action_type": RecommendedActionType.EVAL.value},
                    ),
                    ReviewOption(
                        "guardrail",
                        "D",
                        "Guardrail rule",
                        {"recommended_action_type": RecommendedActionType.GUARDRAIL.value},
                    ),
                    ReviewOption(
                        "workflow_change",
                        "E",
                        "Workflow change",
                        {"recommended_action_type": RecommendedActionType.WORKFLOW_CHANGE.value},
                        follow_up_question_ids=["workflow_determinism"],
                    ),
                    ReviewOption(
                        "retrieval_rule",
                        "F",
                        "Retrieval rule",
                        {"recommended_action_type": RecommendedActionType.RETRIEVAL_RULE.value},
                    ),
                    ReviewOption(
                        "documentation",
                        "G",
                        "Documentation update",
                        {"recommended_action_type": RecommendedActionType.DOCUMENTATION.value},
                    ),
                    ReviewOption(
                        "test",
                        "H",
                        "Test / checklist",
                        {"recommended_action_type": RecommendedActionType.TEST.value},
                    ),
                    ReviewOption(
                        "reject",
                        "I",
                        "Reject lesson",
                        {"recommended_action_type": RecommendedActionType.REJECT.value},
                    ),
                    ReviewOption("other", "J", "Other (free text)", {}),
                ],
                recommended_option_id=candidate.recommended_action_type.value,
                rationale="Match artifact type to observed operational failure mode.",
                allow_free_text=True,
            ),
            ReviewQuestion(
                id="risk_level",
                question="What is the risk level if this lesson is ignored?",
                options=[
                    ReviewOption("low", "A", "Low impact", {"risk_level": RiskLevel.LOW.value}),
                    ReviewOption(
                        "medium", "B", "Moderate impact", {"risk_level": RiskLevel.MEDIUM.value}
                    ),
                    ReviewOption(
                        "high",
                        "C",
                        "High impact",
                        {"risk_level": RiskLevel.HIGH.value},
                        follow_up_question_ids=["approval_requirement"],
                    ),
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
                    ReviewOption(
                        "specific_tools",
                        "C",
                        "Only when specific tools/data sources are used",
                        {"_applies_when_hint": "specific_tools"},
                    ),
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
                    ReviewOption(
                        "conflicting_policy", "C", "Do not apply when policy conflicts", {}
                    ),
                    ReviewOption("other", "D", "Other (free text)", {}),
                ],
                recommended_option_id="different_domain",
                rationale=(
                    "Most lessons are context-specific and should include explicit "
                    "non-applicability bounds."
                ),
                allow_free_text=True,
            ),
            ReviewQuestion(
                id="decision",
                question="What is the review decision?",
                options=[
                    ReviewOption(
                        "approve", "A", "Approve lesson", {"status": LessonStatus.APPROVED.value}
                    ),
                    ReviewOption(
                        "needs_review",
                        "B",
                        "Needs more review",
                        {"status": LessonStatus.NEEDS_REVIEW.value},
                    ),
                    ReviewOption(
                        "reject", "C", "Reject lesson", {"status": LessonStatus.REJECTED.value}
                    ),
                    ReviewOption("other", "D", "Other (free text)", {}),
                ],
                recommended_option_id="needs_review",
                rationale=(
                    "A candidate should typically receive additional review before activation."
                ),
                allow_free_text=True,
            ),
        ]

    def build_follow_up_questions(self, candidate: LessonCandidate) -> dict[str, ReviewQuestion]:
        """Conditional questions that are only asked when an option triggers them."""
        return {
            "approval_requirement": ReviewQuestion(
                id="approval_requirement",
                question="Does activating this high-risk lesson require explicit approval?",
                options=[
                    ReviewOption(
                        "explicit_approval",
                        "A",
                        "Require recorded approver before activation",
                        {"_approval_required": "explicit"},
                    ),
                    ReviewOption(
                        "standard_review",
                        "B",
                        "Standard review is sufficient",
                        {"_approval_required": "standard"},
                    ),
                    ReviewOption("other", "C", "Other (free text)", {}),
                ],
                recommended_option_id="explicit_approval",
                rationale="High-risk lessons usually need a named approver before activation.",
                allow_free_text=True,
            ),
            "workflow_determinism": ReviewQuestion(
                id="workflow_determinism",
                question="Is this workflow change a deterministic rule or a prompt hint?",
                options=[
                    ReviewOption(
                        "deterministic_rule",
                        "A",
                        "Deterministic rule (validation gate / code path)",
                        {"_workflow_determinism": "deterministic_rule"},
                    ),
                    ReviewOption(
                        "prompt_hint",
                        "B",
                        "Prompt hint for the agent",
                        {"_workflow_determinism": "prompt_hint"},
                    ),
                    ReviewOption("other", "C", "Other (free text)", {}),
                ],
                recommended_option_id="deterministic_rule",
                rationale=(
                    "Prefer a deterministic rule when the fix can be enforced outside the prompt."
                ),
                allow_free_text=True,
            ),
        }

    def next_questions(
        self,
        candidate: LessonCandidate,
        answers: list[ReviewAnswer],
    ) -> list[ReviewQuestion]:
        """Return the remaining questions to ask, adapted to the answers so far.

        Adaptive rules (deterministic, no LLM):

        - A ``reject`` decision drops the still-unanswered scope, applicability, and
          negative-conditions questions.
        - Selecting ``high`` risk queues the approval-requirement follow-up.
        - Selecting the ``workflow_change`` action type queues the
          deterministic-vs-prompt follow-up.

        When no follow-up rules fire, the result is the base questions in order, so
        existing static behavior is preserved.
        """
        answered = {answer.question_id for answer in answers}
        base = self.build_questions(candidate)
        follow_ups = self.build_follow_up_questions(candidate)
        rejected = any(
            answer.question_id == "decision" and answer.chosen_option_id == "reject"
            for answer in answers
        )

        plan: list[ReviewQuestion] = []
        for question in base:
            if rejected and question.id in _SKIP_ON_REJECT and question.id not in answered:
                continue
            plan.append(question)

        questions_by_id = {question.id: question for question in base}
        questions_by_id.update(follow_ups)
        planned_ids = {question.id for question in plan}
        for answer in answers:
            source = questions_by_id.get(answer.question_id)
            if source is None:
                continue
            option = next(
                (item for item in source.options if item.id == answer.chosen_option_id), None
            )
            if option is None:
                continue
            for follow_up_id in option.follow_up_question_ids:
                follow_up = follow_ups.get(follow_up_id)
                if follow_up is not None and follow_up.id not in planned_ids:
                    plan.append(follow_up)
                    planned_ids.add(follow_up.id)

        return [question for question in plan if question.id not in answered]

    def build_session_summary(
        self,
        candidate_before: LessonCandidate,
        candidate_after: LessonCandidate,
        answers: list[ReviewAnswer],
    ) -> str:
        """Return a deterministic, human-readable summary of what the review changed."""
        lines = ["# Review session summary"]
        lines.append(f"- Status: {candidate_before.status.value} -> {candidate_after.status.value}")

        changes: list[str] = []
        for field_def in fields(candidate_after):
            if field_def.name in {"metadata", "id"}:
                continue
            before = getattr(candidate_before, field_def.name)
            after = getattr(candidate_after, field_def.name)
            if before != after:
                changes.append(
                    f"- {field_def.name}: {_format_value(before)} -> {_format_value(after)}"
                )
        lines.append("")
        if changes:
            lines.append("## Fields changed")
            lines.extend(changes)
        else:
            lines.append("## Fields changed")
            lines.append("- No candidate fields changed during review.")

        notes = [(answer.question_id, answer.free_text) for answer in answers if answer.free_text]
        if notes:
            lines.append("")
            lines.append("## Reviewer notes")
            lines.extend(f"- {question_id}: {text}" for question_id, text in notes)

        return "\n".join(lines)


def _format_value(value: object) -> str:
    """Render enum members by value and everything else via ``str`` for summaries."""
    enum_value = getattr(value, "value", None)
    if enum_value is not None and not isinstance(value, (list, dict)):
        return str(enum_value)
    return str(value)


def save_session(session: ReviewSession, path: str | Path) -> None:
    """Persist a review session to a JSON file."""
    payload = json.dumps(session.to_dict(), indent=2, sort_keys=True) + "\n"
    Path(path).write_text(payload, encoding="utf-8")


def load_session(path: str | Path) -> ReviewSession:
    """Load a review session previously written by :func:`save_session`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return ReviewSession.from_dict(data)


def apply_review_answer(
    candidate: LessonCandidate,
    question: ReviewQuestion,
    answer: ReviewAnswer,
) -> LessonCandidate:
    """Apply a structured review answer and preserve free text/history."""
    if answer.question_id != question.id:
        raise ValueError(
            f"answer question_id '{answer.question_id}' does not match question '{question.id}'"
        )

    option = next((item for item in question.options if item.id == answer.chosen_option_id), None)
    if option is None:
        raise ValueError(f"unknown option '{answer.chosen_option_id}' for question '{question.id}'")

    allowed_fields = {field.name for field in fields(candidate)}
    for key, value in option.effect.items():
        if key.startswith("_"):
            candidate.metadata[key] = value
            continue
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

    if answer.free_text:
        candidate.metadata[f"review_note_{question.id}"] = answer.free_text
    history = list(candidate.metadata.get("review_history", []))
    history.append(answer.to_dict())
    candidate.metadata["review_history"] = history

    return candidate
