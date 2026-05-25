"""Core domain models for lessonweaver."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TraceEventType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    RETRY = "retry"
    HUMAN_CORRECTION = "human_correction"
    EVALUATION_RESULT = "evaluation_result"
    FINAL_ANSWER = "final_answer"
    WORKFLOW_STEP = "workflow_step"


class RecommendedActionType(str, Enum):
    SKILL = "skill"
    INSTRUCTION_PATCH = "instruction_patch"
    EVAL = "eval"
    GUARDRAIL = "guardrail"
    WORKFLOW_CHANGE = "workflow_change"
    RETRIEVAL_RULE = "retrieval_rule"
    DOCUMENTATION = "documentation"
    TEST = "test"
    REJECT = "reject"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Scope(str, Enum):
    USER = "user"
    PROJECT = "project"
    TEAM = "team"
    ORGANIZATION = "organization"
    GLOBAL = "global"


class LessonStatus(str, Enum):
    CANDIDATE = "candidate"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPORTED = "exported"
    DEPRECATED = "deprecated"


class SkillStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass(slots=True)
class TraceEvent:
    id: str
    type: TraceEventType
    content: str | None = None
    status: str | None = None
    success: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TraceEvent":
        return cls(
            id=str(data["id"]),
            type=TraceEventType(str(data["type"])),
            content=data.get("content"),
            status=data.get("status"),
            success=data.get("success"),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["type"] = self.type.value
        return payload


@dataclass(slots=True)
class TraceBundle:
    trace_id: str
    source: str
    task: str
    events: list[TraceEvent]
    outcome: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TraceBundle":
        return cls(
            trace_id=str(data["trace_id"]),
            source=str(data["source"]),
            task=str(data.get("task", "")),
            events=[TraceEvent.from_dict(item) for item in data.get("events", [])],
            outcome=str(data.get("outcome", "unknown")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "source": self.source,
            "task": self.task,
            "events": [event.to_dict() for event in self.events],
            "outcome": self.outcome,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class LessonCandidate:
    id: str
    summary: str
    evidence_trace_ids: list[str]
    evidence_event_ids: list[str]
    observed_problem: str
    proposed_lesson: str
    confidence: float
    recommended_action_type: RecommendedActionType
    risk_level: RiskLevel
    scope: Scope
    status: LessonStatus = LessonStatus.CANDIDATE

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LessonCandidate":
        return cls(
            id=str(data["id"]),
            summary=str(data["summary"]),
            evidence_trace_ids=list(data.get("evidence_trace_ids", [])),
            evidence_event_ids=list(data.get("evidence_event_ids", [])),
            observed_problem=str(data.get("observed_problem", "")),
            proposed_lesson=str(data.get("proposed_lesson", "")),
            confidence=float(data.get("confidence", 0.0)),
            recommended_action_type=RecommendedActionType(
                str(data.get("recommended_action_type", RecommendedActionType.SKILL.value))
            ),
            risk_level=RiskLevel(str(data.get("risk_level", RiskLevel.LOW.value))),
            scope=Scope(str(data.get("scope", Scope.PROJECT.value))),
            status=LessonStatus(str(data.get("status", LessonStatus.CANDIDATE.value))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "evidence_trace_ids": self.evidence_trace_ids,
            "evidence_event_ids": self.evidence_event_ids,
            "observed_problem": self.observed_problem,
            "proposed_lesson": self.proposed_lesson,
            "confidence": self.confidence,
            "recommended_action_type": self.recommended_action_type.value,
            "risk_level": self.risk_level.value,
            "scope": self.scope.value,
            "status": self.status.value,
        }


@dataclass(slots=True)
class ReviewOption:
    """Single MCQ option; label is the display key shown to reviewers (e.g., A/B/C)."""

    id: str
    label: str
    description: str
    effect: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReviewQuestion:
    id: str
    question: str
    options: list[ReviewOption]
    recommended_option_id: str
    rationale: str
    allow_free_text: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "options": [option.to_dict() for option in self.options],
            "recommended_option_id": self.recommended_option_id,
            "rationale": self.rationale,
            "allow_free_text": self.allow_free_text,
        }


@dataclass(slots=True)
class SkillCard:
    id: str
    name: str
    description: str
    applies_when: list[str]
    does_not_apply_when: list[str]
    instructions: list[str]
    anti_patterns: list[str]
    evidence_trace_ids: list[str]
    confidence: float
    risk_level: RiskLevel
    scope: Scope
    version: str
    status: SkillStatus = SkillStatus.DRAFT

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillCard":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            applies_when=list(data.get("applies_when", [])),
            does_not_apply_when=list(data.get("does_not_apply_when", [])),
            instructions=list(data.get("instructions", [])),
            anti_patterns=list(data.get("anti_patterns", [])),
            evidence_trace_ids=list(data.get("evidence_trace_ids", [])),
            confidence=float(data.get("confidence", 0.0)),
            risk_level=RiskLevel(str(data.get("risk_level", RiskLevel.LOW.value))),
            scope=Scope(str(data.get("scope", Scope.PROJECT.value))),
            version=str(data.get("version", "0.1.0")),
            status=SkillStatus(str(data.get("status", SkillStatus.DRAFT.value))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "applies_when": self.applies_when,
            "does_not_apply_when": self.does_not_apply_when,
            "instructions": self.instructions,
            "anti_patterns": self.anti_patterns,
            "evidence_trace_ids": self.evidence_trace_ids,
            "confidence": self.confidence,
            "risk_level": self.risk_level.value,
            "scope": self.scope.value,
            "version": self.version,
            "status": self.status.value,
        }
