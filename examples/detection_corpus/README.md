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
| False negatives | 1 |
| False positives | 0 |
| True negatives | 3 |
| Precision | 1.00 |
| Recall | 0.833 |
| F1 | 0.909 |

The single false negative (`recurring-unflagged-version-miss`) is **deliberate**:
it encodes a recurring mistake that left no error, failed evaluation, or human
correction in the trace. The conservative detector misses it today. Keeping it in
the corpus makes that gap measurable, and it is the kind of case multi-trace
clustering (#37) and future heuristics should eventually close. `precision = 1.0`
reflects that the detector never fires on the benign cases.

`tests/test_detection_eval.py` locks these numbers so a change that quietly
regresses detection quality fails CI.

For the versioned public benchmark, current results, annotation rules, and the
contribution path for sanitized traces, see
[`benchmark/v1`](../../benchmark/v1/README.md) and
[`docs/detection-benchmark.md`](../../docs/detection-benchmark.md).
