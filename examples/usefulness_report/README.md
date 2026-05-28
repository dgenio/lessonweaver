# Example: usefulness report for a reviewed skill

A small, deterministic example that inspects how often one reviewed skill would
have been retrieved across a set of traces. It uses fixed synthetic data and
simple counts. No model is called.

Tracking issue: [#73](https://github.com/dgenio/lessonweaver/issues/73).

## Contents

| File | What it is |
| --- | --- |
| `registry/skills/skill-refund-policy-version.json` | One reviewed, **active** skill (already approved and promoted). |
| `traces/refund_match_1.json`, `traces/refund_match_2.json` | Tasks about refund policy — the skill should be retrieved. |
| `traces/unrelated_translation.json` | A translation task — the skill should be ignored. |
| `report.py` | Counts matching vs. unrelated traces and retrieved vs. ignored skills. |

## Run it

```bash
python examples/usefulness_report/report.py
```

Expected output:

```text
Skill under review: skill-refund-policy-version
Matching traces:    2
Unrelated traces:   1
Retrieved skills:   2
Ignored skills:     0
```

The same counts are available from `compute_report()` if you want to use them in
your own script.

## What the signal means

- **Matching traces**: tasks where the skill was retrieved by the deterministic
  lexical retriever. A higher share suggests the skill is scoped to tasks that
  actually occur.
- **Unrelated traces**: tasks where the skill was correctly *not* retrieved.
  This is the precision side — a skill that loads everywhere is noise.
- **Retrieved / ignored skills**: how many skills the loader included vs. omitted
  across all traces, within the default character budget.

## Limits of this signal

- Retrieval is **lexical**, so it measures token overlap, not real relevance.
- "Retrieved" is not "helped". This example does not measure outcomes; it only
  shows whether a skill *would have been loaded*.
- Counts are only as good as the trace sample. A handful of synthetic traces
  cannot tell you whether a skill reduces real repeated failures.
- For genuine effectiveness measurement (before/after failure rates, regressions)
  see the closed-loop roadmap issue
  [#61](https://github.com/dgenio/lessonweaver/issues/61).
