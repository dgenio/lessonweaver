"""Tests for the retrieval validation suite models and runner."""

from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.validation import (
    ValidationExample,
    ValidationResult,
    ValidationSuite,
    run_validation_suite,
)

PR_SKILL = "pr-review"


def _skill(
    skill_id: str,
    name: str,
    applies_when: list[str],
    *,
    status: SkillStatus = SkillStatus.ACTIVE,
) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name=name,
        description=f"{name} description with enough detail.",
        applies_when=applies_when,
        does_not_apply_when=["Unrelated tasks"],
        instructions=["Follow the relevant checklist."],
        anti_patterns=[],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=status,
    )


def _pr_skill() -> SkillCard:
    return _skill(PR_SKILL, "PR Diff First", ["reviewing pull requests"])


def _suite(*examples: ValidationExample) -> ValidationSuite:
    return ValidationSuite(
        suite_id="suite-1",
        skill_id=PR_SKILL,
        examples=list(examples),
        created_at="2026-05-27T00:00:00+00:00",
    )


def test_validation_suite_round_trip() -> None:
    suite = _suite(
        ValidationExample("ex-pos", "Review this pull request", should_load=True),
        ValidationExample(
            "ex-neg", "Generate a SQL migration", should_load=False, notes="off-topic"
        ),
    )
    assert ValidationSuite.from_dict(suite.to_dict()).to_dict() == suite.to_dict()


def test_should_load_defaults_true_when_absent() -> None:
    example = ValidationExample.from_dict({"example_id": "ex", "task": "Review this PR"})
    assert example.should_load is True


def test_pass_rate_is_one_for_all_passing_suite() -> None:
    suite = _suite(
        ValidationExample("pos", "Review this pull request", should_load=True),
        ValidationExample("neg", "Generate a SQL migration", should_load=False),
    )
    result = run_validation_suite(suite, [_pr_skill()])
    assert result.passed == 2
    assert result.failed == 0
    assert result.pass_rate == 1.0


def test_pass_rate_is_zero_for_empty_suite() -> None:
    result = run_validation_suite(_suite(), [])
    assert result.total_examples == 0
    assert result.pass_rate == 0.0


def test_positive_example_detects_retrieval() -> None:
    result = run_validation_suite(
        _suite(ValidationExample("pos", "Review this pull request", should_load=True)),
        [_pr_skill()],
    )
    assert result.true_positives == 1
    assert result.results[0].actual is True
    assert result.results[0].classification == "true_positive"
    assert result.results[0].score > 0.0


def test_negative_example_a_naive_retriever_would_fail() -> None:
    # A retriever that always returned every skill would wrongly load PR_SKILL
    # for an unrelated task; this asserts the negative expectation holds.
    result = run_validation_suite(
        _suite(ValidationExample("neg", "Generate a SQL migration", should_load=False)),
        [_pr_skill()],
    )
    assert result.true_negatives == 1
    assert result.passed == 1
    assert result.results[0].actual is False
    assert result.results[0].score == 0.0
    assert result.results[0].classification == "true_negative"


def test_false_negative_when_expected_skill_missing_from_registry() -> None:
    # The suite expects PR_SKILL to load, but only an unrelated skill exists.
    skills = [_skill("policy", "Policy Check", ["answering policy questions"])]
    result = run_validation_suite(
        _suite(ValidationExample("pos", "Review this pull request", should_load=True)), skills
    )
    assert result.false_negatives == 1
    assert result.failed == 1
    assert result.recall == 0.0
    assert result.results[0].classification == "false_negative"


def test_precision_and_recall_with_mixed_outcomes() -> None:
    suite = _suite(
        ValidationExample("tp", "Review this pull request", should_load=True),  # match -> TP
        ValidationExample("fn", "Summarize meeting notes", should_load=True),  # no match -> FN
        ValidationExample("tn", "Generate a SQL migration", should_load=False),  # no match -> TN
    )
    result = run_validation_suite(suite, [_pr_skill()])
    assert (result.true_positives, result.false_negatives, result.true_negatives) == (1, 1, 1)
    assert result.false_positives == 0
    assert result.precision == 1.0  # 1 / (1 + 0)
    assert result.recall == 0.5  # 1 / (1 + 1)


def test_eval_result_to_dict_includes_metrics() -> None:
    result = run_validation_suite(
        _suite(ValidationExample("pos", "Review this pull request", should_load=True)),
        [_pr_skill()],
    )
    data = result.to_dict()
    assert data["pass_rate"] == 1.0
    assert data["precision"] == 1.0
    assert data["recall"] == 1.0
    assert data["results"][0]["classification"] == "true_positive"


def test_validation_result_to_dict_carries_classification() -> None:
    result = ValidationResult(
        example_id="ex",
        skill_id=PR_SKILL,
        expected=True,
        actual=False,
        passed=False,
        score=0.0,
        classification="false_negative",
    )
    data = result.to_dict()
    assert data["classification"] == "false_negative"
    assert data["expected"] is True
    assert data["actual"] is False
