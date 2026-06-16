"""Tests for export-time redaction."""

from __future__ import annotations

import pytest
from redaction_cases import SAFE_CASES, SENSITIVE_CASES_PARAM

from lessonweaver.privacy import SimpleRedactor


@SENSITIVE_CASES_PARAM
def test_simple_redactor_uses_shared_sensitive_cases(
    case_name: str, raw: str, expected: str
) -> None:
    assert case_name
    assert SimpleRedactor().redact(raw) == expected


@pytest.mark.parametrize("text", SAFE_CASES)
def test_redactor_leaves_safe_text_unchanged(text: str) -> None:
    assert SimpleRedactor().redact(text) == text


def test_redactor_propagates_rule_failures() -> None:
    class ExplodingRule:
        def apply(self, text: str) -> str:
            raise RuntimeError("rule failed")

    with pytest.raises(RuntimeError, match="rule failed"):
        SimpleRedactor(rules=[ExplodingRule()]).redact("secret")  # type: ignore[list-item]
