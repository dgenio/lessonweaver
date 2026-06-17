"""Export helpers for approved lessons and skill cards."""

from __future__ import annotations

import json
from typing import Any, Protocol, TypeVar

from .events import LifecycleEvent, LifecycleEventType, emitter
from .models import LessonCandidate, OperationalLesson, SkillCard

_T = TypeVar("_T")


class Redactor(Protocol):
    def redact(self, text: str) -> str: ...


def _text(value: str, redactor: Redactor | None) -> str:
    return redactor.redact(value) if redactor is not None else value


def _list(values: list[str], redactor: Redactor | None) -> list[str]:
    return [_text(value, redactor) for value in values]


def _redact_payload(value: Any, redactor: Redactor | None) -> Any:
    if redactor is None:
        return value
    if isinstance(value, str):
        return redactor.redact(value)
    if isinstance(value, list):
        return [_redact_payload(item, redactor) for item in value]
    if isinstance(value, dict):
        return {key: _redact_payload(item, redactor) for key, item in value.items()}
    return value


def _emit_export(subject_id: str, export_format: str) -> None:
    emitter.emit(
        LifecycleEvent(
            LifecycleEventType.SKILL_EXPORTED,
            subject_id,
            {"format": export_format},
        )
    )


def _with_export_event(subject_id: str, export_format: str, rendered: _T) -> _T:
    _emit_export(subject_id, export_format)
    return rendered


def _section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend(["", f"## {title}", *[f"- {item}" for item in items]])


def export_skillcard_markdown(skill: SkillCard, redactor: Redactor | None = None) -> str:
    """Render a SkillCard as Markdown.

    Callers are responsible for ensuring skills do not contain raw trace content before export.
    Use SimpleRedactor as a safety net, not as the primary privacy control.
    """
    lines = [
        f"# {_text(skill.name, redactor)}",
        "",
        "## Description",
        _text(skill.description, redactor),
    ]
    _section(lines, "Use when", _list(skill.applies_when, redactor))
    _section(lines, "Do not use when", _list(skill.does_not_apply_when, redactor))
    _section(lines, "Instructions", _list(skill.instructions, redactor))
    _section(lines, "Anti-patterns", _list(skill.anti_patterns, redactor))
    _section(
        lines,
        "Evidence",
        [f"trace: {_text(trace_id, redactor)}" for trace_id in skill.evidence_trace_ids],
    )
    lines.extend(
        [
            "",
            "## Governance",
            f"- Confidence: {skill.confidence:.2f}",
            f"- Risk: {skill.risk_level.value}",
            f"- Scope: {skill.scope.value}",
            f"- Version: {_text(skill.version, redactor)}",
            f"- Status: {skill.status.value}",
            f"- Sensitivity: {skill.sensitivity.value}",
        ]
    )
    return _with_export_event(skill.id, "markdown", "\n".join(lines).strip() + "\n")


def export_operational_lesson_markdown(
    lesson: OperationalLesson, redactor: Redactor | None = None
) -> str:
    """Render an approved operational lesson as Markdown."""
    lines = [
        f"# Operational Lesson: {_text(lesson.title, redactor)}",
        "",
        "## Summary",
        _text(lesson.summary, redactor),
    ]
    _section(lines, "Instructions", _list(lesson.instructions, redactor))
    _section(lines, "Applies when", _list(lesson.applies_when, redactor))
    _section(lines, "Does not apply when", _list(lesson.does_not_apply_when, redactor))
    _section(lines, "Anti-patterns", _list(lesson.anti_patterns, redactor))
    _section(
        lines,
        "Evidence",
        [f"trace: {_text(trace_id, redactor)}" for trace_id in lesson.evidence_trace_ids],
    )
    lines.extend(
        [
            "",
            "## Governance",
            f"- Risk: {lesson.risk_level.value}",
            f"- Scope: {lesson.scope.value}",
            f"- Action type: {lesson.recommended_action_type.value}",
            f"- Confidence: {lesson.confidence:.2f}",
            f"- Status: {lesson.status.value}",
        ]
    )
    return _with_export_event(
        lesson.lesson_id,
        "operational_lesson_markdown",
        "\n".join(lines).strip() + "\n",
    )


