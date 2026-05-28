"""Models and execution for skill retrieval validation suites.

A skill is a hypothesis until it has been validated. These models describe the
positive and negative retrieval expectations for a skill, and
``run_validation_suite`` checks them deterministically against
``SkillRetriever``. This is a retrieval *correctness* check (does the right
skill load for the right task?), not a quality evaluation of model output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .models import SkillCard
from .retrieval import RetrievalQuery, SkillRetriever

TRUE_POSITIVE = "true_positive"
TRUE_NEGATIVE = "true_negative"
FALSE_POSITIVE = "false_positive"
FALSE_NEGATIVE = "false_negative"


def _classify(should_load: bool, actual: bool) -> str:
    if should_load:
        return TRUE_POSITIVE if actual else FALSE_NEGATIVE
    return FALSE_POSITIVE if actual else TRUE_NEGATIVE


@dataclass(slots=True)
class ValidationExample:
    """A single retrieval expectation for the skill under validation.

    ``should_load`` distinguishes positive examples (the skill must be retrieved
    for ``task``) from negative examples (it must not be). Negative examples are
    what make retrieval precision measurable, not just recall.
    """

    example_id: str
    task: str
    should_load: bool = True
    expected_skill_id: str = ""  # defaults to the suite's skill_id when empty
    agent_type: str = ""
    scope: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationExample:
        return cls(
            example_id=str(data["example_id"]),
            task=str(data["task"]),
            should_load=bool(data.get("should_load", True)),
            expected_skill_id=str(data.get("expected_skill_id", "")),
            agent_type=str(data.get("agent_type", "")),
            scope=str(data.get("scope", "")),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationSuite:
    """A set of retrieval expectations for one skill."""

    suite_id: str
    skill_id: str
    examples: list[ValidationExample] = field(default_factory=list)
    created_at: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationSuite:
        return cls(
            suite_id=str(data["suite_id"]),
            skill_id=str(data["skill_id"]),
            examples=[ValidationExample.from_dict(item) for item in data.get("examples", [])],
            created_at=str(data.get("created_at", "")),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "skill_id": self.skill_id,
            "examples": [example.to_dict() for example in self.examples],
            "created_at": self.created_at,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ValidationResult:
    """Outcome of validating one example against the retriever."""

    example_id: str
    skill_id: str
    expected: bool  # should_load
    actual: bool  # whether the skill was retrieved
    passed: bool  # actual == expected
    score: float  # retrieval score, 0.0 if not retrieved
    classification: str  # one of the TRUE_/FALSE_ constants in this module
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SkillEvalResult:
    """Aggregate validation outcome for a skill, with precision/recall."""

    suite_id: str
    skill_id: str
    total_examples: int
    passed: int
    failed: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_examples if self.total_examples > 0 else 0.0

    @property
    def precision(self) -> float:
        predicted_positive = self.true_positives + self.false_positives
        return self.true_positives / predicted_positive if predicted_positive > 0 else 0.0

    @property
    def recall(self) -> float:
        actual_positive = self.true_positives + self.false_negatives
        return self.true_positives / actual_positive if actual_positive > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "skill_id": self.skill_id,
            "total_examples": self.total_examples,
            "passed": self.passed,
            "failed": self.failed,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "pass_rate": self.pass_rate,
            "precision": self.precision,
            "recall": self.recall,
            "results": [result.to_dict() for result in self.results],
        }


def run_validation_suite(
    suite: ValidationSuite,
    skills: list[SkillCard],
    retriever: SkillRetriever | None = None,
) -> SkillEvalResult:
    """Check that ``suite.skill_id`` retrieves (or not) for each example.

    Delegates entirely to ``SkillRetriever``; no model calls. An example passes
    when the skill's presence in the retrieval results matches
    ``example.should_load``.
    """

    retriever = retriever or SkillRetriever()
    results: list[ValidationResult] = []
    tallies: dict[str, int] = {
        TRUE_POSITIVE: 0,
        TRUE_NEGATIVE: 0,
        FALSE_POSITIVE: 0,
        FALSE_NEGATIVE: 0,
    }

    for example in suite.examples:
        target_skill_id = example.expected_skill_id or suite.skill_id
        query = RetrievalQuery(
            task=example.task,
            agent_type=example.agent_type,
            scope=example.scope,
            max_results=max(len(skills), 1),
            include_non_active=True,
        )
        retrieved = retriever.retrieve(skills, query)
        match = next((result for result in retrieved if result.skill.id == target_skill_id), None)
        actual = match is not None
        score = match.score if match is not None else 0.0
        classification = _classify(example.should_load, actual)
        tallies[classification] += 1
        results.append(
            ValidationResult(
                example_id=example.example_id,
                skill_id=target_skill_id,
                expected=example.should_load,
                actual=actual,
                passed=actual == example.should_load,
                score=score,
                classification=classification,
                notes=example.notes,
            )
        )

    passed_count = sum(1 for result in results if result.passed)
    return SkillEvalResult(
        suite_id=suite.suite_id,
        skill_id=suite.skill_id,
        total_examples=len(results),
        passed=passed_count,
        failed=len(results) - passed_count,
        true_positives=tallies[TRUE_POSITIVE],
        true_negatives=tallies[TRUE_NEGATIVE],
        false_positives=tallies[FALSE_POSITIVE],
        false_negatives=tallies[FALSE_NEGATIVE],
        results=results,
    )
