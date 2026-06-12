# Guardrail: Inspect diffs before review approval

## Trigger condition
The agent approved a pull request without reading the diff.

## Blocked behavior
Completing the task without applying the corrective check below.

## Rationale
Always inspect changed files before approving a pull request.

## Evidence
- trace: trace-pr-review-001
