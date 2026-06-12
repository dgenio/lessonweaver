"""Core domain models for lessonweaver."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any, *, default: datetime | None = None) -> datetime | None:
    if value is None:
        return default
    if isinstance(value, datetime):
        return _ensure_timezone_aware(value)
    if isinstance(value, str) and value:
        normalized = value.replace("Z", "+00:00")
        return _ensure_timezone_aware(datetime.fromisoformat(normalized))
    return default


def _unit_interval(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be between 0.0 and 1.0, got {value!r}")
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0, got {parsed}")
    return parsed


def _strict_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"{field_name} must be a boolean")


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative integer, got {parsed}")
    return parsed


def _ensure_timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _datetime_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


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
    EXPERIMENTAL = "experimental"
    ACTIVE = "active"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class SensitivityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    COPILOT_INSTRUCTION = "copilot_instruction"
    CLAUDE_SKILL = "claude_skill"
    RUNTIME_SNIPPET = "runtime_snippet"
    CODEX_DIRECTORY = "codex_directory"


# Ordering used to compare risk levels (LOW < MEDIUM < HIGH).
_RISK_LEVEL_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
}


@dataclass(slots=True)
class TraceEvent:
    id: str
    type: TraceEventType
    content: str | None = None
    status: str | None = None
    success: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEvent:
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
    def from_dict(cls, data: dict[str, Any]) -> TraceBundle:
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
    # ``evidence_strength`` measures the quality/directness of the supporting
    # trace evidence and is intentionally distinct from ``confidence`` (how
    # likely the lesson is valid). Lessons are hypotheses, not proven facts: a
    # high-confidence guess can rest on weak evidence, and vice versa.
    evidence_strength: float = 0.0
    # Human-readable rationale captured at detection time explaining why the
    # evidence does or does not support the candidate (causal uncertainty).
    evidence_summary: str = ""
    status: LessonStatus = LessonStatus.CANDIDATE
    owner: str | None = None
    approved_by: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    approved_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LessonCandidate:
        created_at = _parse_datetime(data.get("created_at"), default=_utc_now())
        updated_at = _parse_datetime(data.get("updated_at"), default=created_at)
        assert created_at is not None
        assert updated_at is not None
        return cls(
            id=str(data["id"]),
            summary=str(data["summary"]),
            evidence_trace_ids=list(data.get("evidence_trace_ids", [])),
            evidence_event_ids=list(data.get("evidence_event_ids", [])),
            observed_problem=str(data.get("observed_problem", "")),
            proposed_lesson=str(data.get("proposed_lesson", "")),
            confidence=_unit_interval(data.get("confidence", 0.0), "confidence"),
            recommended_action_type=RecommendedActionType(
                str(data.get("recommended_action_type", RecommendedActionType.SKILL.value))
            ),
            risk_level=RiskLevel(str(data.get("risk_level", RiskLevel.LOW.value))),
            scope=Scope(str(data.get("scope", Scope.PROJECT.value))),
            evidence_strength=_unit_interval(
                data.get("evidence_strength", 0.0), "evidence_strength"
            ),
            evidence_summary=str(data.get("evidence_summary", "")),
            status=LessonStatus(str(data.get("status", LessonStatus.CANDIDATE.value))),
            owner=data.get("owner"),
            approved_by=data.get("approved_by"),
            created_at=created_at,
            updated_at=updated_at,
            approved_at=_parse_datetime(data.get("approved_at")),
            expires_at=_parse_datetime(data.get("expires_at")),
            metadata=dict(data.get("metadata", {})),
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
            "evidence_strength": self.evidence_strength,
            "evidence_summary": self.evidence_summary,
            "status": self.status.value,
            "owner": self.owner,
            "approved_by": self.approved_by,
            "created_at": _datetime_to_str(self.created_at),
            "updated_at": _datetime_to_str(self.updated_at),
            "approved_at": _datetime_to_str(self.approved_at),
            "expires_at": _datetime_to_str(self.expires_at),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ReviewOption:
    """Single MCQ option; label is the display key shown to reviewers (e.g., A/B/C)."""

    id: str
    label: str
    description: str
    effect: dict[str, Any] = field(default_factory=dict)
    follow_up_question_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewOption:
        return cls(
            id=str(data["id"]),
            label=str(data["label"]),
            description=str(data.get("description", "")),
            effect=dict(data.get("effect", {})),
            follow_up_question_ids=list(data.get("follow_up_question_ids", [])),
        )

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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewQuestion:
        return cls(
            id=str(data["id"]),
            question=str(data["question"]),
            options=[ReviewOption.from_dict(item) for item in data.get("options", [])],
            recommended_option_id=str(data.get("recommended_option_id", "")),
            rationale=str(data.get("rationale", "")),
            allow_free_text=_strict_bool(data.get("allow_free_text", True), "allow_free_text"),
        )

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
class ReviewAnswer:
    question_id: str
    chosen_option_id: str
    free_text: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewAnswer:
        return cls(
            question_id=str(data["question_id"]),
            chosen_option_id=str(data["chosen_option_id"]),
            free_text=str(data.get("free_text", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReviewSession:
    """Persisted progress of a guided MCQ review so it can be paused and resumed.

    ``started_at`` and ``updated_at`` are ISO 8601 strings. ``current_question_index``
    is a simple position marker into the review (typically the number of answers
    recorded); the next questions to ask are derived from ``answers`` so adaptive
    follow-ups stay deterministic on resume.
    """

    session_id: str
    candidate_id: str
    started_at: str
    updated_at: str
    answers: list[ReviewAnswer] = field(default_factory=list)
    current_question_index: int = 0
    completed: bool = False
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewSession:
        return cls(
            session_id=str(data["session_id"]),
            candidate_id=str(data["candidate_id"]),
            started_at=str(data["started_at"]),
            updated_at=str(data["updated_at"]),
            answers=[ReviewAnswer.from_dict(item) for item in data.get("answers", [])],
            current_question_index=_non_negative_int(
                data.get("current_question_index", 0), "current_question_index"
            ),
            completed=_strict_bool(data.get("completed", False), "completed"),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "candidate_id": self.candidate_id,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "answers": [answer.to_dict() for answer in self.answers],
            "current_question_index": self.current_question_index,
            "completed": self.completed,
            "notes": self.notes,
        }


@dataclass(slots=True)
class OperationalLesson:
    lesson_id: str
    candidate_id: str
    title: str
    summary: str
    instructions: list[str]
    applies_when: list[str]
    does_not_apply_when: list[str]
    anti_patterns: list[str]
    risk_level: RiskLevel
    scope: Scope
    recommended_action_type: RecommendedActionType
    evidence_trace_ids: list[str]
    evidence_event_ids: list[str]
    confidence: float
    review_answers: list[ReviewAnswer] = field(default_factory=list)
    status: LessonStatus = LessonStatus.APPROVED
    created_at: datetime = field(default_factory=_utc_now)
    approved_at: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperationalLesson:
        created_at = _parse_datetime(data.get("created_at"), default=_utc_now())
        assert created_at is not None
        return cls(
            lesson_id=str(data["lesson_id"]),
            candidate_id=str(data["candidate_id"]),
            title=str(data["title"]),
            summary=str(data.get("summary", "")),
            instructions=list(data.get("instructions", [])),
            applies_when=list(data.get("applies_when", [])),
            does_not_apply_when=list(data.get("does_not_apply_when", [])),
            anti_patterns=list(data.get("anti_patterns", [])),
            risk_level=RiskLevel(str(data.get("risk_level", RiskLevel.LOW.value))),
            scope=Scope(str(data.get("scope", Scope.PROJECT.value))),
            recommended_action_type=RecommendedActionType(
                str(data.get("recommended_action_type", RecommendedActionType.SKILL.value))
            ),
            evidence_trace_ids=list(data.get("evidence_trace_ids", [])),
            evidence_event_ids=list(data.get("evidence_event_ids", [])),
            confidence=_unit_interval(data.get("confidence", 0.0), "confidence"),
            review_answers=[
                ReviewAnswer.from_dict(item) for item in data.get("review_answers", [])
            ],
            status=LessonStatus(str(data.get("status", LessonStatus.APPROVED.value))),
            created_at=created_at,
            approved_at=_parse_datetime(data.get("approved_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "lesson_id": self.lesson_id,
            "candidate_id": self.candidate_id,
            "title": self.title,
            "summary": self.summary,
            "instructions": self.instructions,
            "applies_when": self.applies_when,
            "does_not_apply_when": self.does_not_apply_when,
            "anti_patterns": self.anti_patterns,
            "risk_level": self.risk_level.value,
            "scope": self.scope.value,
            "recommended_action_type": self.recommended_action_type.value,
            "evidence_trace_ids": self.evidence_trace_ids,
            "evidence_event_ids": self.evidence_event_ids,
            "confidence": self.confidence,
            "review_answers": [answer.to_dict() for answer in self.review_answers],
            "status": self.status.value,
            "created_at": _datetime_to_str(self.created_at),
            "approved_at": _datetime_to_str(self.approved_at),
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
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    owner: str | None = None
    approved_by: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    approved_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillCard:
        created_at = _parse_datetime(data.get("created_at"), default=_utc_now())
        updated_at = _parse_datetime(data.get("updated_at"), default=created_at)
        assert created_at is not None
        assert updated_at is not None
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            applies_when=list(data.get("applies_when", [])),
            does_not_apply_when=list(data.get("does_not_apply_when", [])),
            instructions=list(data.get("instructions", [])),
            anti_patterns=list(data.get("anti_patterns", [])),
            evidence_trace_ids=list(data.get("evidence_trace_ids", [])),
            confidence=_unit_interval(data.get("confidence", 0.0), "confidence"),
            risk_level=RiskLevel(str(data.get("risk_level", RiskLevel.LOW.value))),
            scope=Scope(str(data.get("scope", Scope.PROJECT.value))),
            version=str(data.get("version", "0.1.0")),
            status=SkillStatus(str(data.get("status", SkillStatus.DRAFT.value))),
            sensitivity=SensitivityLevel(
                str(data.get("sensitivity", SensitivityLevel.INTERNAL.value))
            ),
            owner=data.get("owner"),
            approved_by=data.get("approved_by"),
            created_at=created_at,
            updated_at=updated_at,
            approved_at=_parse_datetime(data.get("approved_at")),
            expires_at=_parse_datetime(data.get("expires_at")),
            metadata=dict(data.get("metadata", {})),
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
            "sensitivity": self.sensitivity.value,
            "owner": self.owner,
            "approved_by": self.approved_by,
            "created_at": _datetime_to_str(self.created_at),
            "updated_at": _datetime_to_str(self.updated_at),
            "approved_at": _datetime_to_str(self.approved_at),
            "expires_at": _datetime_to_str(self.expires_at),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ExportArtifact:
    artifact_id: str
    format: ExportFormat
    content: str
    skill_id: str | None = None
    lesson_id: str | None = None
    created_at: datetime = field(default_factory=_utc_now)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportArtifact:
        created_at = _parse_datetime(data.get("created_at"), default=_utc_now())
        assert created_at is not None
        return cls(
            artifact_id=str(data["artifact_id"]),
            format=ExportFormat(str(data["format"])),
            content=str(data.get("content", "")),
            skill_id=data.get("skill_id"),
            lesson_id=data.get("lesson_id"),
            created_at=created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "skill_id": self.skill_id,
            "lesson_id": self.lesson_id,
            "format": self.format.value,
            "content": self.content,
            "created_at": _datetime_to_str(self.created_at),
        }


@dataclass(slots=True)
class SkillUsageEvent:
    """A passive record that a skill was loaded into an agent context.

    ``outcome`` and ``outcome_positive`` are filled in after the interaction
    completes; they are never inferred automatically. This is the runtime-reuse
    half of the closed feedback loop: skills accumulate usage evidence rather
    than being trusted forever because they were plausible once.
    """

    id: str
    skill_id: str
    skill_version: str
    task_context: str
    loaded_at: datetime = field(default_factory=_utc_now)
    outcome: str | None = None
    outcome_positive: bool | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillUsageEvent:
        loaded_at = _parse_datetime(data.get("loaded_at"), default=_utc_now())
        assert loaded_at is not None
        outcome_positive = data.get("outcome_positive")
        return cls(
            id=str(data["id"]),
            skill_id=str(data["skill_id"]),
            skill_version=str(data.get("skill_version", "")),
            task_context=str(data.get("task_context", "")),
            loaded_at=loaded_at,
            outcome=data.get("outcome"),
            outcome_positive=(
                _strict_bool(outcome_positive, "outcome_positive")
                if outcome_positive is not None
                else None
            ),
            notes=data.get("notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "task_context": self.task_context,
            "loaded_at": _datetime_to_str(self.loaded_at),
            "outcome": self.outcome,
            "outcome_positive": self.outcome_positive,
            "notes": self.notes,
        }


@dataclass(slots=True)
class LoadingPolicy:
    """Deterministic filter controlling which skills are eligible to load.

    Retrieval without a policy is unconstrained: high-risk skills load beside
    low-risk ones and out-of-scope skills leak across teams. This model is the
    scope-aware, risk-filtered, "do not load" layer applied before retrieval.
    """

    max_skills: int = 5
    max_token_budget: int = 2000
    allowed_scopes: list[Scope] = field(default_factory=list)
    max_risk_level: RiskLevel = RiskLevel.MEDIUM
    excluded_skill_ids: list[str] = field(default_factory=list)
    require_approved_status: bool = True

    def filter(self, skills: list[SkillCard]) -> list[SkillCard]:
        """Return the subset of ``skills`` eligible under this policy.

        ``allowed_scopes`` empty means all scopes are allowed. ``max_risk_level``
        is a ceiling. ``require_approved_status`` keeps only ACTIVE or APPROVED
        skills. The list is iterated once and order is preserved.
        """

        ceiling = _RISK_LEVEL_ORDER[self.max_risk_level]
        allowed_scopes = set(self.allowed_scopes)
        excluded = set(self.excluded_skill_ids)
        eligible: list[SkillCard] = []
        for skill in skills:
            if skill.id in excluded:
                continue
            if _RISK_LEVEL_ORDER[skill.risk_level] > ceiling:
                continue
            if allowed_scopes and skill.scope not in allowed_scopes:
                continue
            if self.require_approved_status and skill.status not in {
                SkillStatus.ACTIVE,
                SkillStatus.APPROVED,
            }:
                continue
            eligible.append(skill)
        return eligible

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoadingPolicy:
        return cls(
            max_skills=_non_negative_int(data.get("max_skills", 5), "max_skills"),
            max_token_budget=_non_negative_int(
                data.get("max_token_budget", 2000), "max_token_budget"
            ),
            allowed_scopes=[Scope(str(item)) for item in data.get("allowed_scopes", [])],
            max_risk_level=RiskLevel(str(data.get("max_risk_level", RiskLevel.MEDIUM.value))),
            excluded_skill_ids=[str(item) for item in data.get("excluded_skill_ids", [])],
            require_approved_status=_strict_bool(
                data.get("require_approved_status", True), "require_approved_status"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_skills": self.max_skills,
            "max_token_budget": self.max_token_budget,
            "allowed_scopes": [scope.value for scope in self.allowed_scopes],
            "max_risk_level": self.max_risk_level.value,
            "excluded_skill_ids": list(self.excluded_skill_ids),
            "require_approved_status": self.require_approved_status,
        }


@dataclass(slots=True)
class StaleSkillReport:
    """A single finding that a skill should be revalidated, deprecated, or removed."""

    skill_id: str
    reason: str  # "expired", "never_used", "deprecated", "low_confidence"
    recommendation: str  # "revalidate", "deprecate", "remove"
    last_used_at: datetime | None = None
    expires_at: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StaleSkillReport:
        return cls(
            skill_id=str(data["skill_id"]),
            reason=str(data["reason"]),
            recommendation=str(data.get("recommendation", "")),
            last_used_at=_parse_datetime(data.get("last_used_at")),
            expires_at=_parse_datetime(data.get("expires_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "reason": self.reason,
            "recommendation": self.recommendation,
            "last_used_at": _datetime_to_str(self.last_used_at),
            "expires_at": _datetime_to_str(self.expires_at),
        }
