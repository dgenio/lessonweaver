"""Tests for persisted artifact schema-version helpers."""

from __future__ import annotations

import pytest

from lessonweaver.schema_versioning import (
    SCHEMA_VERSION,
    migrate_persisted_payload,
    stamp_schema_version,
)


def test_stamp_schema_version_returns_copy_with_current_version() -> None:
    original = {"id": "x", "schema_version": 0}
    stamped = stamp_schema_version(original)

    assert stamped["schema_version"] == SCHEMA_VERSION
    assert original["schema_version"] == 0


def test_migrate_persisted_payload_applies_ordered_migrations() -> None:
    def zero_to_one(payload: dict[str, object]) -> dict[str, object]:
        migrated = dict(payload)
        migrated["steps"] = ["0->1"]
        migrated["schema_version"] = 1
        return migrated

    def one_to_two(payload: dict[str, object]) -> dict[str, object]:
        migrated = dict(payload)
        migrated["steps"] = [*list(migrated["steps"]), "1->2"]
        migrated["schema_version"] = 2
        return migrated

    migrated = migrate_persisted_payload(
        {"id": "x"},
        label="test artifact",
        current_version=2,
        migrations={0: zero_to_one, 1: one_to_two},
    )

    assert migrated == {"id": "x", "steps": ["0->1", "1->2"], "schema_version": 2}


def test_migrate_persisted_payload_rejects_future_versions() -> None:
    with pytest.raises(ValueError, match="newer lessonweaver"):
        migrate_persisted_payload(
            {"schema_version": SCHEMA_VERSION + 1},
            label="test artifact",
        )
