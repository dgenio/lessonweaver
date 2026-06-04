"""Adapter: an agent-kernel ActionTrace -> a lessonweaver TraceBundle (issue #91).

agent-kernel (dgenio/agent-kernel) records an ``ActionTrace``: an ordered list
of actions an agent took toward a goal, each with a type and a status. This
adapter maps one serialized ActionTrace onto the documented trace schema so
lessonweaver can mine it. It implements the core :class:`TraceImporter` protocol
and takes **no dependency on agent-kernel** — it maps a plain dict.

The accepted shape is a best-effort contract (see ``README.md``); unknown keys
are ignored::

    {
      "kind": "agent_kernel.ActionTrace",
      "trace_id": "ak-deploy-001",
      "goal": "Ship the release",
      "actions": [
        {"id": "a1", "type": "tool_call", "status": "error", "output": "..."},
        {"id": "a2", "type": "tool_call", "status": "ok", "output": "..."}
      ],
      "result": "success"
    }

Note: an ActionTrace carries ``actions`` (not ``events``), so it is not a
canonical lessonweaver trace until mapped here.

Run ``python agent_kernel_actiontrace.py`` to detect candidates from the sample.
"""

from __future__ import annotations

from typing import Any

from lessonweaver.models import TraceBundle, TraceEvent, TraceEventType

# Map agent-kernel action types onto trace event types; unknown types fall back
# to a tool_call so the action is still represented.
_ACTION_TYPE_MAP = {
    "tool_call": TraceEventType.TOOL_CALL,
    "tool_result": TraceEventType.TOOL_RESULT,
    "model_call": TraceEventType.MODEL_CALL,
    "message": TraceEventType.ASSISTANT_MESSAGE,
    "retry": TraceEventType.RETRY,
    "error": TraceEventType.ERROR,
}

# agent-kernel results -> trace outcomes.
_RESULT_MAP = {
    "success": "success",
    "ok": "success",
    "failure": "failure",
    "failed": "failure",
    "corrected": "corrected_by_human",
}


class AgentKernelActionTraceImporter:
    """Map a serialized agent-kernel ActionTrace into a :class:`TraceBundle`."""

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        if "actiontrace" in str(source.get("kind", "")).lower():
            return True
        return "actions" in source and isinstance(source.get("actions"), list)

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        trace_id = str(source.get("trace_id") or source.get("id") or "").strip()
        if not trace_id:
            raise ValueError("agent-kernel ActionTrace missing a non-empty 'trace_id'.")
        actions = source.get("actions")
        if not isinstance(actions, list):
            raise ValueError("agent-kernel ActionTrace missing an 'actions' list.")

        events: list[TraceEvent] = []
        for index, action in enumerate(actions):
            status = str(action.get("status", "")).lower()
            declared = str(action.get("type", "")).lower()
            # A failed action becomes an ERROR event regardless of its declared
            # type, which is what the detector's error->retry signal keys on.
            if status in {"error", "failed"}:
                event_type = TraceEventType.ERROR
            else:
                event_type = _ACTION_TYPE_MAP.get(declared, TraceEventType.TOOL_CALL)
            events.append(
                TraceEvent(
                    id=str(action.get("id") or f"{trace_id}-a{index}"),
                    type=event_type,
                    content=action.get("output"),
                    status="failed" if status in {"error", "failed"} else status or None,
                    success=False if status in {"error", "failed"} else None,
                    metadata={"action_type": declared} if declared else {},
                )
            )

        result = str(source.get("result", "")).lower()
        return TraceBundle(
            trace_id=trace_id,
            source="agent-kernel",
            task=str(source.get("goal") or "agent-kernel action trace"),
            events=events,
            outcome=_RESULT_MAP.get(result, "unknown"),
            metadata={"adapter": "agent_kernel_actiontrace"},
        )


if __name__ == "__main__":
    import json
    from pathlib import Path

    from lessonweaver.detection import LessonDetector

    sample = json.loads(
        (Path(__file__).parent / "sample_agent_kernel_actiontrace.json").read_text(encoding="utf-8")
    )
    bundle = AgentKernelActionTraceImporter().import_trace(sample)
    candidates = LessonDetector().detect(bundle)
    print(f"{len(candidates)} candidate(s) from agent-kernel trace {bundle.trace_id}")
    for candidate in candidates:
        print(f"  - {candidate.id}: {candidate.summary}")
