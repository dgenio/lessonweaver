# Persisted artifact schema versioning

lessonweaver registry JSON files and paused review sessions are long-lived user
data. Every file written by `FileSystemRegistry` and `save_session` includes a
top-level `schema_version` field so future model changes can migrate data
explicitly instead of relying on silent defaults.

## Current policy

- The current persisted schema version is `1`.
- Files without `schema_version` are treated as version `0`, the pre-versioning
  shape, and are migrated before model deserialization.
- Version `0 -> 1` is an identity migration plus the schema marker.
- Files with a version newer than the installed package are rejected with a
  "newer lessonweaver" error so users know to upgrade rather than loading data
  with unknown semantics.
- A version is supported when there is a registered migration path from that
  version to the current one. The project should keep migrations for all
  versions that may appear in user registries until a release note explicitly
  announces a narrower compatibility window.

## Adding a future migration

When a persisted shape changes:

1. Bump `SCHEMA_VERSION` in `lessonweaver.schema_versioning`.
2. Add a migration function for the previous version to the next version.
3. Keep the migration deterministic and local to JSON data; do not inspect the
   filesystem, call an LLM, or depend on network state.
4. Add tests for old fixtures, migration ordering, and future-version rejection.
5. Mention the new version and compatibility impact in the changelog or release
   notes.

Transient CLI output and hand-authored input files are separate contracts unless
they are explicitly saved into the registry or as a review session.
