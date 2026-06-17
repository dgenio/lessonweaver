# Detection-quality corpus

A small labeled corpus for measuring how well the conservative `LessonDetector`
finds recurring failures — and, just as importantly, how well it stays silent on
benign runs. It answers the skeptic's question with evidence rather than
assertion: *does detection find real problems, or does it mostly re-surface
mistakes a human already flagged?*

Each case pairs a trace with a ground-truth `should_detect` label:

- `should_detect: true` — the detector ought to emit at least one candidate.
- `should_detect: false` — a benign variation; the detector should stay silent.

A case supplies its trace either inline (`"trace": { ... }`) or by reference
(`"trace_path": "../traces/foo.json"`, resolved relative to this file).

## Run it

```bash
lessonweaver eval-detection examples/detection_corpus/corpus.json
```

Add `--min-precision` / `--min-recall` to fail (exit code 1) when quality drops
below a floor — useful as a CI gate:

```bash
lessonweaver eval-detection examples/detection_corpus/corpus.json --min-precision 1.0
```

To compare independent recall with clustered recall for repeated weak signals:

```bash
lessonweaver eval-detection examples/detection_corpus/corpus.json --with-clustering
```

Programmatic use:

```python
from lessonweaver import DetectionCorpus, run_detection_eval

report = run_detection_eval(DetectionCorpus.from_file("examples/detection_corpus/corpus.json"))
print(report.precision, report.recall, report.f1)
```

## Baseline scorecard (current `main`)

| Metric | Value |
| --- | --- |
| True positives | 5 |
| False negatives | 2 |
| False positives | 0 |
| True negatives | 3 |
| Precision | 1.00 |
| Recall | 0.714 |
| F1 | 0.833 |

The two false negatives (`recurring-unflagged-version-miss` and
`recurring-unflagged-version-repeat`) are **deliberate**: they encode the same
recurring mistake that left no error, failed evaluation, or human correction in
either trace. Independent scoring misses them, while the clustered eval path can
measure whether repeated weak signals improve recall without increasing
single-trace false positives. `precision = 1.0` reflects that the detector never
fires on the benign cases.

`tests/test_detection_eval.py` locks these numbers so a change that quietly
regresses detection quality fails CI.

For the versioned public benchmark, current results, annotation rules, and the
contribution path for sanitized traces, see
[`benchmark/v1`](../../benchmark/v1/README.md) and
[`docs/detection-benchmark.md`](../../docs/detection-benchmark.md).
