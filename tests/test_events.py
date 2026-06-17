from __future__ import annotations

import json
from pathlib import Path

from lessonweaver.detection import LessonDetector
from lessonweaver.events import EventEmitter, LifecycleEvent, LifecycleEventType, emitter
from lessonweaver.export import export_skillcard_markdown
from lessonweaver.interview import LessonInterviewer, apply_review_answer
from lessonweaver.loader import SkillLoader
from lessonweaver.models import (
    LessonCandidate,
    RecommendedActionType,
    ReviewAnswer,
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
)
from lessonweaver.registry import FileSystemRegistry
from lessonweaver.retrieval import RetrievalQuery, SkillRetriever
from lessonweaver.traces import load_trace_bundle
from lessonweaver.validation import ValidationExample, ValidationSuite, run_validation_suite


def _skill(
    skill_id: str = "skill-pr-review",
    *,
    description: str = "Inspect diffs before reviewing pull requests.",
    status: SkillStatus = SkillStatus.ACTIVE,
) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name="PR Diff First",
        description=description,
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Inspect changed files first"],
        anti_patterns=[],
        evidence_trace_ids=["trace-pr"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.1.0",
        status=status,
    )


def _candidate() -> LessonCandidate:
    return LessonCandidate(
        id="candidate-pr-review",
        summary="Inspect diffs before review",
        evidence_trace_ids=["trace-pr"],
        evidence_event_ids=["event-1"],
        observed_problem="The agent approved a PR without reading the diff.",
        proposed_lesson="Read changed files before approving.",
        confidence=0.7,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
    )


def test_lifecycle_event_serializes_to_json_ready_dict() -> None:
    event = LifecycleEvent(
        event_type=LifecycleEventType.TRACE_LOADED,
        subject_id="trace-1",
        metadata={"event_count": 3},
        timestamp="2026-05-26T12:00:00+00:00",
    )

    payload = event.to_dict()

    assert payload == {
        "event_type": "trace_loaded",
        "timestamp": "2026-05-26T12:00:00+00:00",
        "subject_id": "trace-1",
        "metadata": {"event_count": 3},
    }
    json.dumps(payload)


def test_emitter_listener_on_off_and_capture() -> None:
    local = EventEmitter()
    received: list[LifecycleEvent] = []
    event = LifecycleEvent(LifecycleEventType.SKILL_EXPORTED, "skill-1")

    local.on(received.append)
    local.emit(event)
    local.off(received.append)
    local.emit(LifecycleEvent(LifecycleEventType.SKILL_EXPORTED, "skill-2"))

    assert received == [event]

    with local.capture() as captured:
        local.emit(event)

    assert captured == [event]


def test_loading_trace_bundle_emits_trace_loaded() -> None:
    with emitter.capture() as events:
        trace = load_trace_bundle("examples/traces/github_pr_review_failure.json")

    assert trace.trace_id
    assert any(
        event.event_type is LifecycleEventType.TRACE_LOADED
        and event.subject_id == trace.trace_id
        and event.metadata["path"].endswith("github_pr_review_failure.json")
        for event in events
    )


def test_detection_emits_candidate_detected_and_rejected_events() -> None:
    trace = load_trace_bundle("examples/traces/github_pr_review_failure.json")
    with emitter.capture() as detected_events:
        candidates = LessonDetector().detect(trace)

    assert candidates
    assert {
        event.subject_id
        for event in detected_events
        if event.event_type is LifecycleEventType.CANDIDATE_DETECTED
    } == {candidate.id for candidate in candidates}

    boring_trace = load_trace_bundle("examples/traces/workflow_validation_order.json")
    boring_trace.events = []
    boring_trace.outcome = "success"
    with emitter.capture() as rejected_events:
        assert LessonDetector().detect(boring_trace) == []

    assert any(
        event.event_type is LifecycleEventType.CANDIDATE_REJECTED
        and event.subject_id == boring_trace.trace_id
        for event in rejected_events
    )


def test_interview_emits_question_and_answer_events() -> None:
    candidate = _candidate()
    interviewer = LessonInterviewer()

    with emitter.capture() as events:
        questions = interviewer.build_questions(candidate)

    assert questions
    assert any(
        event.event_type is LifecycleEventType.REVIEW_QUESTION_GENERATED
        and event.subject_id == candidate.id
        and event.metadata["question_id"] == questions[0].id
        for event in events
    )

    answer = ReviewAnswer(question_id=questions[0].id, chosen_option_id="team")
    with emitter.capture() as answer_events:
        apply_review_answer(candidate, questions[0], answer)

    assert any(
        event.event_type is LifecycleEventType.REVIEW_ANSWER_APPLIED
        and event.subject_id == candidate.id
        and event.metadata["question_id"] == questions[0].id
        for event in answer_events
    )


def test_retrieval_and_loader_emit_skill_events(tmp_path: Path) -> None:
    selected = _skill("selected")
    omitted = _skill("omitted", description="Inspect diffs before reviewing pull requests also.")
    with emitter.capture() as retrieval_events:
        results = SkillRetriever().retrieve(
            [selected],
            RetrievalQuery(task="Review this pull request", max_results=1),
        )

    assert [result.skill.id for result in results] == ["selected"]
    assert any(
        event.event_type is LifecycleEventType.SKILL_RETRIEVED and event.subject_id == "selected"
        for event in retrieval_events
    )

    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(selected)
    registry.save_skill(omitted)
    with emitter.capture() as load_events:
        context = SkillLoader(registry).load_for_task(
            "Review this pull request", budget_chars=1, max_skills=2
        )

    assert context.omitted_skills
    assert {
        event.subject_id
        for event in load_events
        if event.event_type is LifecycleEventType.SKILL_OMITTED_BUDGET
    } == set(context.omitted_skills)


def test_loader_does_not_emit_budget_events_for_intentional_omissions(tmp_path: Path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("selected"))

    with emitter.capture() as load_events:
        context = SkillLoader(registry).load_for_task(
            "Review this pull request",
            inclusion_level="none",
        )

    assert context.omitted_skills == ["selected"]
    assert not any(
        event.event_type is LifecycleEventType.SKILL_OMITTED_BUDGET for event in load_events
    )


def test_export_and_validation_emit_lifecycle_events() -> None:
    skill = _skill()
    with emitter.capture() as export_events:
        rendered = export_skillcard_markdown(skill)

    assert rendered.startswith("# PR Diff First")
    assert any(
        event.event_type is LifecycleEventType.SKILL_EXPORTED
        and event.subject_id == skill.id
        and event.metadata["format"] == "markdown"
        for event in export_events
    )

    suite = ValidationSuite(
        suite_id="suite-1",
        skill_id=skill.id,
        examples=[
            ValidationExample("pass", "Review this pull request", should_load=True),
            ValidationExample("fail", "Review this pull request", should_load=False),
        ],
    )
    with emitter.capture() as validation_events:
        result = run_validation_suite(suite, [skill])

    assert result.passed == 1
    assert {
        event.event_type
        for event in validation_events
        if event.metadata.get("suite_id") == suite.suite_id
    } == {LifecycleEventType.VALIDATION_PASSED, LifecycleEventType.VALIDATION_FAILED}
