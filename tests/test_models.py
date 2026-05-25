from lessonweaver.traces import load_trace_bundle


def test_load_trace_bundle() -> None:
    trace = load_trace_bundle("examples/traces/github_pr_review_failure.json")
    assert trace.trace_id == "trace-gh-pr-review-001"
    assert trace.events[2].type.value == "human_correction"
