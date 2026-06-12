"""Explainable lesson loading diagnostics.

``SkillLoader`` answers *what* loads for a task; this module answers *why*. It
reuses the deterministic retrieval and compilation path and reports, per skill,
whether it loaded or was skipped (with a reason code), the context-budget usage,
and any overlap/contradiction among the loaded skills. Surfacing skip reasons
and overlaps is how a growing skill library is kept from quietly poisoning
context.

Provisional API: see docs/api-stability.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .analysis import AnalysisFinding, SkillAnalyzer
from .compile import CompiledContext, InclusionLevel, SkillCompiler
from .models import SkillCard
from .retrieval import RetrievalQuery, SkillRetriever, SkippedSkill


@dataclass(slots=True)
class LoadedSkill:
    """A skill that was retrieved and included in the compiled context."""

    skill_id: str
    score: float
    match_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "score": self.score,
            "match_reason": self.match_reason,
        }


@dataclass(slots=True)
class BudgetUsage:
    budget_chars: int
    used_chars: int

    @property
    def remaining_chars(self) -> int:
        return self.budget_chars - self.used_chars

    def to_dict(self) -> dict[str, int]:
        return {
            "budget_chars": self.budget_chars,
            "used_chars": self.used_chars,
            "remaining_chars": self.remaining_chars,
        }


@dataclass(slots=True)
class LoadDiagnostics:
    """The full explanation of a load decision for a task."""

    task: str
    loaded: list[LoadedSkill]
    skipped: list[SkippedSkill]
    budget: BudgetUsage
    overlaps: list[AnalysisFinding] = field(default_factory=list)
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "loaded": [item.to_dict() for item in self.loaded],
            "skipped": [item.to_dict() for item in self.skipped],
            "budget": self.budget.to_dict(),
            "overlaps": [finding.to_dict() for finding in self.overlaps],
            "snippet": self.snippet,
        }


def explain_load(
    skills: list[SkillCard],
    query: RetrievalQuery,
    *,
    budget_chars: int = 2000,
    inclusion_level: InclusionLevel = InclusionLevel.SUMMARY,
    retriever: SkillRetriever | None = None,
    compiler: SkillCompiler | None = None,
    analyzer: SkillAnalyzer | None = None,
    include_snippet: bool = False,
) -> LoadDiagnostics:
    """Explain which of ``skills`` would load for ``query`` and why.

    Retrieval decides candidacy and ranking; compilation decides what actually
    fits the character budget. Skills that retrieved but were dropped by the
    budget are reclassified from "loaded" to skipped with an ``omitted_budget``
    reason so the diagnostics match what an agent would really receive.
    """
    retriever = retriever or SkillRetriever()
    compiler = compiler or SkillCompiler()
    analyzer = analyzer or SkillAnalyzer()

    diag = retriever.diagnose(skills, query)
    context: CompiledContext = compiler.compile(
        diag.selected, budget_chars=budget_chars, default_inclusion=inclusion_level
    )

    by_id = {result.skill.id: result for result in diag.selected}
    included_ids = set(context.included_skills)

    loaded = [
        LoadedSkill(skill_id, by_id[skill_id].score, by_id[skill_id].match_reason)
        for skill_id in context.included_skills
        if skill_id in by_id
    ]

    skipped = list(diag.skipped)
    for skill_id in context.omitted_skills:
        if skill_id in included_ids:
            continue
        skipped.append(
            SkippedSkill(
                skill_id, "omitted_budget", f"retrieved but exceeded budget of {budget_chars} chars"
            )
        )

    loaded_cards = [by_id[item.skill_id].skill for item in loaded]
    overlaps = [
        finding
        for finding in analyzer.analyze(loaded_cards)
        if finding.finding_type in {"overlap", "contradiction"}
    ]

    return LoadDiagnostics(
        task=query.task,
        loaded=loaded,
        skipped=skipped,
        budget=BudgetUsage(budget_chars=budget_chars, used_chars=context.total_chars),
        overlaps=overlaps,
        snippet=context.snippet if include_snippet else "",
    )
