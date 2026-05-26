from lessonweaver.detection import LessonDetector
from lessonweaver.models import TraceBundle
from lessonweaver.traces import load_trace_bundle


def test_detection_from_human_correction() -> None:
    trace = load_trace_bundle("examples/traces/github_pr_review_failure.json")
    candidates = LessonDetector().detect(trace)
    assert any("observed correction" in candidate.summary for candidate in candidates)


def test_detection_boring_success_trace_produces_no_candidate() -> None:
    trace = TraceBundle.from_dict(
        {
            "trace_id": "boring-1",
            "source": "unit-test",
            "task": "Simple greeting",
            "events": [
                {"id": "1", "type": "user_message", "content": "hi"},
                {"id": "2", "type": "assistant_message", "content": "hello"},
                {"id": "3", "type": "final_answer", "content": "done"},
            ],
            "outcome": "success",
        }
    )
    assert LessonDetector().detect(trace) == []


def test_detection_failed_eval() -> None:
    trace = load_trace_bundle("examples/traces/external_chatbot_policy_failure.json")
    candidates = LessonDetector().detect(trace)
    assert any("failed evaluation_result" in c.summary for c in candidates)


def test_detection_error_retry_success() -> None:
    trace = TraceBundle.from_dict(
        {
            "trace_id": "err-retry-1",
            "source": "unit-test",
            "task": "Retry task",
            "events": [
                {"id": "1", "type": "user_message", "content": "do something"},
                {"id": "2", "type": "error", "content": "connection timeout"},
                {"id": "3", "type": "retry", "content": "retrying"},
                {"id": "4", "type": "final_answer", "content": "done"},
            ],
            "outcome": "success",
        }
    )
    candidates = LessonDetector().detect(trace)
    assert any("error followed by retry" in c.summary for c in candidates)


def test_detection_tool_call_fallback() -> None:
    trace = TraceBundle.from_dict(
        {
            "trace_id": "tool-fb-1",
            "source": "unit-test",
            "task": "Tool fallback",
            "events": [
                {
                    "id": "1",
                    "type": "tool_call",
                    "content": "api_a",
                    "success": False,
                    "status": "failed",
                },
                {
                    "id": "2",
                    "type": "tool_call",
                    "content": "api_b",
                    "success": True,
                    "status": "success",
                },
                {"id": "3", "type": "final_answer", "content": "done"},
            ],
            "outcome": "success",
        }
    )
    candidates = LessonDetector().detect(trace)
    assert any("tool failure followed by successful alternative" in c.summary for c in candidates)


def test_detection_tool_call_success_before_failure_not_matched() -> None:
    """Successful tool call BEFORE failure should not produce a fallback candidate."""
    trace = TraceBundle.from_dict(
        {
            "trace_id": "tool-order-1",
            "source": "unit-test",
            "task": "Order check",
            "events": [
                {
                    "id": "1",
                    "type": "tool_call",
                    "content": "api_a",
                    "success": True,
                    "status": "success",
                },
                {
                    "id": "2",
                    "type": "tool_call",
                    "content": "api_b",
                    "success": False,
                    "status": "failed",
                },
                {"id": "3", "type": "final_answer", "content": "done"},
            ],
            "outcome": "success",
        }
    )
    candidates = LessonDetector().detect(trace)
    assert not any(
        "tool failure followed by successful alternative" in c.summary for c in candidates
    )


def test_detection_corrected_by_human_outcome() -> None:
    trace = TraceBundle.from_dict(
        {
            "trace_id": "corrected-1",
            "source": "unit-test",
            "task": "Outcome correction",
            "events": [
                {"id": "1", "type": "user_message", "content": "do task"},
                {"id": "2", "type": "final_answer", "content": "done"},
            ],
            "outcome": "corrected_by_human",
        }
    )
    candidates = LessonDetector().detect(trace)
    assert any("corrected_by_human final outcome" in c.summary for c in candidates)


def test_detection_empty_events_produces_no_candidate() -> None:
    trace = TraceBundle.from_dict(
        {
            "trace_id": "empty-1",
            "source": "unit-test",
            "task": "Empty trace",
            "events": [],
            "outcome": "success",
        }
    )
    assert LessonDetector().detect(trace) == []


def test_detection_error_without_retry_produces_no_retry_candidate() -> None:
    """Error without a subsequent retry should NOT produce an error-retry-success candidate."""
    trace = TraceBundle.from_dict(
        {
            "trace_id": "no-retry-1",
            "source": "unit-test",
            "task": "Error only",
            "events": [
                {"id": "1", "type": "error", "content": "something broke"},
                {"id": "2", "type": "final_answer", "content": "gave up"},
            ],
            "outcome": "success",
        }
    )
    candidates = LessonDetector().detect(trace)
    assert not any("error followed by retry" in c.summary for c in candidates)


def test_detection_metadata_flag() -> None:
    trace = TraceBundle.from_dict(
        {
            "trace_id": "flagged-1",
            "source": "unit-test",
            "task": "Flagged trace",
            "events": [{"id": "1", "type": "final_answer", "content": "done"}],
            "outcome": "success",
            "metadata": {"lesson_candidate": True},
        }
    )
    candidates = LessonDetector().detect(trace)
    assert candidates[0].id == "flagged-1-metadata-flag"
    assert candidates[0].observed_problem == "Explicitly flagged trace."


def test_detection_metadata_flag_uses_custom_problem() -> None:
    trace = TraceBundle.from_dict(
        {
            "trace_id": "flagged-2",
            "source": "unit-test",
            "task": "Flagged trace",
            "events": [{"id": "1", "type": "final_answer", "content": "done"}],
            "outcome": "success",
            "metadata": {
                "lesson_candidate": "true",
                "lesson_problem": "Custom problem",
                "lesson_note": "Custom lesson",
            },
        }
    )
    candidates = LessonDetector().detect(trace)
    assert candidates[0].observed_problem == "Custom problem"
    assert candidates[0].proposed_lesson == "Custom lesson"


def test_detection_corrected_by_human_with_event_does_not_duplicate_outcome_candidate() -> None:
    trace = TraceBundle.from_dict(
        {
            "trace_id": "corrected-dedup",
            "source": "unit-test",
            "task": "Correction",
            "events": [{"id": "1", "type": "human_correction", "content": "fix"}],
            "outcome": "corrected_by_human",
        }
    )
    candidates = LessonDetector().detect(trace)
    assert any("observed correction" in candidate.summary for candidate in candidates)
    assert not any(
        "corrected_by_human final outcome" in candidate.summary for candidate in candidates
    )
