"""Privacy helpers for export safety nets."""

from __future__ import annotations

from .sanitization import SanitizationRule, default_redaction_rules


class SimpleRedactor:
    """Deterministic redactor for obvious sensitive string patterns."""

    def __init__(self, rules: list[SanitizationRule] | None = None) -> None:
        self.rules = rules if rules is not None else default_redaction_rules()

    def redact(self, text: str) -> str:
        for rule in self.rules:
            text = rule.apply(text)
        return text