def export_skillcard_json(skill: SkillCard, redactor: Redactor | None = None) -> str:
    return _with_export_event(
        skill.id,
        "json",
        json.dumps(_redact_payload(skill.to_dict(), redactor), indent=2, sort_keys=True),
    )


def export_copilot_instruction_fragment(skill: SkillCard, redactor: Redactor | None = None) -> str:
    return _with_export_event(
        skill.id,
        "copilot_instruction",
        (
            f"- Skill: {_text(skill.name, redactor)}\n"
            f"- Use when: {'; '.join(_list(skill.applies_when, redactor))}\n"
            f"- Avoid when: {'; '.join(_list(skill.does_not_apply_when, redactor))}\n"
            f"- Do: {'; '.join(_list(skill.instructions, redactor))}"
        ),
    )


def export_claude_skill_fragment(skill: SkillCard, redactor: Redactor | None = None) -> str:
    instruction_block = "\n".join(f"- {line}" for line in _list(skill.instructions, redactor))
    return _with_export_event(
        skill.id,
        "claude_skill",
        (
            f"## {_text(skill.name, redactor)}\n\n"
            f"Description: {_text(skill.description, redactor)}\n\n"
            "When to apply:\n- "
            + "\n- ".join(_list(skill.applies_when, redactor))
            + "\n\nInstructions:\n"
            + instruction_block
        ),
    )


def export_runtime_prompt_snippet(skill: SkillCard, redactor: Redactor | None = None) -> str:
    return _with_export_event(
        skill.id,
        "runtime_snippet",
        (
            "Operational lesson:\n"
            f"{_text(skill.description, redactor)}\n"
            f"Applies when: {'; '.join(_list(skill.applies_when, redactor))}\n"
            f"Do not apply when: {'; '.join(_list(skill.does_not_apply_when, redactor))}\n"
            f"Required behaviors: {'; '.join(_list(skill.instructions, redactor))}"
        ),
    )


def export_agents_md_fragment(skill: SkillCard, redactor: Redactor | None = None) -> str:
    """Render a SkillCard as an AGENTS.md-compatible fragment.

    Review the fragment before appending it to AGENTS.md; it is intentionally
    compact and must not be auto-appended or contain raw trace evidence. The
    leading HTML comment lets future tooling find lessonweaver-managed sections.
    """
    lines = [
        f"<!-- lessonweaver skill_id={skill.id} confidence={skill.confidence:.2f} -->",
        f"### {_text(skill.name, redactor)}",
        "",
        f"**When to apply:** {'; '.join(_list(skill.applies_when, redactor))}",
    ]
    if skill.does_not_apply_when:
        lines.append(
            f"**Do not apply when:** {'; '.join(_list(skill.does_not_apply_when, redactor))}"
        )
    lines.append("")
    lines.extend(f"- {item}" for item in _list(skill.instructions, redactor))
    return _with_export_event(skill.id, "agents-md", "\n".join(lines).strip() + "\n")


def export_copilot_repo_instruction(skill: SkillCard, redactor: Redactor | None = None) -> str:
    """Render a SkillCard as a repository-wide GitHub Copilot instruction block.

    Append the output to .github/copilot-instructions.md after review. The HTML
    comment header carries the skill id and version for future deduplication.
    """
    lines = [
        f"<!-- lessonweaver skill_id={skill.id} version={_text(skill.version, redactor)} -->",
        f"## {_text(skill.name, redactor)}",
        "",
        _text(skill.description, redactor),
        "",
        f"**Apply when:** {'; '.join(_list(skill.applies_when, redactor))}",
    ]
    if skill.does_not_apply_when:
        lines.append(
            f"**Do not apply when:** {'; '.join(_list(skill.does_not_apply_when, redactor))}"
        )
    lines.extend(["", "**Instructions:**"])
    lines.extend(f"- {item}" for item in _list(skill.instructions, redactor))
    return _with_export_event(skill.id, "copilot-repo", "\n".join(lines).strip() + "\n")


