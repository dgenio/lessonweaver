"""Minimal TraceRecorder example.

Run from the repository root:

    PYTHONPATH=src uvx --python 3.10 python examples/trace_recorder.py
    lessonweaver detect /tmp/lessonweaver-recorded-trace.json
"""

from __future__ import annotations

from pathlib import Path

from lessonweaver import record

OUTPUT = Path("/tmp/lessonweaver-recorded-trace.json")


with record(
    "python_agent",
    "Review a pull request",
    trace_id="trace-recorder-example",
    output=OUTPUT,
    sanitize=True,
) as trace:
    trace.user_message("Please review this PR.")
    trace.tool_call("github.diff", metadata={"args_shape": "owner/repo#number"})
    trace.agent_message("Looks good from the title.")
    trace.human_correction("Inspect changed files before review conclusions.")
    trace.set_outcome("corrected_by_human")

print(OUTPUT)
