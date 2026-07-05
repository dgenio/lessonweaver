# Detection benchmark contribution guide

The public detection benchmark measures deterministic lesson-candidate
detection on annotated agent traces. Contributions should make detector quality
more measurable without adding private data or weak labels.

## Annotation policy

Label a trace with `should_detect: true` only when it contains a concrete signal
that lessonweaver should conservatively treat as evidence for a reusable lesson:

- explicit `metadata.lesson_candidate` flags
- `human_correction` events
- failed `evaluation_result` events
- workflow steps followed by `error` or `human_correction`
- `error` followed by `retry` and successful or corrected outcome
- failed tool call followed by a different successful tool call
- `outcome: corrected_by_human` without a preserved correction event

Use `should_detect: false` for benign successes, text that merely contains words
like "error", failed tool calls without a successful fallback, or workflow steps
that completed without a later failure.

The detector intentionally prefers false negatives. If a trace shows a plausible
recurring mistake but lacks a concrete signal, label it with
`pattern: recurring_unflagged`, document the reason in `notes`, and expect the
current detector to miss it unless a future heuristic is deliberately added.

## Sanitization checklist

Only synthetic or fully sanitized traces belong in the public benchmark.

Before submitting a case:

- Run the trace through `TraceSanitizer.default_rules()` or the CLI sanitization
  path used by the importer.
- Manually review every `content`, `task`, `source`, and `metadata` value.
- Replace plausible names, emails, tokens, account ids, URLs, customer details,
  repository names, ticket ids, and exact timestamps.
- Keep the smallest event sequence that demonstrates the signal.
- Add a `notes` value explaining the annotation decision.

Reject a submission when any value still looks like it could identify a real
person, customer, private repository, private service, or incident.

## Contribution path

1. Open a trace importer request with a small synthetic/redacted sample when the
   source format is new.
2. Add benchmark cases to the latest `benchmark/v*/corpus.json`.
3. Run:

   ```bash
   lessonweaver eval-detection benchmark/v1/corpus.json \
     --compare-results benchmark/v1/results.json
   ```

4. If the detector output intentionally changed, the guard prints exactly which
   metric, per-pattern value, or `case_id` drifted. Regenerate the scorecard in
   the same pull request and explain the delta. The regeneration command writes
   deterministic, sorted-key output, so it diffs cleanly:

   ```bash
   lessonweaver eval-detection benchmark/v1/corpus.json > benchmark/v1/results.json
   ```

5. Include the sanitization checklist outcome in the pull request description.
