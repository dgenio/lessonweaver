"""Public API for loading relevant skills into agent context."""

from __future__ import annotations

from .compile import CompiledContext, InclusionLevel, SkillCompiler
from .events import LifecycleEvent, LifecycleEventType, emitter
from .models import LoadingPolicy
from .registry import FileSystemRegistry
from .retrieval import RetrievalQuery, SkillRetriever


class SkillLoader:
    """Thin facade combining registry, retrieval, and compilation."""

    def __init__(
        self,
        registry: FileSystemRegistry | None = None,
        retriever: SkillRetriever | None = None,
        compiler: SkillCompiler | None = None,
        policy: LoadingPolicy | None = None,
    ) -> None:
        self.registry = registry or FileSystemRegistry()
        self.retriever = retriever or SkillRetriever()
        self.compiler = compiler or SkillCompiler()
        self.policy = policy

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
        # When a policy is present it owns load governance: its limits act as
        # ceilings over the per-call arguments, and it has already decided which
        # lifecycle states are eligible. Retrieval must therefore not re-apply
        # its ACTIVE-only default on top, or APPROVED skills the policy admitted
        # (and any policy with require_approved_status=False) would be silently
        # dropped again.
        effective_max_skills = max_skills
        effective_budget = budget_chars
        if self.policy is not None:
            effective_max_skills = min(max_skills, self.policy.max_skills)
            effective_budget = min(budget_chars, self.policy.max_token_budget)

        query = RetrievalQuery(
            task=task,
            agent_type=agent_type,
            tools=tools or [],
            scope=scope,
            risk_level=risk_level,
            max_results=effective_max_skills,
            include_non_active=self.policy is not None,
        )
        skills = self.registry.list_skills()
        if self.policy is not None:
            skills = self.policy.filter(skills)
        results = self.retriever.retrieve(skills, query)
        context = self.compiler.compile(
            results,
            budget_chars=effective_budget,
            default_inclusion=InclusionLevel(inclusion_level),
        )
        for skill_id in context.omitted_skills:
            emitter.emit(
                LifecycleEvent(
                    LifecycleEventType.SKILL_OMITTED_BUDGET,
                    skill_id,
                    {
                        "budget_chars": effective_budget,
                        "total_chars": context.total_chars,
                    },
                )
            )
        return context
