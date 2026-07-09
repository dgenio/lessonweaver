"""Tests for the optional MCP server (issues #141, #317-#320).

The deterministic contract layer (handlers, dispatch, tool definitions) is
tested without the ``mcp`` SDK. The thin SDK binding is smoke-tested behind
``importorskip`` so the suite still runs when the extra is absent.
"""

from __future__ import annotations

import builtins
from typing import Any

import pytest

from lessonweaver import mcp_server
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.registry import FileSystemRegistry


def _flagged_trace(trace_id: str = "trace-mcp-1", *, email: str | None = None) -> dict[str, Any]:
    """A minimal valid trace whose metadata flag deterministically yields a candidate."""
    content = "hello" if email is None else f"contact {email} for help"
    return {
        "trace_id": trace_id,
        "source": "test-agent",
        "task": "do something useful",
        "events": [{"id": "e1", "type": "user_message", "content": content}],
        "outcome": "success",
        "metadata": {"lesson_candidate": True},
    }


def _active_skill(skill_id: str = "pr") -> SkillCard:
    return SkillCard(
        id=skill_id,
        name="PR Diff First",
        description="Inspect diffs before reviewing pull requests.",
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Inspect changed files first"],
        anti_patterns=[],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=SkillStatus.ACTIVE,
    )


def _context(tmp_path) -> mcp_server.MCPServerContext:
    return mcp_server.MCPServerContext(registry_root=str(tmp_path))


# --- propose / read round trip ----------------------------------------------


def test_submit_trace_saves_candidates_listable_and_loadable(tmp_path) -> None:
    context = _context(tmp_path)

    submitted = mcp_server.dispatch_tool("submit_trace", {"trace": _flagged_trace()}, context)
    assert submitted["count"] == 1
    assert submitted["review_required"] is True
    candidate_id = submitted["saved_candidate_ids"][0]

    listed = mcp_server.dispatch_tool("list_pending_candidates", {}, context)
    assert [item["id"] for item in listed["candidates"]] == [candidate_id]

    fetched = mcp_server.dispatch_tool("get_candidate", {"candidate_id": candidate_id}, context)
    assert fetched["id"] == candidate_id


def test_detect_does_not_save(tmp_path) -> None:
    context = _context(tmp_path)
    result = mcp_server.dispatch_tool("detect", {"trace": _flagged_trace()}, context)
    assert result["count"] == 1
    assert FileSystemRegistry(str(tmp_path)).list_candidates() == []


def test_submit_trace_sanitizes_event_content_by_default(tmp_path) -> None:
    bundle = mcp_server._bundle_from_args(
        _context(tmp_path), {"trace": _flagged_trace(email="alice@example.com")}
    )
    assert "alice@example.com" not in bundle.events[0].content
    assert "[REDACTED by email]" in bundle.events[0].content


def test_submit_trace_sanitize_disabled_keeps_content(tmp_path) -> None:
    context = mcp_server.MCPServerContext(registry_root=str(tmp_path), sanitize=False)
    bundle = mcp_server._bundle_from_args(
        context, {"trace": _flagged_trace(email="alice@example.com")}
    )
    assert "alice@example.com" in bundle.events[0].content


def test_retrieve_and_load_skills_for_active_skill(tmp_path) -> None:
    context = _context(tmp_path)
    FileSystemRegistry(str(tmp_path)).save_skill(_active_skill())

    retrieved = mcp_server.dispatch_tool("retrieve", {"task": "Review this PR"}, context)
    assert [item["skill_id"] for item in retrieved["skills"]] == ["pr"]

    loaded = mcp_server.dispatch_tool(
        "load_skills", {"task": "Review this PR", "budget_chars": 200}, context
    )
    assert loaded["included_skills"] == ["pr"]
    assert "PR Diff First" in loaded["snippet"]


def test_explain_load_reports_loaded_skill(tmp_path) -> None:
    context = _context(tmp_path)
    FileSystemRegistry(str(tmp_path)).save_skill(_active_skill())
    explained = mcp_server.dispatch_tool("explain_load", {"task": "Review this PR"}, context)
    assert [item["skill_id"] for item in explained["loaded"]] == ["pr"]


# --- error paths ------------------------------------------------------------


def test_get_candidate_missing_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        mcp_server.dispatch_tool("get_candidate", {"candidate_id": "nope"}, _context(tmp_path))


def test_detect_invalid_trace_raises(tmp_path) -> None:
    with pytest.raises(ValueError, match="Invalid trace bundle"):
        mcp_server.dispatch_tool("detect", {"trace": {"trace_id": "x"}}, _context(tmp_path))


def test_detect_requires_trace_object(tmp_path) -> None:
    with pytest.raises(ValueError, match="must be a trace-bundle object"):
        mcp_server.dispatch_tool("detect", {"trace": "not-an-object"}, _context(tmp_path))


def test_query_tools_require_non_empty_task(tmp_path) -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        mcp_server.dispatch_tool("retrieve", {"task": "  "}, _context(tmp_path))


def test_dispatch_unknown_tool_raises(tmp_path) -> None:
    with pytest.raises(ValueError, match="unknown tool"):
        mcp_server.dispatch_tool("does_not_exist", {}, _context(tmp_path))


# --- review-gate safety (#319) ----------------------------------------------


def test_no_forbidden_tool_is_exposed() -> None:
    exposed = {tool.name for tool in mcp_server.TOOLS}
    assert exposed.isdisjoint(mcp_server.FORBIDDEN_TOOL_NAMES)


def test_exposed_tools_are_exactly_the_read_or_propose_surface() -> None:
    exposed = {tool.name for tool in mcp_server.TOOLS}
    assert exposed == {
        "detect",
        "submit_trace",
        "list_pending_candidates",
        "get_candidate",
        "retrieve",
        "load_skills",
        "explain_load",
    }


