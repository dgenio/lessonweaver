from __future__ import annotations

import copy
import hashlib
import json

import pytest

from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.registry import FileSystemRegistry
from lessonweaver.skill_packs import (
    export_skill_pack,
    import_skill_pack,
    inspect_skill_pack,
)


def _canonical_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(data: object) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _rehash_pack(pack: dict[str, object]) -> None:
    skills = pack["skills"]
    assert isinstance(skills, list)
    for entry in skills:
        assert isinstance(entry, dict)
        entry["digest"] = _digest(entry["skill"])
    pack["pack_digest"] = _digest(
        {
            "schema": pack.get("schema"),
            "metadata": pack.get("metadata"),
            "skills": pack.get("skills"),
        }
    )


def _skill(skill_id: str = "skill-1", *, status: SkillStatus = SkillStatus.APPROVED) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name="PR Diff First",
        description="Inspect changed files before reviewing pull requests.",
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Inspect changed files first"],
        anti_patterns=["title-only approval"],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=status,
    )


def test_skill_pack_export_import_round_trip_with_experimental_status(tmp_path) -> None:
    pack = export_skill_pack(
        [_skill()],
        name="coding-agent-basics",
        version="1.0.0",
        publisher="ai-platform",
    )
    inspection = inspect_skill_pack(pack)
    assert inspection["valid"] is True
    assert inspection["skills"] == [
        {"id": "skill-1", "name": "PR Diff First", "status": "approved"}
    ]

    registry = FileSystemRegistry(tmp_path)
    report = import_skill_pack(pack, registry)

    assert report["imported"] == ["skill-1"]
    imported = registry.load_skill("skill-1")
    assert imported.status is SkillStatus.EXPERIMENTAL
    assert imported.description == "Inspect changed files before reviewing pull requests."
    assert imported.metadata["source_pack"]["name"] == "coding-agent-basics"
    assert imported.metadata["source_pack"]["pack_digest"] == pack["pack_digest"]


def test_skill_pack_import_rejects_tampered_content(tmp_path) -> None:
    pack = export_skill_pack([_skill()], name="pack", version="1.0.0")
    tampered = copy.deepcopy(pack)
    tampered["skills"][0]["skill"]["description"] = "changed after export"

    with pytest.raises(ValueError, match="pack digest mismatch"):
        import_skill_pack(tampered, FileSystemRegistry(tmp_path))


def test_skill_pack_export_blocks_unapproved_skill_without_override() -> None:
    with pytest.raises(ValueError, match="not approved"):
        export_skill_pack([_skill(status=SkillStatus.DRAFT)], name="pack", version="1.0.0")


def test_skill_pack_import_reports_id_collisions(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    pack = export_skill_pack([_skill()], name="pack", version="1.0.0")

    report = import_skill_pack(pack, registry)

    assert report["imported"] == []
    assert report["collisions"] == ["skill-1"]


def test_skill_pack_import_validates_all_skills_before_writing(tmp_path) -> None:
    pack = export_skill_pack(
        [_skill("skill-1"), _skill("skill-2")],
        name="pack",
        version="1.0.0",
    )
    broken = copy.deepcopy(pack)
    broken["skills"][1]["skill"]["risk_level"] = "impossible"
    _rehash_pack(broken)

    registry = FileSystemRegistry(tmp_path)
    with pytest.raises(ValueError, match="impossible"):
        import_skill_pack(broken, registry)

    with pytest.raises(FileNotFoundError):
        registry.load_skill("skill-1")
