from lessonweaver.analysis import SkillAnalyzer
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus


def _skill(skill_id: str, name: str, applies_when: list[str], instructions: list[str]) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name=name,
        description=f"{name} description with enough detail.",
        applies_when=applies_when,
        does_not_apply_when=["Unrelated tasks"],
        instructions=instructions,
        anti_patterns=[],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=SkillStatus.ACTIVE,
    )


def test_duplicate_normalized_names() -> None:
    findings = SkillAnalyzer().analyze(
        [
            _skill("a", "PR Diff First", ["review pull requests"], ["Must inspect diff"]),
            _skill("b", "pr diff first!", ["review pull requests"], ["Must inspect files"]),
        ]
    )
    assert any(finding.finding_type == "duplicate" for finding in findings)


def test_overlap_for_identical_applies_when() -> None:
    findings = SkillAnalyzer().analyze(
        [
            _skill("a", "A", ["customer refund policy"], ["Must check policy"]),
            _skill("b", "B", ["customer refund policy"], ["Must check source"]),
        ]
    )
    assert any(finding.finding_type == "overlap" for finding in findings)


def test_no_overlap_for_unrelated_applies_when() -> None:
    findings = SkillAnalyzer().analyze(
        [
            _skill("a", "A", ["customer refund policy"], ["Must check policy"]),
            _skill("b", "B", ["pull request review"], ["Must inspect diff"]),
        ]
    )
    assert not any(finding.finding_type == "overlap" for finding in findings)


def test_contradiction_for_opposed_modal_guidance() -> None:
    findings = SkillAnalyzer().analyze(
        [
            _skill("a", "Escalate", ["tier one support"], ["Must call escalation API"]),
            _skill("b", "Do not escalate", ["tier one support"], ["Never call escalation API"]),
        ]
    )
    assert any(finding.finding_type == "contradiction" for finding in findings)


def test_agreeing_negative_guidance_is_not_a_contradiction() -> None:
    findings = SkillAnalyzer().analyze(
        [
            _skill("a", "Do not escalate", ["tier one support"], ["Must not call escalation API"]),
            _skill("b", "Avoid escalation", ["tier one support"], ["Never call escalation API"]),
        ]
    )
    assert not any(finding.finding_type == "contradiction" for finding in findings)


def test_single_skill_has_no_findings() -> None:
    assert SkillAnalyzer().analyze([_skill("a", "A", ["one"], ["Must do one"])]) == []
