"""Conservative deterministic lesson candidate detection."""

from __future__ import annotations

import re

from .models import (
    LessonCandidate,
    RecommendedActionType,
    RiskLevel,
    Scope,
    TraceBundle,
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


class LessonDetector:
    """Scan traces for candidate lessons using deterministic heuristics."""

    def detect(self, trace: TraceBundle) -> list[LessonCandidate]:
        candidates: list[LessonCandidate] = []
        events = trace.events

        lesson_flag = trace.metadata.get("lesson_candidate")
        if lesson_flag is True or (isinstance(lesson_flag, str) and lesson_flag.lower() == "true"):
            candidates.append(
                LessonCandidate(
                    id=_candidate_id(trace.trace_id, "metadata-flag"),
                    summary="Candidate lesson flagged explicitly via trace metadata.",
                    evidence_trace_ids=[trace.trace_id],
                    evidence_event_ids=[],
                    observed_problem=str(
                        trace.metadata.get("lesson_problem", "Explicitly flagged trace.")
                    ),
                    proposed_lesson=str(
                        trace.metadata.get(
                            "lesson_note", "Review flagged trace for reusable lesson."
                        )
                    ),
                    confidence=0.70,
                    evidence_strength=0.6,
                    evidence_summary=(
                        "Explicit trace metadata flag is a human-provided signal, but it is "
                        "not derived from observed failure events in the trace."
                    ),
                    recommended_action_type=RecommendedActionType.SKILL,
                    risk_level=RiskLevel.MEDIUM,
                    scope=Scope.PROJECT,
                )
            )

        human_corrections = [e for e in events if e.type is TraceEventType.HUMAN_CORRECTION]
        if human_corrections:
            event_ids = [event.id for event in human_corrections]
            candidates.append(
                LessonCandidate(
                    id=_candidate_id(trace.trace_id, "human-correction"),
                    summary="Candidate lesson based on observed correction by a human reviewer.",
                    evidence_trace_ids=[trace.trace_id],
                    evidence_event_ids=event_ids,
                    observed_problem=(
                        "Agent required explicit human correction before reaching "
                        "acceptable behavior."
                    ),
                    proposed_lesson=(
                        "Possible reusable pattern: incorporate the corrected check earlier "
                        "in similar tasks."
                    ),
                    confidence=0.62,
                    evidence_strength=0.7,
                    evidence_summary=(
                        "A human correction event is direct, first-hand evidence that the "
                        "agent's behavior needed fixing before it was acceptable."
                    ),
                    recommended_action_type=RecommendedActionType.SKILL,
                    risk_level=RiskLevel.MEDIUM,
                    scope=Scope.PROJECT,
                )
            )

        failed_evals = [
            event
            for event in events
            if event.type is TraceEventType.EVALUATION_RESULT and event.status == "failed"
        ]
        if failed_evals:
            candidates.append(
                LessonCandidate(
                    id=_candidate_id(trace.trace_id, "failed-eval"),
                    summary="Candidate lesson based on failed evaluation_result signal.",
                    evidence_trace_ids=[trace.trace_id],
                    evidence_event_ids=[failed_evals[0].id],
                    observed_problem=(
                        "An evaluation_result event marked output quality/compliance as failed."
                    ),
                    proposed_lesson=(
                        "Possible reusable pattern: add stronger retrieval/version checks "
                        "before answering."
                    ),
                    confidence=0.58,
                    evidence_strength=0.65,
                    evidence_summary=(
                        "A failed evaluation_result is a graded signal of a real problem, "
                        "though it may not pinpoint the root cause on its own."
                    ),
                    recommended_action_type=RecommendedActionType.EVAL,
                    risk_level=RiskLevel.HIGH,
                    scope=Scope.PROJECT,
                )
            )

        # Workflow-step signal: a workflow step that precedes a failure (an error
        # or a human correction) is a conservative hint that the step ordering may
        # be missing a validation gate. Report the most recent workflow step before
        # the first such failure (other events may fall between them). Stays
        # conservative: it never fires when the failure has no preceding workflow step.
        _WORKFLOW_FAILURE_TYPES = {TraceEventType.ERROR, TraceEventType.HUMAN_CORRECTION}
        first_failure_index = next(
            (idx for idx, event in enumerate(events) if event.type in _WORKFLOW_FAILURE_TYPES),
            None,
        )
        if first_failure_index is not None:
            preceding_step = next(
                (
                    event
                    for event in reversed(events[:first_failure_index])
                    if event.type is TraceEventType.WORKFLOW_STEP
                ),
                None,
            )
            if preceding_step is not None:
                failure_event = events[first_failure_index]
                failure_kind = (
                    "human correction"
                    if failure_event.type is TraceEventType.HUMAN_CORRECTION
                    else "error"
                )
                step_description = preceding_step.content or "an unlabeled workflow step"
                candidates.append(
                    LessonCandidate(
                        id=_candidate_id(trace.trace_id, "workflow-step-failure"),
                        summary=(
                            "Candidate lesson based on a workflow step that preceded a failure."
                        ),
                        evidence_trace_ids=[trace.trace_id],
                        evidence_event_ids=[preceding_step.id, failure_event.id],
                        observed_problem=(
                            f"Workflow step before the failure: {step_description} "
                            f"(followed by {failure_kind})."
                        ),
                        proposed_lesson=(
                            "Possible deterministic fix: add a validation step before this "
                            "workflow step."
                        ),
                        confidence=0.50,
                        evidence_strength=0.4,
                        evidence_summary=(
                            "The most recent workflow step before a failure is suggestive of a "
                            "missing validation gate, but other events may fall between them and "
                            "the failure may be unrelated to step ordering."
                        ),
                        recommended_action_type=RecommendedActionType.WORKFLOW_CHANGE,
                        risk_level=RiskLevel.MEDIUM,
                        scope=Scope.PROJECT,
                    )
                )

        error_index = next(
            (idx for idx, event in enumerate(events) if event.type is TraceEventType.ERROR), None
        )
        if error_index is not None:
            retry_index = next(
                (
                    idx
                    for idx, event in enumerate(events[error_index + 1 :], start=error_index + 1)
                    if event.type is TraceEventType.RETRY
                ),
                None,
            )
            if retry_index is not None and trace.outcome.lower() in {
                "success",
                "corrected_by_human",
            }:
                candidates.append(
                    LessonCandidate(
                        id=_candidate_id(trace.trace_id, "error-retry-success"),
                        summary="Candidate lesson based on error followed by retry then success.",
                        evidence_trace_ids=[trace.trace_id],
                        evidence_event_ids=[events[error_index].id, events[retry_index].id],
                        observed_problem=(
                            "Task needed retry after an error to reach a successful outcome."
                        ),
                        proposed_lesson=(
                            "Possible reusable pattern: bake pre-checks to reduce retriable "
                            "failure mode."
                        ),
                        confidence=0.49,
                        evidence_strength=0.4,
                        evidence_summary=(
                            "Error followed by retry then success is indirect evidence; the "
                            "recovery may be incidental rather than a reusable pattern."
                        ),
                        recommended_action_type=RecommendedActionType.WORKFLOW_CHANGE,
                        risk_level=RiskLevel.LOW,
                        scope=Scope.PROJECT,
                    )
                )

        failed_tool_calls = [
            event
            for event in events
            if event.type is TraceEventType.TOOL_CALL
            and (event.success is False or event.status == "failed")
        ]
        if failed_tool_calls:
            # Emit at most one fallback candidate per trace to avoid duplicate guidance.
            for failed_call in failed_tool_calls:
                failed_index = events.index(failed_call)
                success_after = next(
                    (
                        event
                        for event in events[failed_index + 1 :]
                        if event.type is TraceEventType.TOOL_CALL
                        and (event.success is True or event.status == "success")
                        and event.id != failed_call.id
                    ),
                    None,
                )
                if success_after is not None:
                    candidates.append(
                        LessonCandidate(
                            id=_candidate_id(trace.trace_id, "tool-fallback"),
                            summary=(
                                "Candidate lesson based on tool failure followed by "
                                "successful alternative."
                            ),
                            evidence_trace_ids=[trace.trace_id],
                            evidence_event_ids=[failed_call.id, success_after.id],
                            observed_problem=(
                                "A tool call failed before a later successful alternative "
                                "completed task progress."
                            ),
                            proposed_lesson=(
                                "Possible reusable pattern: define explicit tool fallback "
                                "guidance for this task type."
                            ),
                            confidence=0.44,
                            evidence_strength=0.35,
                            evidence_summary=(
                                "A later successful tool call after a failure is weak evidence "
                                "of a reusable fallback rule; the alternative may be situational."
                            ),
                            recommended_action_type=RecommendedActionType.WORKFLOW_CHANGE,
                            risk_level=RiskLevel.MEDIUM,
                            scope=Scope.PROJECT,
                        )
                    )
                    break

        if trace.outcome.lower() == "corrected_by_human" and not human_corrections:
            candidates.append(
                LessonCandidate(
                    id=_candidate_id(trace.trace_id, "corrected-outcome"),
                    summary="Candidate lesson based on corrected_by_human final outcome.",
                    evidence_trace_ids=[trace.trace_id],
                    evidence_event_ids=[],
                    observed_problem=(
                        "Final outcome indicates correction was needed even without explicit "
                        "correction event detail."
                    ),
                    proposed_lesson=(
                        "Possible reusable pattern: require extra validation before final "
                        "answer in similar runs."
                    ),
                    confidence=0.42,
                    evidence_strength=0.3,
                    evidence_summary=(
                        "Only the final outcome flag indicates a correction was needed; no "
                        "explicit correction event provides supporting detail."
                    ),
                    recommended_action_type=RecommendedActionType.TEST,
                    risk_level=RiskLevel.MEDIUM,
                    scope=Scope.PROJECT,
                )
            )

        recurring_pattern = trace.metadata.get("recurring_pattern")
        if isinstance(recurring_pattern, str) and recurring_pattern and not candidates:
            candidates.append(
                LessonCandidate(
                    id=_candidate_id(trace.trace_id, "recurring-pattern"),
                    summary="Cluster-only candidate based on repeated unflagged trace metadata.",
                    evidence_trace_ids=[trace.trace_id],
                    evidence_event_ids=[],
                    observed_problem=(
                        "Trace metadata marks this as a recurring unflagged pattern, but the "
                        "single trace has no explicit error, failed evaluation, or human "
                        "correction signal."
                    ),
                    proposed_lesson=(
                        f"Possible recurring pattern to confirm across traces: {recurring_pattern}."
                    ),
                    confidence=0.28,
                    evidence_strength=0.2,
                    evidence_summary=(
                        "A recurring-pattern metadata marker is intentionally weak evidence; "
                        "it should only count when multiple occurrences cluster together."
                    ),
                    recommended_action_type=RecommendedActionType.SKILL,
                    risk_level=RiskLevel.LOW,
                    scope=Scope.PROJECT,
                    metadata={"cluster_only": True, "recurring_pattern": recurring_pattern},
                )
            )

        return candidates
