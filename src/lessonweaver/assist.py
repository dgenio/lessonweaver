"""Optional LLM-assist boundary objects.

The core lessonweaver pipeline remains deterministic. This module only defines
the governed interface for optional assist-mode features: callers must opt in,
evidence is redacted before provider calls by default, and returned suggestions
are audit-marked as non-authoritative drafts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from .models import TraceBundle
from .sanitization import TraceSanitizer


class AssistDisabledError(RuntimeError):
    """Raised when assist mode is called without explicit opt-in."""


@dataclass(slots=True)
class LLMAssistConfig:
    """Runtime opt-in and safety defaults for LLM-assisted draft generation."""

    enabled: bool = False
    redact_evidence: bool = True
    sanitizer: TraceSanitizer = field(default_factory=TraceSanitizer)


@dataclass(slots=True)
class LLMAssistRequest:
    """Provider input after lessonweaver has applied its safety defaults."""

    prompt_id: str
    prompt: str
    trace: TraceBundle | None = None


class LLMAssistProvider(Protocol):
    """Minimal provider contract for optional model-backed draft generation."""

    provider_name: str
    model: str
    model_version: str

    def generate(self, request: LLMAssistRequest) -> str: ...


@dataclass(slots=True)
class LLMAssistMetadata:
    """Audit metadata attached to every assist-mode suggestion."""

    provider: str
    model: str
    model_version: str
    prompt_id: str
    redacted: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "prompt_id": self.prompt_id,
            "redacted": self.redacted,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class LLMAssistSuggestion:
    """Non-authoritative draft text returned by an assist provider."""

    text: str
    metadata: LLMAssistMetadata
    llm_assisted: bool = True
    authoritative: bool = False
    allowed_lifecycle_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "llm_assisted": self.llm_assisted,
            "authoritative": self.authoritative,
            "allowed_lifecycle_actions": list(self.allowed_lifecycle_actions),
            "metadata": self.metadata.to_dict(),
        }

    def to_model_metadata(self) -> dict[str, object]:
        """Return metadata safe to attach to candidates, lessons, or skills.

        Lifecycle fields such as ``status`` and ``approved_by`` are intentionally
        absent so a suggestion cannot masquerade as a review/promotion decision.
        """
        return {
            "llm_assisted": self.llm_assisted,
            "authoritative": self.authoritative,
            "allowed_lifecycle_actions": list(self.allowed_lifecycle_actions),
            "assist": self.metadata.to_dict(),
        }


class LLMAssistClient:
    """Apply lessonweaver's assist-mode guardrails around a provider."""

    def __init__(
        self,
        provider: LLMAssistProvider,
        config: LLMAssistConfig | None = None,
    ) -> None:
        self.provider = provider
        self.config = config if config is not None else LLMAssistConfig()

    def suggest(
        self,
        *,
        prompt_id: str,
        prompt: str,
        trace: TraceBundle | None = None,
    ) -> LLMAssistSuggestion:
        if not self.config.enabled:
            raise AssistDisabledError("LLM assist mode is disabled; pass enabled=True to opt in")

        provider_trace = trace
        if trace is not None and self.config.redact_evidence:
            provider_trace = self.config.sanitizer.sanitize(trace)

        request = LLMAssistRequest(prompt_id=prompt_id, prompt=prompt, trace=provider_trace)
        text = self.provider.generate(request)
        metadata = LLMAssistMetadata(
            provider=self.provider.provider_name,
            model=self.provider.model,
            model_version=self.provider.model_version,
            prompt_id=prompt_id,
            redacted=self.config.redact_evidence,
        )
        return LLMAssistSuggestion(text=text, metadata=metadata)


class MockLLMAssistProvider:
    """Offline provider for tests and local examples."""

    def __init__(
        self,
        response_text: str,
        *,
        provider_name: str = "mock",
        model: str = "offline",
        model_version: str = "test",
    ) -> None:
        self.response_text = response_text
        self.provider_name = provider_name
        self.model = model
        self.model_version = model_version
        self.requests: list[LLMAssistRequest] = []

    def generate(self, request: LLMAssistRequest) -> str:
        self.requests.append(request)
        return self.response_text
