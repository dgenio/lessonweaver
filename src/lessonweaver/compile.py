"""Context-budgeted assembly of retrieved skills."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .export import export_runtime_prompt_snippet
from .models import SkillCard
from .retrieval import RetrievalResult


class InclusionLevel(str, Enum):
    NONE = "none"
    NAME_ONLY = "name_only"
    SUMMARY = "summary"
    FULL = "full"
    FULL_WITH_CHECKLIST = "full_with_checklist"


@dataclass(slots=True)
class CompiledContext:
    snippet: str
    included_skills: list[str]
    omitted_skills: list[str]
    total_chars: int


def _render_skill(skill: SkillCard, level: InclusionLevel) -> str:
    if level is InclusionLevel.NONE:
        return ""
    if level is InclusionLevel.NAME_ONLY:
        return f"[Skill] {skill.name}"
    if level is InclusionLevel.SUMMARY:
        return f"[Skill] {skill.name}: {skill.description}"
    full = export_runtime_prompt_snippet(skill)
    if level is InclusionLevel.FULL:
        return full
    checklist = "\n".join(f"- [ ] {instruction}" for instruction in skill.instructions)
    return f"{full}\n\nChecklist:\n{checklist}" if checklist else full


class SkillCompiler:
    """Compile retrieved skills into a prompt snippet within a character budget.

    Budgets are measured with ``len(...)`` over the rendered snippet. This is a
    character budget, not an estimated tokenizer budget.
    """

    def compile(
        self,
        results: list[RetrievalResult],
        budget_chars: int = 2000,
        default_inclusion: InclusionLevel = InclusionLevel.SUMMARY,
    ) -> CompiledContext:
        """Return a compiled context capped by ``budget_chars`` characters."""
        if not results or budget_chars <= 0:
            return CompiledContext("", [], [result.skill.id for result in results], 0)

        snippets: list[str] = []
        included: list[str] = []
        omitted: list[str] = []

        for result in sorted(results, key=lambda item: item.score, reverse=True):
            if default_inclusion is InclusionLevel.NONE:
                omitted.append(result.skill.id)
                continue

            rendered = _render_skill(result.skill, default_inclusion)
            candidate = _join(snippets, rendered)
            if len(candidate) <= budget_chars:
                snippets.append(rendered)
                included.append(result.skill.id)
                continue

            fallback = _render_skill(result.skill, InclusionLevel.NAME_ONLY)
            candidate = _join(snippets, fallback)
            if fallback and len(candidate) <= budget_chars:
                snippets.append(fallback)
                included.append(result.skill.id)
            else:
                omitted.append(result.skill.id)

        snippet = "\n\n".join(snippets)
        return CompiledContext(snippet, included, omitted, len(snippet))


def _join(existing: list[str], next_snippet: str) -> str:
    if not existing:
        return next_snippet
    return "\n\n".join([*existing, next_snippet])
