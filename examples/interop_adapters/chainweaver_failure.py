"""Adapter: a ChainWeaver flow-failure record -> a TraceBundle (issue #91).

ChainWeaver (dgenio/ChainWeaver) records a flow-failure when a multi-step flow
fails at one of its steps. This adapter maps one serialized flow-failure record
onto the documented trace schema, mapping each step to a ``workflow_step`` event
and the failing step to an ``error`` event. It implements the core
:class:`TraceImporter` protocol and takes **no dependency on ChainWeaver** — it
maps a plain dict.

The accepted shape is a best-effort contract (see ``README.md``); unknown keys
are ignored::

    {
      "kind": "chainweaver.flow_failure",
      "flow_id": "cw-checkout-001",
      "flow": "checkout_pipeline",
      "steps": [
        {"id": "s1", "name": "validate_cart", "status": "ok"},
        {"id": "s2", "name": "charge_card", "status": "failed", "error": "..."}
      ],
      "recovery": {"summary": "Re-ordered validation before the charge step."},
      "outcome": "corrected_by_human"
    }

Note: a flow-failure record carries ``steps`` (not ``events``), so it is not a
canonical lessonweaver trace until mapped here.

Run ``python chainweaver_failure.py`` to detect candidates from the sample.
"""

from __future__ import annotations

from typing import Any

from lessonweaver.models import TraceBundle, TraceEvent, TraceEventType


class ChainWeaverFailureImporter:
    """Map a serialized ChainWeaver flow-failure into a :class:`TraceBundle`."""

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        if "flow_failure" in str(source.get("kind", "")).lower():
            return True
        return "steps" in source and ("flow_id" in source or "flow" in source)

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        flow_id = str(source.get("flow_id") or source.get("id") or "").strip()
        if not flow_id:
            raise ValueError("ChainWeaver flow-failure missing a non-empty 'flow_id'.")
        steps = source.get("steps")
        if not isinstance(steps, list):
            raise ValueError("ChainWeaver flow-failure missing a 'steps' list.")

        events: list[TraceEvent] = []
        for index, step in enumerate(steps):
            step_id = str(step.get("id") or f"{flow_id}-s{index}")
            status = str(step.get("status", "")).lower()
            events.append(
                TraceEvent(
                    id=step_id,
                    type=TraceEventType.WORKFLOW_STEP,
                    content=str(step.get("name") or step_id),
                    status=status or None,
                    metadata={"step": step.get("name")},
                )
            )
            if status in {"failed", "error"}:
                events.append(
                    TraceEvent(
                        id=f"{step_id}-error",
                        type=TraceEventType.ERROR,
                        content=str(step.get("error") or f"Step '{step.get('name')}' failed."),
                    )
                )

        recovery = source.get("recovery")
        outcome = "failure"
        if isinstance(recovery, dict) and recovery.get("summary"):
            events.append(
                TraceEvent(
                    id=f"{flow_id}-recovery",
                    type=TraceEventType.HUMAN_CORRECTION,
                    content=str(recovery["summary"]),
                )
            )
            outcome = "corrected_by_human"

        return TraceBundle(
            trace_id=flow_id,
            source="chainweaver",
            task=str(source.get("flow") or "chainweaver flow"),
            events=events,
            outcome=str(source.get("outcome") or outcome),
            metadata={"adapter": "chainweaver_failure"},
        )


if __name__ == "__main__":
    import json
    from pathlib import Path

    from lessonweaver.detection import LessonDetector

    sample = json.loads(
        (Path(__file__).parent / "sample_chainweaver_failure.json").read_text(encoding="utf-8")
    )
    bundle = ChainWeaverFailureImporter().import_trace(sample)
    candidates = LessonDetector().detect(bundle)
    print(f"{len(candidates)} candidate(s) from chainweaver flow {bundle.trace_id}")
    for candidate in candidates:
        print(f"  - {candidate.id}: {candidate.summary}")
