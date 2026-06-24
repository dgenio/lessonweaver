"""Optional MCP server exposing the governed loop to agents (issues #141, #317-#320).

This module lets MCP-capable agent runtimes (Claude Code, Copilot, and other
clients) reach lessonweaver in-session: submit a trace, list and read the
resulting review-pending candidates, and load reviewed skills into context.
Approval stays exclusively a human action — the server can *propose* and *load*,
but it deliberately exposes no tool that answers review questions, approves, or
promotes a skill (#319).

Two layers live here:

* A deterministic, SDK-free contract layer (:data:`TOOLS`, :func:`dispatch_tool`)
  that wraps the existing public library APIs and returns JSON-serializable
  results. It imports only the standard library and lessonweaver, so it is fully
  unit-testable without the optional ``mcp`` dependency.
* A thin binding (:func:`build_server`, :func:`serve`, :func:`main`) that imports
  the reference ``mcp`` SDK *lazily* and maps each tool onto the low-level
  server. This keeps the base install dependency-free: ``import lessonweaver``
  never loads ``mcp`` (the package ``__init__`` does not import this module).

Install the server with the optional extra::

    pip install "lessonweaver[mcp]"
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .detection import LessonDetector
from .diagnostics import explain_load
from .importers import DictTraceImporter
from .loader import SkillLoader
from .models import LessonCandidate
from .registry import FileSystemRegistry
from .retrieval import RetrievalQuery, SkillRetriever
from .sanitization import TraceSanitizer

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mcp.server.lowlevel import Server

# Tool names that would let a model bypass the human review gate. No exposed
# tool may use one of these; :func:`_validate_tool_names` enforces it at import
# time so a regression fails fast rather than shipping a gate-bypassing surface.
FORBIDDEN_TOOL_NAMES = frozenset(
    {"answer", "approve", "promote", "promote_skill", "reject", "review"}
)

_MISSING_MCP_MESSAGE = (
    "The lessonweaver MCP server requires the optional 'mcp' dependency. "
    "Install it with: pip install 'lessonweaver[mcp]'"
)


@dataclass(slots=True)
class MCPServerContext:
    """Runtime configuration shared by every tool handler.

    ``sanitize`` controls whether traces submitted by an agent are scrubbed with
    :class:`TraceSanitizer` before mining. It defaults to ``True`` because
    submitted trace content is untrusted input (see the threat model in
    ``docs/integrations/mcp.md`` and the instruction-poisoning work in #137).
    """

    registry_root: str | None = None
    sanitize: bool = True

    def registry(self) -> FileSystemRegistry:
        return FileSystemRegistry(self.registry_root)


ToolHandler = Callable[[MCPServerContext, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class McpTool:
    """A single MCP tool: its name, description, input schema, and handler.

    The handler is a plain synchronous function over the deterministic library,
    so it can be called and asserted on directly in tests without the SDK.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


# --- shared JSON Schema fragments -------------------------------------------

_TRACE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "A lessonweaver trace bundle (see docs/trace-format.md).",
}

_TASK_QUERY_PROPERTIES: dict[str, Any] = {
    "task": {"type": "string", "description": "The task the agent is about to perform."},
    "agent_type": {"type": "string", "description": "Optional agent role/type hint."},
    "tools": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional tool names available to the agent.",
    },
    "scope": {"type": "string", "description": "Optional scope filter (e.g. project)."},
    "risk_level": {"type": "string", "description": "Optional maximum risk level."},
    "max_results": {"type": "integer", "description": "Maximum skills to consider.", "minimum": 1},
}

_SANITIZE_PROP: dict[str, Any] = {
    "type": "boolean",
    "description": "Scrub trace content before mining (defaults to the server setting).",
}

_BUDGET_PROP: dict[str, Any] = {
    "type": "integer",
    "description": "Character budget for the compiled context.",
    "minimum": 0,
}


def _candidates_payload(candidates: list[LessonCandidate]) -> dict[str, Any]:
    return {
        "count": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }


def _opt_bool(arguments: dict[str, Any], key: str, default: bool) -> bool:
    """Return a boolean tool argument, defaulting when absent or null.

    The schema declares these as booleans, so a non-boolean (e.g. the JSON
    string ``"false"``) is a client error rather than something to coerce
    silently — coercion here would let ``"false"`` enable sanitization.
    """
    value = arguments.get(key, default)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"argument '{key}' must be a boolean")
    return value


def _opt_int(arguments: dict[str, Any], key: str, default: int) -> int:
    """Return an integer tool argument, defaulting when absent or null."""
    value = arguments.get(key, default)
    if value is None:
        return default
    # bool is an int subclass; reject it so True/False is not read as 1/0.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"argument '{key}' must be an integer")
    return int(value)


def _opt_str(arguments: dict[str, Any], key: str, default: str) -> str:
    """Return a string tool argument, defaulting when absent or null."""
    value = arguments.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"argument '{key}' must be a string")
    return value


