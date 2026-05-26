from lessonweaver.lint import LintSeverity, SkillLinter
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus


def _skill(**overrides) -> SkillCard:
    data = {
        "id": "skill-1",
        "name": "PR Diff First",
        "description": "Inspect changed files before reviewing pull requests.",
        "applies_when": ["Reviewing pull requests"],
        "does_not_apply_when": ["No code changes"],
        "instructions": ["Inspect changed files when reviewing pull requests."],
        "anti_patterns": ["Approving based on title only"],
        "evidence_trace_ids": ["trace-1"],
        "confidence": 0.8,
        "risk_level": RiskLevel.MEDIUM,
        "scope": Scope.PROJECT,
        "version": "0.2.0",
    }
    data.update(overrides)
    return SkillCard(**data)


def _rule_ids(skill: SkillCard) -> set[str]:
    return {finding.rule_id for finding in SkillLinter().lint(skill)}


def test_well_formed_skill_passes() -> None:
    assert SkillLinter().lint(_skill()) == []


def test_lw001_empty_applies_when() -> None:
    assert "LW001" in _rule_ids(_skill(applies_when=[]))


def test_lw002_empty_does_not_apply_when() -> None:
    assert "LW002" in _rule_ids(_skill(does_not_apply_when=[]))


def test_lw003_empty_instructions() -> None:
    assert "LW003" in _rule_ids(_skill(instructions=[]))


def test_lw004_empty_evidence() -> None:
    finding = next(
        f for f in SkillLinter().lint(_skill(evidence_trace_ids=[])) if f.rule_id == "LW004"
    )
    assert finding.severity is LintSeverity.WARNING


def test_lw005_low_confidence() -> None:
    assert "LW005" in _rule_ids(_skill(confidence=0.3))


def test_lw006_high_risk_active_without_approval() -> None:
    assert "LW006" in _rule_ids(_skill(risk_level=RiskLevel.HIGH, status=SkillStatus.ACTIVE))


def test_lw007_unqualified_absolute_language() -> None:
    assert "LW007" in _rule_ids(_skill(instructions=["Always inspect every file."]))


def test_lw008_short_description() -> None:
    assert "LW008" in _rule_ids(_skill(description="Too short"))


def test_lw009_initial_version() -> None:
    assert "LW009" in _rule_ids(_skill(version="0.1.0"))
