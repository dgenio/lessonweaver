# Workflow recommendation: Inspect diffs before review approval

## Problem observed
The agent approved a pull request without reading the diff.

## Recommended workflow change
Always inspect changed files before approving a pull request.

## Rationale
Derived from reviewed trace evidence; prefer a deterministic fix where possible.

## Evidence
- trace: trace-pr-review-001
