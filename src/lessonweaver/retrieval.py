"""Lexical runtime retrieval for skill cards."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import RiskLevel, Scope, SkillCard, SkillStatus


@dataclass(slots=True)
class RetrievalQuery:
    task: str
    agent_type: str = ""
    tools: list[str] = field(default_factory=list)
    scope: str = ""
    risk_level: str = ""
    max_results: int = 10
    include_non_active: bool = False


@dataclass(slots=True)
class RetrievalResult:
    skill: SkillCard
    score: float
    match_reason: str


_TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")
_RISK_ORDER = {
    RiskLevel.LOW.value: 1,
    RiskLevel.MEDIUM.value: 2,
    RiskLevel.HIGH.value: 3,
}


def _tokens(value: str) -> set[str]:
    tokens = {token.lower() for token in _TOKEN_RE.findall(value)}
    if "pr" in tokens:
        tokens.update({"pull", "request", "requests"})
    return tokens


def _skill_tokens(skill: SkillCard) -> set[str]:
    chunks = [skill.name, skill.description, *skill.applies_when]
    return set().union(*[_tokens(chunk) for chunk in chunks])


def _risk_allowed(skill: SkillCard, risk_level: str) -> bool:
    if not risk_level:
        return True
    threshold = _RISK_ORDER.get(risk_level)
    if threshold is None:
        return True
    return _RISK_ORDER[skill.risk_level.value] <= threshold


def _scope_value(scope: str) -> str:
    if not scope:
        return ""
    return Scope(scope).value


class SkillRetriever:
    """Rank active skills for a task with a deterministic lexical baseline."""

    def retrieve(self, skills: list[SkillCard], query: RetrievalQuery) -> list[RetrievalResult]:
        query_tokens = _tokens(" ".join([query.task, query.agent_type, *query.tools]))
        if not query_tokens:
            return []

        scope = _scope_value(query.scope) if query.scope else ""
        risk_level = RiskLevel(query.risk_level).value if query.risk_level else ""
        results: list[RetrievalResult] = []

        for skill in skills:
            if not query.include_non_active and skill.status is not SkillStatus.ACTIVE:
                continue
            if not _risk_allowed(skill, risk_level):
                continue

            skill_tokens = _skill_tokens(skill)
            if not skill_tokens:
                continue
            shared = query_tokens & skill_tokens
            score = len(shared) / len(query_tokens | skill_tokens)
            reason_parts: list[str] = []
            if shared:
                reason_parts.append("matched tokens: " + ", ".join(sorted(shared)))
            if scope and skill.scope.value == scope:
                score += 0.1
                reason_parts.append(f"scope matched: {scope}")
            if score <= 0.0:
                continue

            results.append(
                RetrievalResult(
                    skill=skill,
                    score=min(score, 1.0),
                    match_reason="; ".join(reason_parts) if reason_parts else "scope matched",
                )
            )

        results.sort(key=lambda result: result.score, reverse=True)
        return results[: max(query.max_results, 0)]
