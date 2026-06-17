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
    email / bearer-token / private-key / common secret patterns. :meth:`sanitize`
    returns a new bundle and never mutates its input.
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
                name="aws_access_key_id",
                pattern=r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
                replacement="[REDACTED by aws_access_key_id]",
            ),
            SanitizationRule(
                name="aws_secret_access_key",
                pattern=r"(?i)\b(aws_secret_access_key\s*[:=]\s*)['\"]?[A-Za-z0-9/+=]{40}['\"]?",
                replacement=r"\1[REDACTED by aws_secret_access_key]",
            ),
            SanitizationRule(
                name="generic_secret",
                pattern=(
                    r"(?i)\b(api[_-]?key|token|password|secret)\b"
                    r"(\s*[:=]\s*)['\"]?[A-Za-z0-9][A-Za-z0-9._/\-+=]{5,}['\"]?"
                ),
                replacement=r"\1\2[REDACTED by generic_secret]",
            ),
            SanitizationRule(
                name="jwt",
                pattern=r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
                replacement="[REDACTED by jwt]",
            ),
            SanitizationRule(
                name="private_key",
                # Redact the whole PEM block (header + base64 body + footer) when
                # both markers are present; fall back to a lone header otherwise.
                # ``(?s)`` lets ``.`` span the newlines of a multi-line key body.
                pattern=(
                    r"(?s)-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----"
                    r".*?-----END [A-Z0-9 ]{0,40}PRIVATE KEY-----"
                    r"|-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----"
                ),
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
