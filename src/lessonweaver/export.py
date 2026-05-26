"""Export helpers for approved lessons and skill cards."""

from __future__ import annotations

import json
from typing import Any, Protocol

from .models import OperationalLesson, SkillCard


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
    return "\n".join(lines).strip() + "\n"


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
    return "\n".join(lines).strip() + "\n"


def export_skillcard_json(skill: SkillCard, redactor: Redactor | None = None) -> str:
    return json.dumps(_redact_payload(skill.to_dict(), redactor), indent=2, sort_keys=True)


def export_copilot_instruction_fragment(skill: SkillCard, redactor: Redactor | None = None) -> str:
    return (
        f"- Skill: {_text(skill.name, redactor)}\n"
        f"- Use when: {'; '.join(_list(skill.applies_when, redactor))}\n"
        f"- Avoid when: {'; '.join(_list(skill.does_not_apply_when, redactor))}\n"
        f"- Do: {'; '.join(_list(skill.instructions, redactor))}"
    )


def export_claude_skill_fragment(skill: SkillCard, redactor: Redactor | None = None) -> str:
    instruction_block = "\n".join(f"- {line}" for line in _list(skill.instructions, redactor))
    return (
        f"## {_text(skill.name, redactor)}\n\n"
        f"Description: {_text(skill.description, redactor)}\n\n"
        "When to apply:\n- "
        + "\n- ".join(_list(skill.applies_when, redactor))
        + "\n\nInstructions:\n"
        + instruction_block
    )


def export_runtime_prompt_snippet(skill: SkillCard, redactor: Redactor | None = None) -> str:
    return (
        "Operational lesson:\n"
        f"{_text(skill.description, redactor)}\n"
        f"Applies when: {'; '.join(_list(skill.applies_when, redactor))}\n"
        f"Do not apply when: {'; '.join(_list(skill.does_not_apply_when, redactor))}\n"
        f"Required behaviors: {'; '.join(_list(skill.instructions, redactor))}"
    )
