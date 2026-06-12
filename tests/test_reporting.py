"""Tests for stale and unused skill reporting."""

from datetime import datetime, timedelta, timezone

from lessonweaver.models import (
    RiskLevel,
    RolloutMetadata,
    RolloutStatus,
    Scope,
    SkillCard,
    SkillStatus,
    SkillUsageEvent,
)
from lessonweaver.registry import FileSystemRegistry
from lessonweaver.reporting import SkillReporter

NOW = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)


def _skill(
    skill_id: str = "skill-1",
    *,
    status: SkillStatus = SkillStatus.ACTIVE,
    confidence: float = 0.8,
    expires_at: datetime | None = None,
) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name="Test Skill",
        description="A test skill with enough detail.",
        applies_when=["testing"],
        does_not_apply_when=["production"],
        instructions=["do this"],
        anti_patterns=["don't do that"],
        evidence_trace_ids=["trace-1"],
        confidence=confidence,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.1.0",
        status=status,
        expires_at=expires_at,
    )


def _log_usage(registry: FileSystemRegistry, skill_id: str) -> None:
    registry.save_usage_event(
        SkillUsageEvent(
            id=f"usage-{skill_id}",
            skill_id=skill_id,
            skill_version="0.1.0",
            task_context="testing reuse",
            loaded_at=NOW,
        )
    )


def test_report_stale_empty_registry_returns_empty(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    assert SkillReporter().report_stale(registry, now=NOW) == []


def test_report_stale_healthy_used_skill_has_no_findings(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    _log_usage(registry, "skill-1")
    assert SkillReporter().report_stale(registry, now=NOW) == []


def test_report_stale_flags_expired_skill(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    skill = _skill(expires_at=NOW - timedelta(days=1))
    skill.rollout = RolloutMetadata(status=RolloutStatus.CANARY, review_date=NOW)
    registry.save_skill(skill)
    _log_usage(registry, "skill-1")
    reports = SkillReporter().report_stale(registry, now=NOW)
    reasons = {report.reason for report in reports}
    assert "expired" in reasons
    expired = next(report for report in reports if report.reason == "expired")
    assert expired.recommendation == "revalidate"
    assert expired.last_used_at == NOW
    assert expired.rollout_status is RolloutStatus.CANARY
    assert expired.review_date == NOW


def test_report_stale_does_not_flag_future_expiry(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill(expires_at=NOW + timedelta(days=1)))
    _log_usage(registry, "skill-1")
    assert SkillReporter().report_stale(registry, now=NOW) == []


def test_report_stale_flags_deprecated_skill(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill(status=SkillStatus.DEPRECATED))
    _log_usage(registry, "skill-1")
    reports = SkillReporter().report_stale(registry, now=NOW)
    deprecated = next(report for report in reports if report.reason == "deprecated")
    assert deprecated.recommendation == "remove"


def test_report_stale_flags_low_confidence_skill(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill(confidence=0.2))
    _log_usage(registry, "skill-1")
    reports = SkillReporter().report_stale(registry, now=NOW)
    assert any(report.reason == "low_confidence" for report in reports)


def test_report_stale_flags_never_used_skill(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    reports = SkillReporter().report_stale(registry, now=NOW)
    never_used = next(report for report in reports if report.reason == "never_used")
    assert never_used.last_used_at is None
    assert never_used.recommendation == "revalidate"
