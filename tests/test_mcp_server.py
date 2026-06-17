import pytest

from lessonweaver.mcp_server import LessonWeaverMcpTools
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.registry import FileSystemRegistry


def _trace_payload(**metadata: object) -> dict[str, object]:
    return {
        "trace_id": "trace-1",
        "source": "pytest",
        "task": "review a pull request",
        "events": [
            {
                "id": "evt-1",
                "type": "human_correction",
                "content": "Do not paste Bearer abcdefghijklmnopqrstuvwxyz123456 tokens.",
            }
        ],
        "outcome": "corrected_by_human",
        "metadata": metadata,
    }


def _skill() -> SkillCard:
    return SkillCard(
        id="review-diff-first",
        name="Review Diff First",
        description="Inspect pull request diffs before commenting.",
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Open the changed files before writing review feedback."],
        anti_patterns=[],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.1.0",
        status=SkillStatus.ACTIVE,
    )


def test_mcp_tool_surface_excludes_human_approval_actions(tmp_path) -> None:
    tools = LessonWeaverMcpTools(registry=FileSystemRegistry(tmp_path))

    assert tools.tool_names() == [
        "submit_trace",
        "list_pending_candidates",
        "get_candidate",
        "load_skills",
        "explain_load",
    ]
    assert {"answer", "approve", "promote_skill"}.isdisjoint(tools.tool_names())


def test_submit_trace_sanitizes_and_saves_pending_candidates(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    tools = LessonWeaverMcpTools(registry=registry)

    result = tools.submit_trace(_trace_payload())

    assert result["saved"] == 1
    assert result["review_required"] is True
    assert "lessonweaver interview <candidate-id>" in result["review_instructions"]
    assert "lessonweaver review" not in result["review_instructions"]
    [candidate] = registry.list_candidates()
    assert candidate.id == result["candidates"][0]["id"]
    evidence_events = candidate.metadata["mcp"]["sanitized_evidence_events"]
    assert "[REDACTED by bearer_token]" in evidence_events[0]["content"]
    assert "Bearer abcdefghijklmnopqrstuvwxyz123456" not in evidence_events[0]["content"]


def test_submit_trace_sanitizes_metadata_backed_candidates(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    tools = LessonWeaverMcpTools(registry=registry)

    tools.submit_trace(
        _trace_payload(
            lesson_candidate=True,
            lesson_problem="Customer email admin@example.com leaked.",
            lesson_note="Never persist Bearer abcdefghijklmnopqrstuvwxyz123456.",
            nested={"owner": "ops@example.com"},
        )
    )

    candidates = {candidate.id: candidate for candidate in registry.list_candidates()}
    candidate = candidates["trace-1-metadata-flag"]
    assert "[REDACTED by email]" in candidate.observed_problem
    assert "[REDACTED by bearer_token]" in candidate.proposed_lesson
    assert "admin@example.com" not in candidate.observed_problem
    assert "Bearer abcdefghijklmnopqrstuvwxyz123456" not in candidate.proposed_lesson


def test_submit_trace_reports_invalid_trace_without_saving(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    tools = LessonWeaverMcpTools(registry=registry)

    with pytest.raises(ValueError, match="Invalid trace bundle"):
        tools.submit_trace({"trace_id": "broken", "events": []})

    assert registry.list_candidates() == []


def test_list_and_get_pending_candidates_return_review_guidance(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    tools = LessonWeaverMcpTools(registry=registry)
    submitted = tools.submit_trace(_trace_payload())

    pending = tools.list_pending_candidates()
    candidate = tools.get_candidate(str(submitted["candidates"][0]["id"]))

    assert [item["id"] for item in pending["candidates"]] == [candidate["id"]]
    assert pending["review_required"] is True
    assert candidate["status"] == "candidate"
    assert "lessonweaver interview <candidate-id>" in pending["review_instructions"]
    assert f"lessonweaver interview {candidate['id']}" in candidate["review_instructions"]


def test_load_skills_matches_skill_loader_output(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    tools = LessonWeaverMcpTools(registry=registry)

    result = tools.load_skills(
        task="Review this pull request",
        agent_type="coding-agent",
        tools=["git"],
        budget_chars=500,
    )

    assert result["included_skills"] == ["review-diff-first"]
    assert "Review Diff First" in result["snippet"]
    assert result["total_chars"] == len(result["snippet"])


def test_explain_load_returns_diagnostics_with_snippet(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    tools = LessonWeaverMcpTools(registry=registry)

    result = tools.explain_load(task="Review this pull request", budget_chars=500)

    assert [item["skill_id"] for item in result["loaded"]] == ["review-diff-first"]
    assert "Review Diff First" in result["snippet"]
