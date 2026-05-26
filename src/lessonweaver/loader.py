"""Public API for loading relevant skills into agent context."""

from __future__ import annotations

from .compile import CompiledContext, InclusionLevel, SkillCompiler
from .registry import FileSystemRegistry
from .retrieval import RetrievalQuery, SkillRetriever


class SkillLoader:
    """Thin facade combining registry, retrieval, and compilation."""

    def __init__(
        self,
        registry: FileSystemRegistry | None = None,
        retriever: SkillRetriever | None = None,
        compiler: SkillCompiler | None = None,
    ) -> None:
        self.registry = registry or FileSystemRegistry()
        self.retriever = retriever or SkillRetriever()
        self.compiler = compiler or SkillCompiler()

    def load_for_task(
        self,
        task: str,
        agent_type: str = "",
        tools: list[str] | None = None,
        scope: str = "",
        risk_level: str = "",
        budget_chars: int = 2000,
        max_skills: int = 10,
        inclusion_level: str = "summary",
    ) -> CompiledContext:
        query = RetrievalQuery(
            task=task,
            agent_type=agent_type,
            tools=tools or [],
            scope=scope,
            risk_level=risk_level,
            max_results=max_skills,
        )
        results = self.retriever.retrieve(self.registry.list_skills(), query)
        return self.compiler.compile(
            results,
            budget_chars=budget_chars,
            default_inclusion=InclusionLevel(inclusion_level),
        )
