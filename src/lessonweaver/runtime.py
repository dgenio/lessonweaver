"""Runtime retrieval API for applicable reviewed lessons."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import RiskLevel, Scope, SkillCard, SkillStatus
from .registry import FileSystemRegistry
from .retrieval import RetrievalQuery, RetrievalResult, SkillRetriever

_TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")
_RUNTIME_STATUSES = {SkillStatus.APPROVED, SkillStatus.ACTIVE}
_STATUS_ORDER = {
    SkillStatus.APPROVED: 0,
    SkillStatus.ACTIVE: 1,
}
_RISK_ORDER = {
    RiskLevel.LOW.value: 1,
    RiskLevel.MEDIUM.value: 2,
    RiskLevel.HIGH.value: 3,
}


@dataclass(frozen=True, slots=True)
class RuntimeLessonQuery:
    """Context contract for retrieving reviewed lessons at runtime."""

    task: str
    runtime: str = ""
    tools: list[str] = field(default_factory=list)
    scope: str = ""
    risk_level: str = ""
    artifact_types: list[str] = field(default_factory=lambda: ["skill"])
    max_results: int = 10

    def to_dict(self) -> dict[str, object]:
        return {
            "task": self.task,
            "runtime": self.runtime,
            "tools": list(self.tools),
            "scope": self.scope,
            "risk_level": self.risk_level,
            "artifact_types": list(self.artifact_types),
            "max_results": self.max_results,
        }


class RuntimeLessonRetriever:
    """Retrieve applicable approved or active lessons for runtime callers."""

    def __init__(
        self,
        registry: FileSystemRegistry | None = None,
        retriever: SkillRetriever | None = None,
    ) -> None:
        self.registry = registry or FileSystemRegistry()
        self.retriever = retriever or SkillRetriever()

    def retrieve(self, query: RuntimeLessonQuery) -> list[RetrievalResult]:
        if "skill" not in query.artifact_types:
            return []
        skills = [
            skill
            for skill in self.registry.list_skills()
            if _eligible(skill, query) and not _negative_applies(skill, query)
        ]
        skills.sort(key=lambda skill: (_STATUS_ORDER[skill.status], skill.id))
        return self.retriever.retrieve(
            skills,
            RetrievalQuery(
                task=query.task,
                agent_type=query.runtime,
                tools=query.tools,
                scope=query.scope,
                risk_level=query.risk_level,
                max_results=query.max_results,
                include_non_active=True,
            ),
        )


def _eligible(skill: SkillCard, query: RuntimeLessonQuery) -> bool:
    if skill.status not in _RUNTIME_STATUSES:
        return False
    scope = _scope_value(query.scope)
    if scope and skill.scope not in {Scope.GLOBAL, Scope(scope)}:
        return False
    risk_level = _risk_value(query.risk_level)
    return not (risk_level and _RISK_ORDER[skill.risk_level.value] > _RISK_ORDER[risk_level])


def _negative_applies(skill: SkillCard, query: RuntimeLessonQuery) -> bool:
    query_tokens = _tokens(" ".join([query.task, query.runtime, *query.tools]))
    if not query_tokens:
        return False
    for negative in skill.does_not_apply_when:
        negative_tokens = _tokens(negative)
        if negative_tokens and len(negative_tokens & query_tokens) / len(negative_tokens) >= 0.75:
            return True
    return False


def _tokens(value: str) -> set[str]:
    tokens = {token.lower() for token in _TOKEN_RE.findall(value)}
    tokens.update(
        {token[:-3] for token in list(tokens) if token.endswith("ing") and len(token) > 4}
    )
    if "pr" in tokens:
        tokens.update({"pull", "request", "requests"})
    return tokens


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