@pytest.mark.parametrize("name", ["approve", "promote-skill", "Promote_Skill"])
def test_validate_tool_names_rejects_gate_bypassing_tools(name: str) -> None:
    sneaky = mcp_server.McpTool(
        name=name,
        description="should never exist",
        input_schema={"type": "object", "properties": {}},
        handler=lambda context, arguments: {},
    )
    with pytest.raises(RuntimeError, match="review-gate operations"):
        mcp_server._validate_tool_names((sneaky,))


@pytest.mark.parametrize("name", ["publish", "grant", "approve_candidate"])
def test_validate_tool_names_rejects_unlisted_tools(name: str) -> None:
    # A verb that is not in FORBIDDEN_TOOL_NAMES must still be rejected: the
    # guard is an allowlist, so anything outside the vetted read/propose surface
    # fails fast rather than silently shipping a gate-bypassing tool.
    assert name.lower().replace("-", "_") not in mcp_server.FORBIDDEN_TOOL_NAMES
    unlisted = mcp_server.McpTool(
        name=name,
        description="not a vetted read/propose tool",
        input_schema={"type": "object", "properties": {}},
        handler=lambda context, arguments: {},
    )
    with pytest.raises(RuntimeError, match="vetted read/propose surface"):
        mcp_server._validate_tool_names((unlisted,))


# --- tool-call boundary validation ------------------------------------------


def test_sanitize_argument_must_be_boolean(tmp_path) -> None:
    with pytest.raises(ValueError, match="'sanitize' must be a boolean"):
        mcp_server.dispatch_tool(
            "detect", {"trace": _flagged_trace(), "sanitize": "false"}, _context(tmp_path)
        )


def test_null_budget_and_inclusion_fall_back_to_defaults(tmp_path) -> None:
    context = _context(tmp_path)
    FileSystemRegistry(str(tmp_path)).save_skill(_active_skill())
    loaded = mcp_server.dispatch_tool(
        "load_skills",
        {"task": "Review this PR", "budget_chars": None, "inclusion_level": None},
        context,
    )
    assert loaded["included_skills"] == ["pr"]


def test_budget_chars_must_be_integer(tmp_path) -> None:
    with pytest.raises(ValueError, match="'budget_chars' must be an integer"):
        mcp_server.dispatch_tool(
            "load_skills", {"task": "Review this PR", "budget_chars": "lots"}, _context(tmp_path)
        )


def test_budget_chars_rejects_boolean(tmp_path) -> None:
    with pytest.raises(ValueError, match="'budget_chars' must be an integer"):
        mcp_server.dispatch_tool(
            "explain_load", {"task": "Review this PR", "budget_chars": True}, _context(tmp_path)
        )


def test_budget_chars_rejects_value_below_minimum(tmp_path) -> None:
    # The SDK enforces the schema ``minimum`` before a handler runs; dispatch_tool
    # is the SDK-free contract layer, so it enforces the same bound itself.
    with pytest.raises(ValueError, match="'budget_chars' must be >= 0"):
        mcp_server.dispatch_tool(
            "load_skills", {"task": "Review this PR", "budget_chars": -1}, _context(tmp_path)
        )


def test_max_results_rejects_value_below_minimum(tmp_path) -> None:
    with pytest.raises(ValueError, match="'max_results' must be >= 1"):
        mcp_server.dispatch_tool(
            "retrieve", {"task": "Review this PR", "max_results": 0}, _context(tmp_path)
        )


def test_every_tool_has_an_object_input_schema() -> None:
    for tool in mcp_server.TOOLS:
        assert tool.input_schema["type"] == "object"
        assert "properties" in tool.input_schema
        for required in tool.input_schema.get("required", []):
            assert required in tool.input_schema["properties"]


# --- optional-dependency boundary -------------------------------------------


def test_build_server_without_mcp_raises_with_install_hint(monkeypatch) -> None:
    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("No module named 'mcp'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(RuntimeError, match=r"lessonweaver\[mcp\]"):
        mcp_server.build_server()


def test_main_reports_missing_mcp_without_traceback(monkeypatch, capsys) -> None:
    # Block the mcp import entirely so main() exercises the real path: the
    # missing dependency must surface as exit code 1 with an install hint, not
    # an uncaught ImportError from the stdio transport (the _serve_stdio order).
    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("No module named 'mcp'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    assert mcp_server.main([]) == 1
    assert "lessonweaver[mcp]" in capsys.readouterr().err


# --- SDK binding smoke test -------------------------------------------------


def test_build_server_registers_tool_handlers() -> None:
    pytest.importorskip("mcp")
    import mcp.types as types
    from mcp.server.lowlevel import Server

    server = mcp_server.build_server()
    assert isinstance(server, Server)
    assert server.name == "lessonweaver"
    assert types.ListToolsRequest in server.request_handlers
    assert types.CallToolRequest in server.request_handlers


def test_call_tool_handler_returns_structured_content(tmp_path) -> None:
    # Exercise the SDK binding's call path end to end (not just registration):
    # a dict handler result must surface as CallToolResult.structuredContent
    # with a JSON-text mirror in content.
    pytest.importorskip("mcp")
    import asyncio

    import mcp.types as types

    server = mcp_server.build_server(_context(tmp_path))
    handler = server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name="detect", arguments={"trace": _flagged_trace()}),
    )
    result = asyncio.run(handler(request)).root
    assert result.isError is False
    assert result.structuredContent["count"] == 1
    assert result.content[0].text  # JSON-text mirror of the structured payload