def _bundle_from_args(context: MCPServerContext, arguments: dict[str, Any]) -> Any:
    """Validate and build a trace bundle from tool arguments, optionally scrubbing.

    ``DictTraceImporter`` applies the same validation as the CLI loader and
    raises ``ValueError`` on an invalid trace, which the SDK surfaces to the
    caller as a tool error.
    """
    trace = arguments.get("trace")
    if not isinstance(trace, dict):
        raise ValueError("argument 'trace' must be a trace-bundle object")
    bundle = DictTraceImporter().import_trace(trace)
    if _opt_bool(arguments, "sanitize", context.sanitize):
        bundle = TraceSanitizer().sanitize(bundle)
    return bundle


def _query_from_args(arguments: dict[str, Any]) -> RetrievalQuery:
    task = arguments.get("task")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("argument 'task' must be a non-empty string")
    tools = arguments.get("tools") or []
    if not isinstance(tools, list) or not all(isinstance(item, str) for item in tools):
        raise ValueError("argument 'tools' must be a list of strings")
    return RetrievalQuery(
        task=task,
        agent_type=_opt_str(arguments, "agent_type", ""),
        tools=list(tools),
        scope=_opt_str(arguments, "scope", ""),
        risk_level=_opt_str(arguments, "risk_level", ""),
        max_results=_opt_int(arguments, "max_results", 10),
    )


# --- tool handlers (deterministic, SDK-free) --------------------------------


