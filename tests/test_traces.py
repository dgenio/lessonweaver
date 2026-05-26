import json

import pytest

from lessonweaver.detection import LessonDetector
from lessonweaver.traces import load_trace_bundle, validate_trace_dict


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
