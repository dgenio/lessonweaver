"""Drift protection for the bundled examples.

These tests load the example traces, skills, and validation suite through the
public API and assert their detection/retrieval behavior, so the worked examples
cannot silently drift from what their READMEs claim.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lessonweaver import (
    FileSystemRegistry,
    LessonDetector,
    SkillCard,
    SkillLoader,
    load_trace_bundle,
)
from lessonweaver.models import SkillStatus
from lessonweaver.validation import ValidationSuite, run_validation_suite

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
CODING_AGENT = EXAMPLES / "coding_agent_pr_review"
USEFULNESS = EXAMPLES / "usefulness_report"

# Expected number of candidates produced by LessonDetector for each trace. The
# zero-candidate traces are the "boring" cases that prove detection is
# conservative; the others lock the documented signal counts.
EXPECTED_TRACE_CANDIDATES = {
    "coding_agent_pr_review/traces/pr_review_correct.json": 0,
    "coding_agent_pr_review/traces/pr_review_missing_test.json": 1,
    "coding_agent_pr_review/traces/pr_review_security_miss.json": 2,
    "traces/external_chatbot_policy_failure.json": 1,
    "traces/github_pr_review_failure.json": 1,
    "traces/repo_check_finding.json": 1,
    "traces/specialist_agent_governance_miss.json": 1,
    "traces/tool_api_fallback.json": 1,
    "traces/voice_slot_correction.json": 1,
    "traces/workflow_validation_order.json": 0,
    "usefulness_report/traces/refund_match_1.json": 0,
    "usefulness_report/traces/refund_match_2.json": 0,
    "usefulness_report/traces/unrelated_translation.json": 0,
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_trace_file_has_an_expected_count() -> None:
    # Guards against a new trace being added without an expectation here.
    on_disk = {
        str(path.relative_to(EXAMPLES))
        for path in EXAMPLES.rglob("*.json")
        if "events" in _load_json(path) and "trace_id" in _load_json(path)
    }
    assert on_disk == set(EXPECTED_TRACE_CANDIDATES)


@pytest.mark.parametrize(("relative_path", "expected"), sorted(EXPECTED_TRACE_CANDIDATES.items()))
def test_trace_produces_expected_candidate_count(relative_path: str, expected: int) -> None:
    bundle = load_trace_bundle(EXAMPLES / relative_path)
    candidates = LessonDetector().detect(bundle)
    assert len(candidates) == expected


def test_coding_agent_skill_is_approved() -> None:
    skill = SkillCard.from_dict(_load_json(CODING_AGENT / "skill.json"))
    assert skill.status is SkillStatus.APPROVED


def test_coding_agent_validation_suite_passes_fully() -> None:
    suite = ValidationSuite.from_dict(_load_json(CODING_AGENT / "validation_suite.json"))
    skill = SkillCard.from_dict(_load_json(CODING_AGENT / "skill.json"))
    result = run_validation_suite(suite, [skill])
    assert result.total_examples == 4
    assert result.passed == 4
    assert result.precision == 1.0
    assert result.recall == 1.0


def test_coding_agent_validation_suite_passes_via_cli(capsys: pytest.CaptureFixture[str]) -> None:
    # Exercises the documented `validate-skill --skills-dir <example dir>` path
    # from the worked-example README. The directory also holds candidate.json and
    # validation_suite.json, so the CLI must skip non-skill JSON rather than crash.
    from lessonweaver.cli import main

    exit_code = main(
        [
            "validate-skill",
            str(CODING_AGENT / "validation_suite.json"),
            "--skills-dir",
            str(CODING_AGENT),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["passed"] == 4
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0


def test_coding_agent_candidate_matches_detector_output() -> None:
    # candidate.json must stay in sync with what the detector produces for its
    # source trace (ignoring only the wall-clock timestamps).
    stored = _load_json(CODING_AGENT / "candidate.json")
    bundle = load_trace_bundle(CODING_AGENT / "traces/pr_review_missing_test.json")
    detected = LessonDetector().detect(bundle)[0].to_dict()
    ignore = {"created_at", "updated_at"}
    assert {k: v for k, v in stored.items() if k not in ignore} == {
        k: v for k, v in detected.items() if k not in ignore
    }


def test_usefulness_report_retrieval_counts() -> None:
    loader = SkillLoader(registry=FileSystemRegistry(root=USEFULNESS / "registry"))
    matching = 0
    unrelated = 0
    for path in sorted((USEFULNESS / "traces").glob("*.json")):
        context = loader.load_for_task(task=load_trace_bundle(path).task)
        if "skill-refund-policy-version" in context.included_skills:
            matching += 1
        else:
            unrelated += 1
    assert (matching, unrelated) == (2, 1)


@pytest.mark.parametrize(
    ("registry_dir", "task", "skill_id"),
    [
        (
            "llamaindex_runtime_loader/example_registry",
            "Answer a question about our refund policy",
            "skill-refund-policy",
        ),
        (
            "openai_agents_runtime_loader/example_registry",
            "Review this pull request for missing tests",
            "skill-pr-review",
        ),
    ],
)
def test_framework_example_registry_loads_active_skill(
    registry_dir: str, task: str, skill_id: str
) -> None:
    loader = SkillLoader(registry=FileSystemRegistry(root=EXAMPLES / registry_dir))
    skills = loader.registry.list_skills()
    assert [skill.status for skill in skills] == [SkillStatus.ACTIVE]
    context = loader.load_for_task(task=task)
    assert skill_id in context.included_skills