def export_copilot_path_instruction(
    skill: SkillCard, applies_to_glob: str = "**", redactor: Redactor | None = None
) -> str:
    """Render a SkillCard as a path-specific Copilot instructions file.

    Intended for .github/instructions/{skill.id}.instructions.md. The applyTo
    frontmatter scopes the instructions to matching file paths.
    """
    lines = [
        "---",
        f"applyTo: {json.dumps(applies_to_glob)}",
        "---",
        "",
        f"# {_text(skill.name, redactor)}",
        "",
        _text(skill.description, redactor),
    ]
    _section(lines, "When to apply", _list(skill.applies_when, redactor))
    _section(lines, "When not to apply", _list(skill.does_not_apply_when, redactor))
    _section(lines, "Required behaviors", _list(skill.instructions, redactor))
    return _with_export_event(skill.id, "copilot-path", "\n".join(lines).strip() + "\n")


def export_claude_skill_md(skill: SkillCard, redactor: Redactor | None = None) -> str:
    """Render a SkillCard as a Claude Code SKILL.md document.

    Claude Code formats may evolve; treat the output as reviewed project guidance,
    not a guaranteed integration. Empty sections are suppressed.
    """
    lines = [
        f"# {_text(skill.name, redactor)}",
        "",
        _text(skill.description, redactor),
    ]
    _section(lines, "When to use", _list(skill.applies_when, redactor))
    _section(lines, "When NOT to use", _list(skill.does_not_apply_when, redactor))
    _section(lines, "Instructions", _list(skill.instructions, redactor))
    _section(lines, "Anti-patterns", _list(skill.anti_patterns, redactor))
    metadata = [
        f"Confidence: {skill.confidence:.2f}",
        f"Risk: {skill.risk_level.value}",
    ]
    if skill.evidence_trace_ids:
        metadata.append(f"Evidence: {', '.join(_list(skill.evidence_trace_ids, redactor))}")
    _section(lines, "Metadata", metadata)
    return _with_export_event(skill.id, "claude-skill-md", "\n".join(lines).strip() + "\n")


def export_claude_rule_fragment(skill: SkillCard, redactor: Redactor | None = None) -> str:
    """Render a SkillCard as a concise rule fragment for .claude/rules/."""
    return _with_export_event(
        skill.id,
        "claude-rule",
        (
            f"# Rule: {_text(skill.name, redactor)}\n\n"
            f"**Applies when:** {'; '.join(_list(skill.applies_when, redactor))}\n\n"
            f"**Do:** {'; '.join(_list(skill.instructions, redactor))}\n\n"
            f"**Avoid:** {'; '.join(_list(skill.anti_patterns, redactor))}"
        ),
    )


def export_claude_md_snippet(skill: SkillCard, redactor: Redactor | None = None) -> str:
    """Render a SkillCard as a short, appendable CLAUDE.md block."""
    return _with_export_event(
        skill.id,
        "claude-md",
        (
            f"## Operational guidance: {_text(skill.name, redactor)}\n\n"
            f"{_text(skill.description, redactor)}\n\n"
            f"When: {'; '.join(_list(skill.applies_when, redactor))}. "
            f"Required: {'; '.join(_list(skill.instructions, redactor))}."
        ),
    )


