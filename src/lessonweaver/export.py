"""Export helpers for approved lessons and skill cards."""

from __future__ import annotations

import json

from .models import SkillCard


def export_skillcard_markdown(skill: SkillCard) -> str:
    lines = [
        f"# {skill.name}",
        "",
        "## Description",
        skill.description,
        "",
        "## Use when",
        *[f"- {item}" for item in skill.applies_when],
        "",
        "## Do not use when",
        *[f"- {item}" for item in skill.does_not_apply_when],
        "",
        "## Instructions",
        *[f"- {item}" for item in skill.instructions],
        "",
        "## Anti-patterns",
        *[f"- {item}" for item in skill.anti_patterns],
        "",
        "## Evidence",
        *[f"- trace: {trace_id}" for trace_id in skill.evidence_trace_ids],
        "",
        "## Governance",
        f"- Confidence: {skill.confidence:.2f}",
        f"- Risk: {skill.risk_level.value}",
        f"- Scope: {skill.scope.value}",
        f"- Version: {skill.version}",
        f"- Status: {skill.status.value}",
    ]
    return "\n".join(lines).strip() + "\n"


def export_skillcard_json(skill: SkillCard) -> str:
    return json.dumps(skill.to_dict(), indent=2, sort_keys=True)


def export_copilot_instruction_fragment(skill: SkillCard) -> str:
    return (
        f"- Skill: {skill.name}\n"
        f"- Use when: {'; '.join(skill.applies_when)}\n"
        f"- Avoid when: {'; '.join(skill.does_not_apply_when)}\n"
        f"- Do: {'; '.join(skill.instructions)}"
    )


def export_claude_skill_fragment(skill: SkillCard) -> str:
    instruction_block = "\n".join(f"- {line}" for line in skill.instructions)
    return (
        f"## {skill.name}\n\n"
        f"Description: {skill.description}\n\n"
        f"When to apply:\n- "
        + "\n- ".join(skill.applies_when)
        + "\n\nInstructions:\n"
        + instruction_block
    )


def export_runtime_prompt_snippet(skill: SkillCard) -> str:
    return (
        "Operational lesson:\n"
        f"{skill.description}\n"
        f"Applies when: {'; '.join(skill.applies_when)}\n"
        f"Do not apply when: {'; '.join(skill.does_not_apply_when)}\n"
        f"Required behaviors: {'; '.join(skill.instructions)}"
    )
