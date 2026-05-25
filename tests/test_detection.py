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
