# ADR-0002: Require Human Review Before Activation

## Status

Accepted

## Context

The project exists to prevent unreviewed observations from becoming agent
instructions. README.md states that skills are reviewed, governed, and
auditable, with no skill activation without review. `governance.py` enforces
skill lifecycle transitions, and CLI approval flows promote reviewed candidates
through `OperationalLesson` and `SkillCard` artifacts.

## Decision

No detected or generated lesson may become an active skill without human review
and governed promotion. Assist features may prepare `LessonCandidate` input or
review material, but they cannot mark generated guidance active.

## Consequences

This keeps context injection auditable and reduces instruction-poisoning risk.
It also means automation must stop at candidate or draft boundaries unless a
caller explicitly applies a reviewed promotion path. Changes to status enums,
promotion rules, or CLI approval flows require lifecycle tests and migration
notes when persisted artifacts are affected.
