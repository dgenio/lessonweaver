# ADR-0005: Use Filesystem JSON As The Reference Registry

## Status

Accepted

## Context

`registry.py` persists candidates, lessons, skills, artifacts, and usage events
as JSON files under a root directory. The CLI and examples use this filesystem
registry as the shared storage path. There is no database service, migration
daemon, or hidden remote state in the default workflow.

## Decision

The filesystem JSON registry is the reference implementation for persisted
lessonweaver artifacts. Alternative registries may be added later, but they must
preserve the same explicit artifact model and keep the filesystem path usable.

## Consequences

Artifacts are inspectable, diffable, and easy to test with `tmp_path`. The
tradeoff is that large installations may eventually need indexing, locking, or
remote storage. Those changes should be driven by measured registry scaling
needs and introduced through an interface that does not weaken local auditability.