def export_codex_skill_directory(
    skill: SkillCard, redactor: Redactor | None = None
) -> dict[str, str]:
    """Render a SkillCard as a Codex-compatible skill directory.

    Returns a mapping of file name to file content (a SKILL.md with YAML
    frontmatter plus a metadata.json sidecar). The caller decides where to write
    the files; this function does not touch disk. Frontmatter scalars are
    JSON-encoded so names/descriptions containing ``:``, ``#``, quotes, or
    newlines stay valid YAML.
    """
    description = _text(skill.description, redactor)
    name = _text(skill.name, redactor)
    skill_md_lines = [
        "---",
        f"name: {json.dumps(name)}",
        f"description: {json.dumps(description)}",
        "---",
        "",
        f"# {name}",
        "",
        description,
    ]
    _section(skill_md_lines, "When to use", _list(skill.applies_when, redactor))
    _section(skill_md_lines, "When not to use", _list(skill.does_not_apply_when, redactor))
    _section(skill_md_lines, "Instructions", _list(skill.instructions, redactor))
    _section(skill_md_lines, "Anti-patterns", _list(skill.anti_patterns, redactor))
    skill_md = "\n".join(skill_md_lines).strip() + "\n"

    metadata = {
        "id": skill.id,
        "name": name,
        "version": _text(skill.version, redactor),
        "description": description,
        "risk_level": skill.risk_level.value,
        "scope": skill.scope.value,
        "confidence": skill.confidence,
        "evidence_trace_ids": _list(skill.evidence_trace_ids, redactor),
    }
    metadata_json = json.dumps(metadata, indent=2, sort_keys=True)
    return _with_export_event(
        skill.id,
        "codex_directory",
        {"SKILL.md": skill_md, "metadata.json": metadata_json},
    )


def export_eval_spec_markdown(candidate: LessonCandidate, redactor: Redactor | None = None) -> str:
    """Render a candidate as a Markdown eval spec.

    The CLI ``export-lesson`` enforces that the candidate is approved with a
    matching action type before calling this; invoked directly it renders
    whatever candidate it is given.
    """
    lines = [
        f"# Eval: {_text(candidate.summary, redactor)}",
        "",
        "## Description",
        _text(candidate.observed_problem, redactor),
        "",
        "## Test condition",
        _text(candidate.proposed_lesson, redactor),
        "",
        "## Expected behavior",
        "The agent satisfies the lesson above without requiring human correction.",
    ]
    _section(
        lines,
        "Evidence",
        [f"trace: {_text(trace_id, redactor)}" for trace_id in candidate.evidence_trace_ids],
    )
    return _with_export_event(candidate.id, "eval", "\n".join(lines).strip() + "\n")


def export_guardrail_rule_markdown(
    candidate: LessonCandidate, redactor: Redactor | None = None
) -> str:
    """Render a candidate as a Markdown guardrail.

    The CLI ``export-lesson`` enforces that the candidate is approved with a
    matching action type before calling this; invoked directly it renders
    whatever candidate it is given.
    """
    lines = [
        f"# Guardrail: {_text(candidate.summary, redactor)}",
        "",
        "## Trigger condition",
        _text(candidate.observed_problem, redactor),
        "",
        "## Blocked behavior",
        "Completing the task without applying the corrective check below.",
        "",
        "## Rationale",
        _text(candidate.proposed_lesson, redactor),
    ]
    _section(
        lines,
        "Evidence",
        [f"trace: {_text(trace_id, redactor)}" for trace_id in candidate.evidence_trace_ids],
    )
    return _with_export_event(candidate.id, "guardrail", "\n".join(lines).strip() + "\n")


def export_workflow_recommendation_markdown(
    candidate: LessonCandidate, redactor: Redactor | None = None
) -> str:
    """Render a candidate as a Markdown workflow recommendation.

    The CLI ``export-lesson`` enforces that the candidate is approved with a
    matching action type before calling this; invoked directly it renders
    whatever candidate it is given.
    """
    lines = [
        f"# Workflow recommendation: {_text(candidate.summary, redactor)}",
        "",
        "## Problem observed",
        _text(candidate.observed_problem, redactor),
        "",
        "## Recommended workflow change",
        _text(candidate.proposed_lesson, redactor),
        "",
        "## Rationale",
        "Derived from reviewed trace evidence; prefer a deterministic fix where possible.",
    ]
    _section(
        lines,
        "Evidence",
        [f"trace: {_text(trace_id, redactor)}" for trace_id in candidate.evidence_trace_ids],
    )
    return _with_export_event(candidate.id, "workflow", "\n".join(lines).strip() + "\n")
