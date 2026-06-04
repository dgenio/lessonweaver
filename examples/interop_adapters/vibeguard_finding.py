"""Adapter: a vibeguard finding -> a lessonweaver TraceBundle (issue #91).

vibeguard (dgenio/vibeguard) emits structured findings when it reviews an
agent-generated change. This adapter maps one serialized finding onto the
documented trace schema so the normal ``detect -> review -> approve -> export``
loop can mine it. It implements the core :class:`TraceImporter` protocol and
takes **no dependency on vibeguard** — it maps a plain dict, never importing the
sibling.

The accepted shape is a best-effort contract (see ``README.md``); unknown keys
are ignored::

    {
      "tool": "vibeguard",
      "finding_id": "VG-SECRET-01",
      "severity": "high",
      "path": "src/config.py",
      "message": "Hardcoded secret detected in config loader.",
      "task": "Review agent-generated change before merge",
      "remediation": "Replace hardcoded secret with an env var lookup."
    }

Run ``python vibeguard_finding.py`` to detect candidates from the sample.
"""

from __future__ import annotations

from typing import Any

from lessonweaver.models import TraceBundle, TraceEvent, TraceEventType


class VibeguardFindingImporter:
    """Map a serialized vibeguard finding into a :class:`TraceBundle`."""

    def can_import(self, source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        if str(source.get("tool", "")).lower() == "vibeguard":
            return True
        return "finding_id" in source and "message" in source

    def import_trace(self, source: dict[str, Any]) -> TraceBundle:
        finding_id = str(source.get("finding_id") or source.get("id") or "").strip()
        if not finding_id:
            raise ValueError("vibeguard finding missing a non-empty 'finding_id'.")

        events: list[TraceEvent] = [
            TraceEvent(
                id=f"{finding_id}-finding",
                type=TraceEventType.EVALUATION_RESULT,
                content=str(source.get("message") or "vibeguard finding."),
                status="failed",
                metadata={
                    "finding_id": finding_id,
                    "severity": source.get("severity"),
                    "path": source.get("path"),
                },
            )
        ]
        outcome = "failure"
        remediation = source.get("remediation")
        if remediation:
            events.append(
                TraceEvent(
                    id=f"{finding_id}-fix",
                    type=TraceEventType.HUMAN_CORRECTION,
                    content=str(remediation),
                )
            )
            outcome = "corrected_by_human"

        return TraceBundle(
            trace_id=finding_id,
            source="vibeguard",
            task=str(source.get("task") or "Review agent-generated change before merge"),
            events=events,
            outcome=str(source.get("outcome") or outcome),
            metadata={"adapter": "vibeguard_finding"},
        )


if __name__ == "__main__":
    import json
    from pathlib import Path

    from lessonweaver.detection import LessonDetector

    sample = json.loads(
        (Path(__file__).parent / "sample_vibeguard_finding.json").read_text(encoding="utf-8")
    )
    bundle = VibeguardFindingImporter().import_trace(sample)
    candidates = LessonDetector().detect(bundle)
    print(f"{len(candidates)} candidate(s) from vibeguard finding {bundle.trace_id}")
    for candidate in candidates:
        print(f"  - {candidate.id}: {candidate.summary}")
