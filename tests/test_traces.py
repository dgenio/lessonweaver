import json

import pytest

from lessonweaver.detection import LessonDetector
from lessonweaver.traces import load_trace_bundle, validate_trace_dict, validate_trace_issues


def test_validate_trace_dict_accepts_valid_trace() -> None:
    errors = validate_trace_dict(
        {
            "trace_id": "trace-1",
            "source": "unit-test",
            "task": "Do work",
            "events": [{"id": "e1", "type": "user_message"}],
            "outcome": "success",
        }
    )
    assert errors == []


def test_validate_trace_issues_report_json_pointer_paths() -> None:
    issues = validate_trace_issues(
        {
            "trace_id": "",
            "events": [
                {"id": "", "type": "unknown"},
                {"id": "e1", "type": "user_message"},
                {"id": "e1", "type": "final_answer"},
            ],
        }
    )
    by_path = {issue.path: issue.message for issue in issues}
    assert by_path["/trace_id"] == "field 'trace_id' must be non-empty"
    assert by_path["/source"] == "missing required field: source"
    assert by_path["/task"] == "missing required field: task"
    assert by_path["/outcome"] == "missing required field: outcome"
    assert by_path["/events/0/id"] == "missing non-empty id"
    assert by_path["/events/0/type"] == "unknown type 'unknown'"
    assert by_path["/events/2/id"] == "event 'e1': duplicate id"


def test_load_trace_bundle_missing_required_field(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"trace_id": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required field: source"):
        load_trace_bundle(path)


def test_load_trace_bundle_duplicate_event_id(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "trace_id": "trace-1",
                "source": "unit-test",
                "task": "Do work",
                "events": [
                    {"id": "e1", "type": "user_message"},
                    {"id": "e1", "type": "final_answer"},
                ],
                "outcome": "success",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate id"):
        load_trace_bundle(path)


def test_load_trace_bundle_unknown_event_type(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "trace_id": "trace-1",
                "source": "unit-test",
                "task": "Do work",
                "events": [{"id": "e1", "type": "unknown"}],
                "outcome": "success",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown type 'unknown'"):
        load_trace_bundle(path)


def test_new_example_traces_load() -> None:
    for path in [
        "examples/traces/workflow_validation_order.json",
        "examples/traces/specialist_agent_governance_miss.json",
        "examples/traces/voice_slot_correction.json",
    ]:
        assert load_trace_bundle(path).trace_id


def test_workflow_validation_order_is_boring_trace() -> None:
    trace = load_trace_bundle("examples/traces/workflow_validation_order.json")
    assert LessonDetector().detect(trace) == []
