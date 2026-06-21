"""Deterministic quality checks for skill cards."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ._text import token_list
from .models import RiskLevel, SkillCard, SkillStatus


class LintSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(slots=True)
class LintFinding:
    rule_id: str
    severity: LintSeverity
    message: str
    field: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
        }


_ABSOLUTE_WORDS = {"always", "never"}
_QUALIFIERS = {"when", "unless", "except", "if"}


def _has_unqualified_absolute(text: str) -> bool:
    tokens = token_list(text)
    for index, token in enumerate(tokens):
        if token not in _ABSOLUTE_WORDS:
            continue
        window = tokens[max(0, index - 5) : index + 6]
        if not (_QUALIFIERS & set(window)) and not {"only", "if"}.issubset(window):
            return True
    return False


class SkillLinter:
    """Run deterministic structural and governance checks on a skill."""

    def lint(self, skill: SkillCard) -> list[LintFinding]:
        findings: list[LintFinding] = []

        if not skill.applies_when:
            findings.append(
                LintFinding(
                    "LW001",
                    LintSeverity.ERROR,
                    "Skill must define when it applies.",
                    "applies_when",
                )
            )
        if not skill.does_not_apply_when:
            findings.append(
                LintFinding(
                    "LW002",
                    LintSeverity.ERROR,
                    "Skill must define when it does not apply.",
                    "does_not_apply_when",
                )
            )
        if not skill.instructions:
            findings.append(
                LintFinding(
                    "LW003",
                    LintSeverity.ERROR,
                    "Skill must include at least one instruction.",
                    "instructions",
                )
            )
        if not skill.evidence_trace_ids:
            findings.append(
                LintFinding(
                    "LW004",
                    LintSeverity.WARNING,
                    "Skill should include at least one evidence trace ID.",
                    "evidence_trace_ids",
                )
            )
        if skill.confidence < 0.4:
            findings.append(
                LintFinding(
                    "LW005", LintSeverity.WARNING, "Skill confidence is below 0.40.", "confidence"
                )
            )
        if (
            skill.risk_level is RiskLevel.HIGH
            and skill.status is SkillStatus.ACTIVE
            and not (skill.approved_by or skill.metadata.get("approved_by"))
        ):
            findings.append(
                LintFinding(
                    "LW006",
                    LintSeverity.ERROR,
                    "High-risk active skills must record an approver.",
                    "approved_by",
                )
            )
        for instruction in skill.instructions:
            if _has_unqualified_absolute(instruction):
                findings.append(
                    LintFinding(
                        "LW007",
                        LintSeverity.WARNING,
                        "Avoid unqualified always/never language in instructions.",
                        "instructions",
                    )
                )
                break
        if len(skill.description.strip()) < 20:
            findings.append(
                LintFinding(
                    "LW008",
                    LintSeverity.WARNING,
                    "Skill description should be at least 20 characters.",
                    "description",
                )
            )
        if skill.version == "0.1.0":
            findings.append(
                LintFinding(
                    "LW009",
                    LintSeverity.INFO,
                    "Skill version is still 0.1.0; confirm whether it should be bumped.",
                    "version",
                )
            )

        return findings
