"""Conservative deterministic lesson candidate detection."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from .models import (
    LessonCandidate,
    RecommendedActionType,
    RiskLevel,
    Scope,
    TraceBundle,
    TraceEvent,
    TraceEventType,
)

_UNSAFE_ID_CHARS_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _candidate_id(trace_id: str, suffix: str) -> str:
    safe_trace_id = _UNSAFE_ID_CHARS_RE.sub("-", trace_id).strip(".-")
    while ".." in safe_trace_id:
        safe_trace_id = safe_trace_id.replace("..", ".")
    if not safe_trace_id:
        safe_trace_id = "trace"
    return f"{safe_trace_id}-{suffix}"


@runtime_checkable
class DetectionSignal(Protocol):
    """Small deterministic detector that emits zero or more lesson candidates."""

    name: str

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]: ...


def _candidate(
    trace: TraceBundle,
    *,
    suffix: str,
    summary: str,
    evidence_event_ids: list[str],
    observed_problem: str,
    proposed_lesson: str,
    confidence: float,
    evidence_strength: float,
    evidence_summary: str,
    recommended_action_type: RecommendedActionType,
    risk_level: RiskLevel,
    scope: Scope,
) -> LessonCandidate:
    return LessonCandidate(
        id=_candidate_id(trace.trace_id, suffix),
        summary=summary,
        evidence_trace_ids=[trace.trace_id],
        evidence_event_ids=evidence_event_ids,
        observed_problem=observed_problem,
        proposed_lesson=proposed_lesson,
        confidence=confidence,
        evidence_strength=evidence_strength,
        evidence_summary=evidence_summary,
        recommended_action_type=recommended_action_type,
        risk_level=risk_level,
        scope=scope,
    )


class MetadataFlagSignal:
    name = "metadata_flag"
    CONFIDENCE = 0.70
    EVIDENCE_STRENGTH = 0.6

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        lesson_flag = trace.metadata.get("lesson_candidate")
        if not (
            lesson_flag is True or (isinstance(lesson_flag, str) and lesson_flag.lower() == "true")
        ):
            return []
        return [
            _candidate(
                trace,
                suffix="metadata-flag",
                summary="Candidate lesson flagged explicitly via trace metadata.",
                evidence_event_ids=[],
                observed_problem=str(
                    trace.metadata.get("lesson_problem", "Explicitly flagged trace.")
                ),
                proposed_lesson=str(
                    trace.metadata.get("lesson_note", "Review flagged trace for reusable lesson.")
                ),
                confidence=self.CONFIDENCE,
                evidence_strength=self.EVIDENCE_STRENGTH,
                evidence_summary=(
                    "Explicit trace metadata flag is a human-provided signal, but it is "
                    "not derived from observed failure events in the trace."
                ),
                recommended_action_type=RecommendedActionType.SKILL,
                risk_level=RiskLevel.MEDIUM,
                scope=Scope.PROJECT,
            )
        ]


class HumanCorrectionSignal:
    name = "human_correction"
    CONFIDENCE = 0.62
    EVIDENCE_STRENGTH = 0.7

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        human_corrections = [
            event for event in trace.events if event.type is TraceEventType.HUMAN_CORRECTION
        ]
        if not human_corrections:
            return []
        return [
            _candidate(
                trace,
                suffix="human-correction",
                summary="Candidate lesson based on observed correction by a human reviewer.",
                evidence_event_ids=[event.id for event in human_corrections],
                observed_problem=(
                    "Agent required explicit human correction before reaching acceptable behavior."
                ),
                proposed_lesson=(
                    "Possible reusable pattern: incorporate the corrected check earlier "
                    "in similar tasks."
                ),
                confidence=self.CONFIDENCE,
                evidence_strength=self.EVIDENCE_STRENGTH,
                evidence_summary=(
                    "A human correction event is direct, first-hand evidence that the "
                    "agent's behavior needed fixing before it was acceptable."
                ),
                recommended_action_type=RecommendedActionType.SKILL,
                risk_level=RiskLevel.MEDIUM,
                scope=Scope.PROJECT,
            )
        ]


class FailedEvalSignal:
    name = "failed_eval"
    CONFIDENCE = 0.58
    EVIDENCE_STRENGTH = 0.65

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        failed_evals = [
            event
            for event in trace.events
            if event.type is TraceEventType.EVALUATION_RESULT and event.status == "failed"
        ]
        if not failed_evals:
            return []
        return [
            _candidate(
                trace,
                suffix="failed-eval",
                summary="Candidate lesson based on failed evaluation_result signal.",
                evidence_event_ids=[failed_evals[0].id],
                observed_problem=(
                    "An evaluation_result event marked output quality/compliance as failed."
                ),
                proposed_lesson=(
                    "Possible reusable pattern: add stronger retrieval/version checks "
                    "before answering."
                ),
                confidence=self.CONFIDENCE,
                evidence_strength=self.EVIDENCE_STRENGTH,
                evidence_summary=(
                    "A failed evaluation_result is a graded signal of a real problem, "
                    "though it may not pinpoint the root cause on its own."
                ),
                recommended_action_type=RecommendedActionType.EVAL,
                risk_level=RiskLevel.HIGH,
                scope=Scope.PROJECT,
            )
        ]


class WorkflowStepFailureSignal:
    name = "workflow_step_failure"
    CONFIDENCE = 0.50
    EVIDENCE_STRENGTH = 0.4
    FAILURE_TYPES = {TraceEventType.ERROR, TraceEventType.HUMAN_CORRECTION}

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        first_failure_index = next(
            (idx for idx, event in enumerate(trace.events) if event.type in self.FAILURE_TYPES),
            None,
        )
        if first_failure_index is None:
            return []
        preceding_step = next(
            (
                event
                for event in reversed(trace.events[:first_failure_index])
                if event.type is TraceEventType.WORKFLOW_STEP
            ),
            None,
        )
        if preceding_step is None:
            return []
        failure_event = trace.events[first_failure_index]
        failure_kind = (
            "human correction" if failure_event.type is TraceEventType.HUMAN_CORRECTION else "error"
        )
        step_description = preceding_step.content or "an unlabeled workflow step"
        return [
            _candidate(
                trace,
                suffix="workflow-step-failure",
                summary="Candidate lesson based on a workflow step that preceded a failure.",
                evidence_event_ids=[preceding_step.id, failure_event.id],
                observed_problem=(
                    f"Workflow step before the failure: {step_description} "
                    f"(followed by {failure_kind})."
                ),
                proposed_lesson=(
                    "Possible deterministic fix: add a validation step before this workflow step."
                ),
                confidence=self.CONFIDENCE,
                evidence_strength=self.EVIDENCE_STRENGTH,
                evidence_summary=(
                    "The most recent workflow step before a failure is suggestive of a "
                    "missing validation gate, but other events may fall between them and "
                    "the failure may be unrelated to step ordering."
                ),
                recommended_action_type=RecommendedActionType.WORKFLOW_CHANGE,
                risk_level=RiskLevel.MEDIUM,
                scope=Scope.PROJECT,
            )
        ]


class ErrorRetrySuccessSignal:
    name = "error_retry_success"
    CONFIDENCE = 0.49
    EVIDENCE_STRENGTH = 0.4

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        error_index = next(
            (idx for idx, event in enumerate(trace.events) if event.type is TraceEventType.ERROR),
            None,
        )
        if error_index is None:
            return []
        retry_index = next(
            (
                idx
                for idx, event in enumerate(trace.events[error_index + 1 :], start=error_index + 1)
                if event.type is TraceEventType.RETRY
            ),
            None,
        )
        if retry_index is None or trace.outcome.lower() not in {"success", "corrected_by_human"}:
            return []
        return [
            _candidate(
                trace,
                suffix="error-retry-success",
                summary="Candidate lesson based on error followed by retry then success.",
                evidence_event_ids=[trace.events[error_index].id, trace.events[retry_index].id],
                observed_problem="Task needed retry after an error to reach a successful outcome.",
                proposed_lesson=(
                    "Possible reusable pattern: bake pre-checks to reduce retriable failure mode."
                ),
                confidence=self.CONFIDENCE,
                evidence_strength=self.EVIDENCE_STRENGTH,
                evidence_summary=(
                    "Error followed by retry then success is indirect evidence; the "
                    "recovery may be incidental rather than a reusable pattern."
                ),
                recommended_action_type=RecommendedActionType.WORKFLOW_CHANGE,
                risk_level=RiskLevel.LOW,
                scope=Scope.PROJECT,
            )
        ]


class ToolFallbackSignal:
    name = "tool_fallback"
    CONFIDENCE = 0.44
    EVIDENCE_STRENGTH = 0.35

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        for failed_index, failed_call in enumerate(trace.events):
            if not _is_failed_tool_call(failed_call):
                continue
            success_after = next(
                (
                    event
                    for event in trace.events[failed_index + 1 :]
                    if _is_successful_tool_call(event) and event.id != failed_call.id
                ),
                None,
            )
            if success_after is None:
                continue
            return [
                _candidate(
                    trace,
                    suffix="tool-fallback",
                    summary=(
                        "Candidate lesson based on tool failure followed by successful alternative."
                    ),
                    evidence_event_ids=[failed_call.id, success_after.id],
                    observed_problem=(
                        "A tool call failed before a later successful alternative "
                        "completed task progress."
                    ),
                    proposed_lesson=(
                        "Possible reusable pattern: define explicit tool fallback "
                        "guidance for this task type."
                    ),
                    confidence=self.CONFIDENCE,
                    evidence_strength=self.EVIDENCE_STRENGTH,
                    evidence_summary=(
                        "A later successful tool call after a failure is weak evidence "
                        "of a reusable fallback rule; the alternative may be situational."
                    ),
                    recommended_action_type=RecommendedActionType.WORKFLOW_CHANGE,
                    risk_level=RiskLevel.MEDIUM,
                    scope=Scope.PROJECT,
                )
            ]
        return []


class CorrectedOutcomeSignal:
    name = "corrected_outcome"
    CONFIDENCE = 0.42
    EVIDENCE_STRENGTH = 0.3

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        has_human_correction = any(
            event.type is TraceEventType.HUMAN_CORRECTION for event in trace.events
        )
        if trace.outcome.lower() != "corrected_by_human" or has_human_correction:
            return []
        return [
            _candidate(
                trace,
                suffix="corrected-outcome",
                summary="Candidate lesson based on corrected_by_human final outcome.",
                evidence_event_ids=[],
                observed_problem=(
                    "Final outcome indicates correction was needed even without explicit "
                    "correction event detail."
                ),
                proposed_lesson=(
                    "Possible reusable pattern: require extra validation before final "
                    "answer in similar runs."
                ),
                confidence=self.CONFIDENCE,
                evidence_strength=self.EVIDENCE_STRENGTH,
                evidence_summary=(
                    "Only the final outcome flag indicates a correction was needed; no "
                    "explicit correction event provides supporting detail."
                ),
                recommended_action_type=RecommendedActionType.TEST,
                risk_level=RiskLevel.MEDIUM,
                scope=Scope.PROJECT,
            )
        ]


def _is_failed_tool_call(event: TraceEvent) -> bool:
    return event.type is TraceEventType.TOOL_CALL and (
        event.success is False or event.status == "failed"
    )


def _is_successful_tool_call(event: TraceEvent) -> bool:
    return event.type is TraceEventType.TOOL_CALL and (
        event.success is True or event.status == "success"
    )


DEFAULT_DETECTION_SIGNALS: tuple[DetectionSignal, ...] = (
    MetadataFlagSignal(),
    HumanCorrectionSignal(),
    FailedEvalSignal(),
    WorkflowStepFailureSignal(),
    ErrorRetrySuccessSignal(),
    ToolFallbackSignal(),
    CorrectedOutcomeSignal(),
)


class LessonDetector:
    """Scan traces for candidate lessons using deterministic heuristics."""

    def __init__(self, signals: Sequence[DetectionSignal] | None = None) -> None:
        self.signals = tuple(DEFAULT_DETECTION_SIGNALS if signals is None else signals)

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        candidates: list[LessonCandidate] = []
        for signal in self.signals:
            candidates.extend(signal.detect(trace))
        return candidates
