"""Pre-mining trace sanitization (issue #46).

Redaction in :mod:`lessonweaver.privacy` runs at *export* time, which is too
late: sensitive trace content can already have shaped candidates, review
questions, and registry files by then. :class:`TraceSanitizer` scrubs
``TraceEvent.content`` *before* a bundle reaches :class:`LessonDetector`.

This is a best-effort layer, not a privacy guarantee — pattern-based redaction
cannot catch every form of sensitive data. Treat traces as sensitive at the
source as well.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from .models import TraceBundle, TraceEvent


@dataclass(slots=True)
class SanitizationRule:
    """A named regex rule that replaces matches in trace content."""

    name: str
    pattern: str
    replacement: str = "[REDACTED]"
    _compiled: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._compiled = re.compile(self.pattern)

    def apply(self, text: str) -> str:
        return self._compiled.sub(self.replacement, text)


class TraceSanitizer:
    """Scrub sensitive content from a :class:`TraceBundle` before mining.

    Construct with custom rules, or use :meth:`default_rules` for the built-in
    email / bearer-token / private-key patterns. :meth:`sanitize` returns a new
    bundle and never mutates its input.
    """

    def __init__(self, rules: list[SanitizationRule] | None = None) -> None:
        self.rules = rules if rules is not None else self.default_rules()

    @staticmethod
    def default_rules() -> list[SanitizationRule]:
        return [
            SanitizationRule(
                name="email",
                pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                replacement="[REDACTED by email]",
            ),
            SanitizationRule(
                name="bearer_token",
                pattern=r"Bearer\s+[A-Za-z0-9._\-]{20,}",
                replacement="[REDACTED by bearer_token]",
            ),
            SanitizationRule(
                name="private_key",
                pattern=r"-----BEGIN .{1,30} PRIVATE KEY-----",
                replacement="[REDACTED by private_key]",
            ),
        ]

    def _scrub(self, text: str) -> str:
        for rule in self.rules:
            text = rule.apply(text)
        return text

    def sanitize(self, bundle: TraceBundle) -> TraceBundle:
        """Return a new bundle with every ``TraceEvent.content`` scrubbed."""
        sanitized_events: list[TraceEvent] = [
            replace(event, content=self._scrub(event.content) if event.content else event.content)
            for event in bundle.events
        ]
        return replace(bundle, events=sanitized_events)
