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


@dataclass(slots=True)
class SkippedSkill:
    """A skill that was considered but not selected, with a machine-readable reason.

    ``reason`` is a stable reason code (see :meth:`SkillRetriever.diagnose`);
    ``detail`` is a human-readable elaboration safe to print in diagnostics.
    """

    skill_id: str
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"skill_id": self.skill_id, "reason": self.reason, "detail": self.detail}


@dataclass(slots=True)
class RetrievalDiagnostics:
    """The full retrieval decision: what was selected and what was skipped (and why)."""

    selected: list[RetrievalResult]
    skipped: list[SkippedSkill]


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
    try:
        return Scope(scope).value
    except ValueError:
        return ""


def _risk_value(risk_level: str) -> str:
    if not risk_level:
        return ""
    try:
        return RiskLevel(risk_level).value
    except ValueError:
        return ""


class SkillRetriever:
    """Rank active skills for a task with a deterministic lexical baseline."""

    def retrieve(self, skills: list[SkillCard], query: RetrievalQuery) -> list[RetrievalResult]:
        return self.diagnose(skills, query).selected

    def diagnose(self, skills: list[SkillCard], query: RetrievalQuery) -> RetrievalDiagnostics:
        """Score skills like :meth:`retrieve`, but also report why skills were dropped.

        Reason codes on skipped skills: ``empty_query`` (the query had no usable
        tokens), ``status_not_active`` (non-active skill while active-only),
        ``risk_above_threshold``, ``no_skill_tokens``, ``no_match`` (no token or
        scope overlap), and ``omitted_max_results`` (matched but beyond
        ``max_results``). Compilation-budget drops are layered on by the loader,
        not here, since this method does not know the character budget.
        """
        query_tokens = _tokens(" ".join([query.task, query.agent_type, *query.tools]))
        if not query_tokens:
            return RetrievalDiagnostics(
                selected=[],
                skipped=[SkippedSkill(skill.id, "empty_query") for skill in skills],
            )

        scope = _scope_value(query.scope)
        risk_level = _risk_value(query.risk_level)
        scored: list[RetrievalResult] = []
        skipped: list[SkippedSkill] = []

        for skill in skills:
            if not query.include_non_active and skill.status is not SkillStatus.ACTIVE:
                skipped.append(
                    SkippedSkill(skill.id, "status_not_active", f"status is {skill.status.value}")
                )
                continue
            if not _risk_allowed(skill, risk_level):
                skipped.append(
                    SkippedSkill(
                        skill.id,
                        "risk_above_threshold",
                        f"risk {skill.risk_level.value} exceeds requested ceiling {risk_level}",
                    )
                )
                continue

            skill_tokens = _skill_tokens(skill)
            if not skill_tokens:
                skipped.append(
                    SkippedSkill(skill.id, "no_skill_tokens", "skill has no indexable text")
                )
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
                skipped.append(SkippedSkill(skill.id, "no_match", "no token or scope overlap"))
                continue

            scored.append(
                RetrievalResult(
                    skill=skill,
                    score=min(score, 1.0),
                    match_reason="; ".join(reason_parts) if reason_parts else "scope matched",
                )
            )

        scored.sort(key=lambda result: result.score, reverse=True)
        limit = max(query.max_results, 0)
        selected = scored[:limit]
        for result in scored[limit:]:
            skipped.append(
                SkippedSkill(
                    result.skill.id, "omitted_max_results", f"ranked beyond max_results={limit}"
                )
            )
        return RetrievalDiagnostics(selected=selected, skipped=skipped)
