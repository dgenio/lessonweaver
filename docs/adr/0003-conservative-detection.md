# ADR-0003: Prefer Conservative Lesson Detection

## Status

Accepted

## Context

`LessonDetector.detect` intentionally emits candidates from a small set of
explainable signals such as human corrections, failed evaluations, and recovery
after errors. AGENTS.md instructs contributors to add the smallest deterministic
rule and to prefer false negatives over false positives. `detection_eval.py`
provides a corpus-based way to measure detection changes.

## Decision

Detection should remain conservative. New signals must be deterministic,
explainable, and covered by true-positive, false-positive, and edge-case tests.
Changes that broaden detection should be evaluated against the detection corpus.

## Consequences

The system may miss some useful lessons, but emitted candidates are easier for
reviewers to trust. This protects users from noisy skill libraries and context
poisoning. Higher-recall model or embedding assistance can propose additional
candidates, but the deterministic detector remains the baseline.
