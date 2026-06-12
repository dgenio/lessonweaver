"""Privacy helpers for export safety nets."""

from __future__ import annotations

import re
from typing import ClassVar


class SimpleRedactor:
    """Deterministic redactor for obvious sensitive string patterns."""

    _patterns: ClassVar[tuple[re.Pattern[str], ...]] = (
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
        re.compile(r"(?:api[_-]?key|apikey)\s*[:=]\s*\S+", re.IGNORECASE),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN .{1,30} PRIVATE KEY-----"),
    )

    def redact(self, text: str) -> str:
        try:
            redacted = text
            for pattern in self._patterns:
                redacted = pattern.sub("[REDACTED]", redacted)
            return redacted
        except Exception:
            return text
