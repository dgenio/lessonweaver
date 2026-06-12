"""Deterministic analysis for duplicate, overlapping, and conflicting skills.

Provisional API: see docs/api-stability.md.
"""

from __future__ import annotations

import itertools
import re
import string
from dataclasses import dataclass

from .models import SkillCard


@dataclass(slots=True)
class AnalysisFinding:
    finding_type: str
    skill_id_a: str
    skill_id_b: str
    reason: str
    confidence: float

    def to_dict(self) -> dict[str, str | float]:
        return {
            "finding_type": self.finding_type,
            "skill_id_a": self.skill_id_a,
            "skill_id_b": self.skill_id_b,
            "reason": self.reason,
            "confidence": self.confidence,
        }


_TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "before",
    "for",
    "if",
    "in",
    "is",
    "it",
    "must",
    "not",
    "or",
    "the",
    "to",
    "when",
}
_POSITIVE_MODALS = {"must", "always", "required"}
_NEGATIVE_MARKERS = {"never", "avoid"}


def _normalize_name(value: str) -> str:
    table = str.maketrans("", "", string.punctuation)
    return " ".join(value.lower().translate(table).split())


def _tokens(value: str) -> set[str]:
    return set(_token_list(value))


def _token_list(value: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(value)]


def _applies_tokens(skill: SkillCard) -> set[str]:
    return (
        set().union(*[_tokens(item) for item in skill.applies_when])
        if skill.applies_when
        else set()
    )


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _instruction_tokens(skill: SkillCard) -> set[str]:
    tokens = (
        set().union(*[_tokens(item) for item in skill.instructions])
        if skill.instructions
        else set()
    )
    return {token for token in tokens if token not in _STOPWORDS}


def _has_positive_modal(skill: SkillCard) -> bool:
    tokens = _token_list(" ".join(skill.instructions))
    for index, token in enumerate(tokens):
        if token == "must" and _next_token(tokens, index) != "not":
            return True
        if token == "required" and _previous_token(tokens, index) != "not":
            return True
        if token == "always":
            return True
    return False


def _has_negative_modal(skill: SkillCard) -> bool:
    text = " ".join(skill.instructions).lower()
    tokens = _tokens(text)
    return bool(tokens & _NEGATIVE_MARKERS) or "must not" in text or "do not" in text


def _previous_token(tokens: list[str], index: int) -> str:
    return tokens[index - 1] if index > 0 else ""


def _next_token(tokens: list[str], index: int) -> str:
    return tokens[index + 1] if index + 1 < len(tokens) else ""


def _contradicts(left: SkillCard, right: SkillCard) -> bool:
    left_subjects = _instruction_tokens(left)
    right_subjects = _instruction_tokens(right)
    if not left_subjects & right_subjects:
        return False
    return (_has_positive_modal(left) and _has_negative_modal(right)) or (
        _has_negative_modal(left) and _has_positive_modal(right)
    )


class SkillAnalyzer:
    """Find deterministic duplicate, overlap, and contradiction candidates."""

    def analyze(self, skills: list[SkillCard]) -> list[AnalysisFinding]:
        findings: list[AnalysisFinding] = []
        for left, right in itertools.combinations(skills, 2):
            if _normalize_name(left.name) == _normalize_name(right.name):
                findings.append(
                    AnalysisFinding(
                        "duplicate",
                        left.id,
                        right.id,
                        "Skills have identical normalized names.",
                        1.0,
                    )
                )

            left_applies = _applies_tokens(left)
            right_applies = _applies_tokens(right)
            overlap = _jaccard(left_applies, right_applies)
            if overlap >= 0.5:
                findings.append(
                    AnalysisFinding(
                        "overlap",
                        left.id,
                        right.id,
                        "Skills share at least half of their applies_when tokens.",
                        overlap,
                    )
                )

            if overlap >= 0.3 and _contradicts(left, right):
                findings.append(
                    AnalysisFinding(
                        "contradiction",
                        left.id,
                        right.id,
                        "Skills contain conflicting modal guidance over overlapping applicability.",
                        max(0.7, overlap),
                    )
                )

        return findings
