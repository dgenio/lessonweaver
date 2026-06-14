"""Optional Model Context Protocol server for lessonweaver.

The core tool adapter is dependency-free so importing :mod:`lessonweaver` never
requires the optional MCP SDK. ``create_server`` and ``main`` lazy-load the SDK
only when the ``lessonweaver-mcp`` entry point is used.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from typing import Any

from .compile import InclusionLevel
from .detection import LessonDetector
from .diagnostics import explain_load
from .importers import DictTraceImporter
from .loader import SkillLoader
from .models import LessonCandidate, LessonStatus, TraceBundle
from .registry import FileSystemRegistry
from .retrieval import RetrievalQuery
from .sanitization import TraceSanitizer

_TOOL_NAMES = [
    "submit_trace",
    "list_pending_candidates",
    "get_candidate",
    "load_skills",
    "explain_load",
]


class LessonWeaverMcpTools:
    """Dependency-free implementation behind the MCP tool surface."""

    def __init__(
        self,
        registry: FileSystemRegistry | None = None,
        detector: LessonDetector | None = None,
        sanitizer: TraceSanitizer | None = None,
    ) -> None:
        self.registry = registry or FileSystemRegistry()
        self.detector = detector or LessonDetector()
        self.sanitizer = sanitizer or TraceSanitizer()

    def tool_names(self) -> list[str]:
        """Return the exact MCP tools this adapter exposes."""
        return list(_TOOL_NAMES)

    def submit_trace(self, trace_json: dict[str, Any] | str) -> dict[str, Any]:
        """Validate, sanitize, detect, and save candidate lessons from a trace."""
        payload = _coerce_json_object(trace_json, "trace_json")
        bundle = DictTraceImporter().import_trace(payload)
        sanitized = self.sanitizer.sanitize(bundle)
        candidates = [
            self._with_mcp_metadata(candidate, sanitized)
            for candidate in self.detector.detect(sanitized)
        ]
        for candidate in candidates:
            self.registry.save_candidate(candidate)
        return {
            "saved": len(candidates),
            "candidates": [_candidate_summary(candidate) for candidate in candidates],
            "review_required": bool(candidates),
            "review_instructions": _review_instructions(),
        }

    def list_pending_candidates(self) -> dict[str, Any]:
        """List candidates that still require the human review gate."""
        candidates = [
            candidate
            for candidate in self.registry.list_candidates()
            if candidate.status in {LessonStatus.CANDIDATE, LessonStatus.NEEDS_REVIEW}
        ]
        return {
            "candidates": [_candidate_summary(candidate) for candidate in candidates],
            "review_required": bool(candidates),
            "review_instructions": _review_instructions(),
        }

    def get_candidate(self, candidate_id: str) -> dict[str, Any]:
        """Return one candidate with review guidance."""
        payload = self.registry.load_candidate(candidate_id).to_dict()
        payload["review_instructions"] = _review_instructions(candidate_id)
        return payload

    def load_skills(
        self,
        task: str,
        agent_type: str = "",
        tools: list[str] | None = None,
        scope: str = "",
        risk_level: str = "",
        budget_chars: int = 2000,
        max_skills: int = 10,
        inclusion_level: str = "summary",
    ) -> dict[str, Any]:
        """Load reviewed skills into an agent-ready context snippet."""
        context = SkillLoader(self.registry).load_for_task(
            task=task,
            agent_type=agent_type,
            tools=tools or [],
            scope=scope,
            risk_level=risk_level,
            budget_chars=budget_chars,
            max_skills=max_skills,
            inclusion_level=inclusion_level,
        )
        return {
            "snippet": context.snippet,
            "included_skills": context.included_skills,
            "omitted_skills": context.omitted_skills,
            "total_chars": context.total_chars,
        }

    def explain_load(
        self,
        task: str,
        agent_type: str = "",
        tools: list[str] | None = None,
        scope: str = "",
        risk_level: str = "",
        budget_chars: int = 2000,
        max_skills: int = 10,
        inclusion_level: str = "summary",
    ) -> dict[str, Any]:
        """Explain why skills would load or be skipped for a task."""
        diagnostics = explain_load(
            self.registry.list_skills(),
            RetrievalQuery(
                task=task,
                agent_type=agent_type,
                tools=tools or [],
                scope=scope,
                risk_level=risk_level,
                max_results=max_skills,
            ),
            budget_chars=budget_chars,
            inclusion_level=InclusionLevel(inclusion_level),
            include_snippet=True,
        )
        return diagnostics.to_dict()

    def _with_mcp_metadata(
        self, candidate: LessonCandidate, sanitized: TraceBundle
    ) -> LessonCandidate:
        events_by_id = {event.id: event for event in sanitized.events}
        evidence_events = [
            {
                "id": event.id,
                "type": event.type.value,
                "content": event.content,
                "status": event.status,
                "success": event.success,
            }
            for event_id in candidate.evidence_event_ids
            if (event := events_by_id.get(event_id)) is not None
        ]
        metadata = dict(candidate.metadata)
        metadata["mcp"] = {
            "submitted_via": "lessonweaver-mcp",
            "trace_id": sanitized.trace_id,
            "sanitized_evidence_events": evidence_events,
        }
        return replace(candidate, metadata=metadata)


def create_server(registry_root: str | Path | None = None) -> Any:
    """Create a FastMCP server with lessonweaver's safe tool surface."""
    try:
        fastmcp_module = import_module("mcp.server.fastmcp")
    except ImportError as exc:  # pragma: no cover - exercised only without optional extra.
        raise RuntimeError(
            "The MCP server requires the optional dependency: pip install 'lessonweaver[mcp]'"
        ) from exc

    fast_mcp = fastmcp_module.FastMCP
    server = fast_mcp("lessonweaver")
    registry = FileSystemRegistry(registry_root)
    tools = LessonWeaverMcpTools(registry=registry)

    @server.tool()  # type: ignore[untyped-decorator]
    def submit_trace(trace_json: dict[str, Any] | str) -> dict[str, Any]:
        return tools.submit_trace(trace_json)

    @server.tool()  # type: ignore[untyped-decorator]
    def list_pending_candidates() -> dict[str, Any]:
        return tools.list_pending_candidates()

    @server.tool()  # type: ignore[untyped-decorator]
    def get_candidate(candidate_id: str) -> dict[str, Any]:
        return tools.get_candidate(candidate_id)

    @server.tool()  # type: ignore[untyped-decorator]
    def load_skills(
        task: str,
        agent_type: str = "",
        tools: list[str] | None = None,
        scope: str = "",
        risk_level: str = "",
        budget_chars: int = 2000,
        max_skills: int = 10,
        inclusion_level: str = "summary",
    ) -> dict[str, Any]:
        return LessonWeaverMcpTools(registry=registry).load_skills(
            task=task,
            agent_type=agent_type,
            tools=tools,
            scope=scope,
            risk_level=risk_level,
            budget_chars=budget_chars,
            max_skills=max_skills,
            inclusion_level=inclusion_level,
        )

    @server.tool()  # type: ignore[untyped-decorator]
    def explain_load(
        task: str,
        agent_type: str = "",
        tools: list[str] | None = None,
        scope: str = "",
        risk_level: str = "",
        budget_chars: int = 2000,
        max_skills: int = 10,
        inclusion_level: str = "summary",
    ) -> dict[str, Any]:
        return LessonWeaverMcpTools(registry=registry).explain_load(
            task=task,
            agent_type=agent_type,
            tools=tools,
            scope=scope,
            risk_level=risk_level,
            budget_chars=budget_chars,
            max_skills=max_skills,
            inclusion_level=inclusion_level,
        )

    return server


def main(argv: list[str] | None = None) -> int:
    """Run the stdio MCP server."""
    parser = argparse.ArgumentParser(description="Run the lessonweaver MCP server")
    parser.add_argument("--registry-root", help="Registry root shared with the CLI")
    args = parser.parse_args(argv)
    create_server(args.registry_root).run()
    return 0


def _coerce_json_object(value: dict[str, Any] | str, field_name: str) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must be valid JSON") from exc
    else:
        decoded = value
    if not isinstance(decoded, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return decoded


def _candidate_summary(candidate: LessonCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "summary": candidate.summary,
        "status": candidate.status.value,
        "risk_level": candidate.risk_level.value,
        "scope": candidate.scope.value,
        "confidence": candidate.confidence,
        "recommended_action_type": candidate.recommended_action_type.value,
        "evidence_trace_ids": list(candidate.evidence_trace_ids),
        "evidence_event_ids": list(candidate.evidence_event_ids),
    }


def _review_instructions(candidate_id: str | None = None) -> str:
    suffix = f" {candidate_id}" if candidate_id else ""
    return (
        "Human approval is intentionally not available through MCP. "
        f"Run `lessonweaver review{suffix}` or the guided CLI review flow before approving "
        "or promoting any candidate."
    )
