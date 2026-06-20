"""Schema-version helpers for persisted lessonweaver JSON artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping

SCHEMA_VERSION = 1

Migration = Callable[[dict[str, object]], dict[str, object]]


def _migrate_v0_to_v1(payload: dict[str, object]) -> dict[str, object]:
    migrated = dict(payload)
    migrated["schema_version"] = 1
    return migrated


MIGRATIONS: dict[int, Migration] = {0: _migrate_v0_to_v1}


def stamp_schema_version(payload: dict[str, object]) -> dict[str, object]:
    """Return a copy of ``payload`` stamped with the current schema version."""
    stamped = dict(payload)
    stamped["schema_version"] = SCHEMA_VERSION
    return stamped


def migrate_persisted_payload(
    payload: dict[str, object],
    *,
    label: str,
    current_version: int = SCHEMA_VERSION,
    migrations: Mapping[int, Migration] | None = None,
) -> dict[str, object]:
    """Migrate a persisted JSON object to ``current_version``.

    Missing ``schema_version`` is treated as version 0 so registries written by
    earlier lessonweaver versions remain readable. Future versions are rejected
    with an actionable error instead of being silently coerced.
    """
    migrated = dict(payload)
    version = _schema_version(migrated, label=label)
    if version > current_version:
        raise ValueError(
            f"{label} was produced by a newer lessonweaver "
            f"(schema_version {version}; current {current_version})"
        )

    migration_table = migrations if migrations is not None else MIGRATIONS
    while version < current_version:
        migration = migration_table.get(version)
        if migration is None:
            raise ValueError(
                f"{label} has schema_version {version}, but no migration to "
                f"{version + 1} is registered"
            )
        migrated = migration(dict(migrated))
        next_version = _schema_version(migrated, label=label)
        expected = version + 1
        if next_version != expected:
            raise ValueError(
                f"{label} migration {version}->{expected} produced schema_version {next_version}"
            )
        version = next_version

    return migrated


def _schema_version(payload: dict[str, object], *, label: str) -> int:
    raw_version = payload.get("schema_version", 0)
    if isinstance(raw_version, bool) or not isinstance(raw_version, int):
        raise ValueError(f"{label} has invalid schema_version {raw_version!r}")
    if raw_version < 0:
        raise ValueError(f"{label} has invalid schema_version {raw_version!r}")
    return raw_version
