"""Portable skill pack export, inspection, and import helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .models import SkillCard, SkillStatus
from .privacy import SimpleRedactor
from .registry import FileSystemRegistry

PACK_SCHEMA = "lessonweaver/skill-pack@1"
_EXPORTABLE_STATUSES = {SkillStatus.APPROVED, SkillStatus.ACTIVE}


def _canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _redact_value(value: Any, redactor: SimpleRedactor) -> Any:
    if isinstance(value, str):
        return redactor.redact(value)
    if isinstance(value, list):
        return [_redact_value(item, redactor) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item, redactor) for key, item in value.items()}
    return value


def _pack_payload_without_digest(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": pack.get("schema"),
        "metadata": pack.get("metadata"),
        "skills": pack.get("skills"),
    }


def verify_skill_pack(pack: dict[str, Any]) -> None:
    if pack.get("schema") != PACK_SCHEMA:
        raise ValueError(f"unsupported skill pack schema: {pack.get('schema')}")
    skills = pack.get("skills")
    if not isinstance(skills, list):
        raise ValueError("skill pack missing a skills list")
    expected_pack_digest = _digest(_pack_payload_without_digest(pack))
    if pack.get("pack_digest") != expected_pack_digest:
        raise ValueError("pack digest mismatch")
    for index, entry in enumerate(skills):
        if not isinstance(entry, dict) or not isinstance(entry.get("skill"), dict):
            raise ValueError(f"skill entry {index} must contain a skill object")
        expected_skill_digest = _digest(entry["skill"])
        if entry.get("digest") != expected_skill_digest:
            raise ValueError(f"skill digest mismatch for entry {index}")


def export_skill_pack(
    skills: list[SkillCard],
    *,
    name: str,
    version: str,
    publisher: str = "",
    redact: bool = True,
    allow_unapproved: bool = False,
) -> dict[str, Any]:
    redactor = SimpleRedactor()
    entries: list[dict[str, Any]] = []
    for skill in skills:
        if not allow_unapproved and skill.status not in _EXPORTABLE_STATUSES:
            raise ValueError(f"skill '{skill.id}' is not approved for pack export")
        skill_data = skill.to_dict()
        if redact:
            skill_data = _redact_value(skill_data, redactor)
        entries.append({"skill": skill_data, "digest": _digest(skill_data)})

    pack = {
        "schema": PACK_SCHEMA,
        "metadata": {
            "name": name,
            "version": version,
            "publisher": publisher,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "skills": entries,
    }
    pack["pack_digest"] = _digest(pack)
    return pack


def inspect_skill_pack(pack: dict[str, Any]) -> dict[str, Any]:
    verify_skill_pack(pack)
    return {
        "valid": True,
        "schema": pack["schema"],
        "metadata": pack["metadata"],
        "pack_digest": pack["pack_digest"],
        "skills": [
            {
                "id": entry["skill"]["id"],
                "name": entry["skill"].get("name", ""),
                "status": entry["skill"].get("status", ""),
            }
            for entry in pack["skills"]
        ],
    }


def import_skill_pack(pack: dict[str, Any], registry: FileSystemRegistry) -> dict[str, Any]:
    verify_skill_pack(pack)
    metadata = pack["metadata"]
    source_pack = {
        "name": metadata.get("name", ""),
        "version": metadata.get("version", ""),
        "publisher": metadata.get("publisher", ""),
        "pack_digest": pack["pack_digest"],
        "schema": pack["schema"],
    }
    imported: list[str] = []
    collisions: list[str] = []
    for entry in pack["skills"]:
        skill = SkillCard.from_dict(entry["skill"])
        try:
            registry.load_skill(skill.id)
        except FileNotFoundError:
            skill_metadata = dict(skill.metadata)
            skill_metadata["source_pack"] = dict(source_pack)
            imported_skill = replace(
                skill,
                status=SkillStatus.EXPERIMENTAL,
                metadata=skill_metadata,
                updated_at=datetime.now(timezone.utc),
            )
            registry.save_skill(imported_skill)
            imported.append(imported_skill.id)
        else:
            collisions.append(skill.id)
    return {
        "valid": True,
        "imported": imported,
        "collisions": collisions,
        "pack_digest": pack["pack_digest"],
    }
