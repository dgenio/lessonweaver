from __future__ import annotations

import pytest

from lessonweaver.detection import LessonDetector
from lessonweaver.models import TraceEventType
from lessonweaver.recorder import TraceRecorder, record
from lessonweaver.traces import load_trace_bundle


def test_trace_recorder_emits_valid_ordered_events_with_stable_ids(tmp_path) -> None:
    recorder = TraceRecorder("trace-1", "unit-test", "Review a pull request")
    recorder.user_message("Please review this PR.")
    recorder.agent_message("Looks good from the title.")
    recorder.tool_call("github.diff", metadata={"args": {"pr": 1}})
    recorder.tool_result("github.diff", success=True)
    recorder.model_call("gpt-4.1", metadata={"tokens": 42})
    recorder.workflow_step("Inspect changed files")
    recorder.evaluation_result("diff inspected", status="failed")
    recorder.human_correction("Inspect the diff before review conclusions.")
    recorder.retry("Retry with diff inspection")
    recorder.final_answer("Needs changes.")
    recorder.set_outcome("corrected_by_human")

    out = tmp_path / "trace.json"
    recorder.save(out)
    bundle = load_trace_bundle(out)

    assert [event.id for event in bundle.events] == [f"e{idx}" for idx in range(1, 11)]
    assert [event.type for event in bundle.events] == [
        TraceEventType.USER_MESSAGE,
        TraceEventType.ASSISTANT_MESSAGE,
        TraceEventType.TOOL_CALL,
        TraceEventType.TOOL_RESULT,
        TraceEventType.MODEL_CALL,
        TraceEventType.WORKFLOW_STEP,
        TraceEventType.EVALUATION_RESULT,
        TraceEventType.HUMAN_CORRECTION,
        TraceEventType.RETRY,
        TraceEventType.FINAL_ANSWER,
    ]
    assert bundle.events[2].metadata["tool_name"] == "github.diff"
    assert bundle.outcome == "corrected_by_human"


def test_record_context_manager_saves_exception_trace(tmp_path) -> None:
    out = tmp_path / "trace.json"

    with pytest.raises(RuntimeError, match="boom"):
        with record("unit-test", "Run risky tool", trace_id="trace-error", output=out) as recorder:
            recorder.user_message("run it")
            raise RuntimeError("boom")

    bundle = load_trace_bundle(out)
    assert bundle.trace_id == "trace-error"
    assert bundle.outcome == "failure"
    assert bundle.events[-1].type is TraceEventType.ERROR
    assert bundle.events[-1].content == "RuntimeError: boom"


def test_recorder_sanitize_scrubs_content_before_save(tmp_path) -> None:
    out = tmp_path / "trace.json"
    recorder = TraceRecorder("trace-sensitive", "unit-test", "Handle user", sanitize=True)
    recorder.user_message("Email me at person@example.com")
    recorder.set_outcome("success")
    recorder.save(out)

    bundle = load_trace_bundle(out)
    assert bundle.events[0].content == "Email me at [REDACTED by email]"


def test_recorder_event_ids_are_stable_for_identical_call_sequences() -> None:
    def build() -> list[str]:
        recorder = TraceRecorder("trace", "unit-test", "Task")
        recorder.user_message("hi")
        recorder.agent_message("hello")
        recorder.human_correction("needs more detail")
        return [event.id for event in recorder.to_bundle().events]

    assert build() == build() == ["e1", "e2", "e3"]


def test_recorder_tool_results_preserve_fallback_detection_signals() -> None:
    recorder = TraceRecorder("trace-tool-fallback", "unit-test", "Use API fallback")
    recorder.tool_call("api_a")
    recorder.tool_result("api_a", success=False)
    recorder.tool_call("api_b")
    recorder.tool_result("api_b", success=True)
    recorder.final_answer("done")
    recorder.set_outcome("success")

    bundle = recorder.to_bundle()
    candidates = LessonDetector().detect(bundle)

    assert bundle.events[0].type is TraceEventType.TOOL_CALL
    assert bundle.events[0].success is False
    assert bundle.events[0].status == "failed"
    assert bundle.events[2].type is TraceEventType.TOOL_CALL
    assert bundle.events[2].success is True
    assert bundle.events[2].status == "success"
    assert any("tool failure followed by successful alternative" in c.summary for c in candidates)