def _handle_detect(context: MCPServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    bundle = _bundle_from_args(context, arguments)
    candidates = LessonDetector().detect(bundle)
    return _candidates_payload(candidates)


def _handle_submit_trace(context: MCPServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    bundle = _bundle_from_args(context, arguments)
    candidates = LessonDetector().detect(bundle)
    registry = context.registry()
    for candidate in candidates:
        registry.save_candidate(candidate)
    payload = _candidates_payload(candidates)
    payload["saved_candidate_ids"] = [candidate.id for candidate in candidates]
    payload["review_required"] = True
    payload["next_step"] = (
        "Saved candidates are review-pending. A human must review and approve them "
        "with the lessonweaver CLI (interview/answer/approve); this server cannot "
        "answer review questions, approve, or promote a skill."
    )
    return payload


def _handle_list_pending_candidates(
    context: MCPServerContext, arguments: dict[str, Any]
) -> dict[str, Any]:
    candidates = context.registry().list_candidates()
    return {
        "count": len(candidates),
        "candidates": [
            {"id": candidate.id, "summary": candidate.summary} for candidate in candidates
        ],
    }


def _handle_get_candidate(context: MCPServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    candidate_id = arguments.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("argument 'candidate_id' must be a non-empty string")
    return context.registry().load_candidate(candidate_id).to_dict()


def _handle_retrieve(context: MCPServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    query = _query_from_args(arguments)
    skills = context.registry().list_skills()
    diagnostics = SkillRetriever().diagnose(skills, query)
    return {
        "count": len(diagnostics.selected),
        "skills": [
            {
                "skill_id": result.skill.id,
                "score": result.score,
                "match_reason": result.match_reason,
            }
            for result in diagnostics.selected
        ],
        "skipped": [skipped.to_dict() for skipped in diagnostics.skipped],
    }


def _handle_load_skills(context: MCPServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    query = _query_from_args(arguments)
    budget_chars = _opt_int(arguments, "budget_chars", 2000)
    inclusion_level = _opt_str(arguments, "inclusion_level", "summary")
    compiled = SkillLoader(registry=context.registry()).load_for_task(
        task=query.task,
        agent_type=query.agent_type,
        tools=query.tools,
        scope=query.scope,
        risk_level=query.risk_level,
        budget_chars=budget_chars,
        max_skills=query.max_results,
        inclusion_level=inclusion_level,
    )
    return {
        "snippet": compiled.snippet,
        "included_skills": compiled.included_skills,
        "omitted_skills": compiled.omitted_skills,
        "total_chars": compiled.total_chars,
    }


def _handle_explain_load(context: MCPServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    query = _query_from_args(arguments)
    budget_chars = _opt_int(arguments, "budget_chars", 2000)
    skills = context.registry().list_skills()
    diagnostics = explain_load(skills, query, budget_chars=budget_chars)
    return diagnostics.to_dict()


TOOLS: tuple[McpTool, ...] = (
    McpTool(
        name="detect",
        description=(
            "Detect candidate lessons in a trace bundle without saving them. "
            "Read-only; nothing is written to the registry."
        ),
        input_schema={
            "type": "object",
            "properties": {"trace": _TRACE_SCHEMA, "sanitize": _SANITIZE_PROP},
            "required": ["trace"],
        },
        handler=_handle_detect,
    ),
    McpTool(
        name="submit_trace",
        description=(
            "Validate, sanitize, and mine a trace, saving any detected candidates "
            "as review-pending. This proposes candidates only; it never approves "
            "or promotes them."
        ),
        input_schema={
            "type": "object",
            "properties": {"trace": _TRACE_SCHEMA, "sanitize": _SANITIZE_PROP},
            "required": ["trace"],
        },
        handler=_handle_submit_trace,
    ),
    McpTool(
        name="list_pending_candidates",
        description="List review-pending candidate lessons in the registry. Read-only.",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_list_pending_candidates,
    ),
    McpTool(
        name="get_candidate",
        description="Fetch a single candidate lesson by id. Read-only.",
        input_schema={
            "type": "object",
            "properties": {
                "candidate_id": {"type": "string", "description": "The candidate id to fetch."}
            },
            "required": ["candidate_id"],
        },
        handler=_handle_get_candidate,
    ),
    McpTool(
        name="retrieve",
        description="Rank active skills relevant to a task. Read-only.",
        input_schema={
            "type": "object",
            "properties": dict(_TASK_QUERY_PROPERTIES),
            "required": ["task"],
        },
        handler=_handle_retrieve,
    ),
    McpTool(
        name="load_skills",
        description=(
            "Compile reviewed, active skills relevant to a task into a "
            "context-budgeted prompt snippet. Read-only."
        ),
        input_schema={
            "type": "object",
            "properties": {
                **_TASK_QUERY_PROPERTIES,
                "budget_chars": _BUDGET_PROP,
                "inclusion_level": {
                    "type": "string",
                    "description": "Rendering level (none, name_only, summary, full, ...).",
                },
            },
            "required": ["task"],
        },
        handler=_handle_load_skills,
    ),
    McpTool(
        name="explain_load",
        description=(
            "Explain which skills would load for a task and why, including skip "
            "reasons, budget usage, and overlaps. Read-only."
        ),
        input_schema={
            "type": "object",
            "properties": {**_TASK_QUERY_PROPERTIES, "budget_chars": _BUDGET_PROP},
            "required": ["task"],
        },
        handler=_handle_explain_load,
    ),
)


def _validate_tool_names(tools: tuple[McpTool, ...]) -> None:
    """Fail fast if any exposed tool would bypass the human review gate.

    Names are normalized (lowercased, ``-`` -> ``_``) before comparison so a
    kebab-case alias such as ``promote-skill`` cannot slip past the check.
    """
    forbidden = sorted(
        tool.name for tool in tools if tool.name.lower().replace("-", "_") in FORBIDDEN_TOOL_NAMES
    )
    if forbidden:
        raise RuntimeError(f"MCP tools must not expose review-gate operations: {forbidden}")


_validate_tool_names(TOOLS)

_TOOLS_BY_NAME: dict[str, McpTool] = {tool.name: tool for tool in TOOLS}


def dispatch_tool(
    name: str, arguments: dict[str, Any], context: MCPServerContext
) -> dict[str, Any]:
    """Route a tool call to its handler and return a JSON-serializable result."""
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ValueError(f"unknown tool: {name}")
    return tool.handler(context, arguments)


# --- MCP SDK binding (lazy import) ------------------------------------------


def build_server(context: MCPServerContext | None = None) -> Server:
    """Build a low-level MCP ``Server`` wiring :data:`TOOLS` to the dispatcher.

    Raises ``RuntimeError`` with install guidance if the optional ``mcp``
    dependency is not installed.
    """
    context = context or MCPServerContext()
    try:
        import mcp.types as types
        from mcp.server.lowlevel import Server
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch in tests
        raise RuntimeError(_MISSING_MCP_MESSAGE) from exc

    _validate_tool_names(TOOLS)
    server: Server = Server("lessonweaver")

    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(name=tool.name, description=tool.description, inputSchema=tool.input_schema)
            for tool in TOOLS
        ]

    async def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return dispatch_tool(name, arguments or {}, context)

    # Register imperatively through an Any-typed alias rather than with the
    # ``@server.list_tools()`` decorator syntax. The SDK's decorators are not
    # precisely typed, and under mypy --strict a decorator/call resolving to an
    # untyped object trips ``untyped-decorator`` (older mypy) or
    # ``no-untyped-call`` (newer mypy) on different lines. Going through ``Any``
    # without decorator syntax keeps registration version-robust and free of
    # error-code-specific ignores, while ``server`` keeps its real type for the
    # return value.
    registrar: Any = server
    registrar.list_tools()(_list_tools)
    registrar.call_tool()(_call_tool)

    return server


async def _serve_stdio(context: MCPServerContext) -> None:
    # Build first: build_server() converts a missing 'mcp' extra into a
    # user-friendly RuntimeError. Importing the stdio transport before that
    # would raise a raw ImportError that main() does not catch.
    server = build_server(context)
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def serve(context: MCPServerContext | None = None) -> None:
    """Run the MCP server over stdio until the client disconnects."""
    import asyncio

    asyncio.run(_serve_stdio(context or MCPServerContext()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lessonweaver-mcp",
        description="Run the lessonweaver MCP server (stdio) under the human review gate.",
    )
    parser.add_argument("--registry-root", help="Registry root (defaults to the CLI default).")
    parser.add_argument(
        "--no-sanitize",
        action="store_true",
        help="Do not scrub submitted trace content before mining (not recommended).",
    )
    args = parser.parse_args(argv)
    try:
        serve(MCPServerContext(registry_root=args.registry_root, sanitize=not args.no_sanitize))
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
