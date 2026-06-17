# Detection benchmark v1

`benchmark/v1` is the first citable public benchmark for lessonweaver's
deterministic failure-pattern detector. It contains synthetic or fully sanitized
traces only, with ground-truth labels for the detector's current signal families
and explicit no-candidate cases.

## Reproduce the scorecard

```bash
lessonweaver eval-detection benchmark/v1/corpus.json \
  --compare-results benchmark/v1/results.json
```

The command prints the JSON report and exits non-zero when the live detector
output differs from the checked-in `results.json`. CI runs the same comparison,
so detector changes must either preserve the benchmark scorecard or update the
results intentionally.

## Current results

The checked-in report is [`results.json`](results.json). It includes overall
precision, recall, F1, every per-case classification, and `by_pattern` metrics
for each labeled signal.

The v1 corpus intentionally includes `recurring_unflagged` false negatives:
these traces encode repeated mistakes that left no explicit error, evaluation,
or correction signal. They keep the conservative detector's known blind spot
visible without making the detector fire on weak text-only evidence.

## Corpus layout

Each case in [`corpus.json`](corpus.json) has:

- `case_id`: stable identifier used in result diffs.
- `should_detect`: ground truth for whether at least one candidate should be
  emitted.
- `pattern`: signal label used for per-pattern precision/recall reporting.
- `trace` or `trace_path`: inline trace JSON or a path relative to the corpus
  file.
- `notes`: short annotation rationale.

Patterns covered in v1:

- `metadata_flag`
- `human_correction`
- `failed_evaluation`
- `workflow_step`
- `error_retry`
- `tool_fallback`
- `corrected_outcome`
- `recurring_unflagged`
- `no_candidate`
