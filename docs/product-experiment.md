# LessonWeaver product experiment

This document is the reproducible protocol template for issue #111.

The purpose is to test whether LessonWeaver adds material value over a strong simple human process without giving the product an unfair intervention advantage.

## Product question

> For recurring coding-agent failures already corrected in review, does an evidence-backed proposal workflow improve decision quality, reviewer effort, or validated outcomes enough to justify its additional complexity?

## Intervention space

Every decision-making condition that may choose an intervention receives the same initial repertoire:

- `no_change`;
- `instruction_patch`;
- `skill`;
- `deterministic_check`.

`deterministic_check` includes a test, hook, CI check, workflow gate, or equivalent deterministic enforcement.

If the pilot discovers a genuinely necessary intervention outside this taxonomy, record it as an out-of-taxonomy case. Do not add the option only to LessonWeaver.

## Baselines and treatments

### B0 — control

No durable change.

### B1 — minimal decision checklist

A deliberately small human process with no LessonWeaver machinery:

```text
Is there enough evidence that the failure is recurring and worth a durable change?
No -> no_change.

Can the required behavior be enforced deterministically at acceptable cost?
Yes -> deterministic_check.

Does the behavior require reusable, scoped, multi-step guidance that should be loaded selectively?
Yes -> skill.

Otherwise -> the narrowest repository instruction patch.
```

Freeze the exact checklist before confirmatory execution.

### B2 — human best intervention

An experienced reviewer receives equivalent eligible evidence and may choose any intervention from the full shared repertoire, then writes the smallest appropriate realization manually.

This is the strongest product baseline.

### T1 — evidence packet only

Normalize/present the correction evidence in the LessonWeaver-compatible packet, but provide no LessonWeaver intervention recommendation. The human chooses and writes the intervention.

### T2 — recommendation

Evidence packet + LessonWeaver intervention recommendation. The human makes the final decision and writes/edits the realization.

### T3 — full LessonWeaver

Evidence -> proposal -> human review -> selected realization -> positive/negative cases -> recorded result.

## Phase A — pilot

Use 12–20 realistic corrections from at least three repositories.

The pilot is for methodology calibration, not launch proof.

Include:

- `no_change` cases;
- instruction cases;
- Skill cases;
- deterministic-enforcement cases;
- ambiguous/insufficient-evidence cases;
- negative cases that could expose over-generalization.

Prefer real agent/review history where privacy/licensing permits. Label synthetic fixtures clearly.

### Pilot outputs

Estimate or decide:

- outcome variance across comparable model/runtime runs;
- repeated-run requirement per treatment/case;
- intervention-taxonomy ambiguities;
- unusable/noisy metrics;
- realistic reviewer-time measurement;
- experiment harness defects;
- provisional effect sizes for confirmatory planning.

Do not convert pilot wins into public causal/product claims.

## Gold/adjudication record

Each case should contain:

```text
case_id:
source_repository:
source_evidence_refs:
observed_behavior:
expected_behavior:
recurrence_status: established|uncertain|absent
minimum_evidence_required:
preferred_interventions:
acceptable_alternatives:
expected_scope:
risk_notes:
positive_cases:
negative_cases:
reviewer_1_decision:
reviewer_2_decision:
adjudication_notes:
```

### Independence

For confirmatory cases:

- use at least two intervention reviewers where practical;
- hide LessonWeaver's recommendation until gold adjudication is complete;
- preserve disagreement instead of forcing consensus;
- include a source-repository maintainer or another non-LessonWeaver designer where practical;
- report inter-reviewer agreement as context for the achievable ceiling.

## Phase B — preregistration/freeze

Before inspecting aggregate confirmatory outcomes, version/freeze:

- hypotheses;
- primary/secondary metrics;
- superiority/non-inferiority margins;
- eligibility/exclusion rules;
- intervention taxonomy;
- B1 checklist;
- treatment assignment/counterbalancing;
- model/runtime/environment versions;
- repeated-run strategy;
- handling of failed/missing runs;
- statistical summaries/uncertainty intervals;
- confirmatory corpus or holdout commitment.

Changes after looking at aggregate confirmatory outcomes are exploratory and must be labelled as such.

## Confirmatory metrics

### Behavior gate — mandatory

- target-failure recurrence;
- overall task success.

T3 must be non-inferior to B2 under the frozen margins.

### Safety gate — mandatory

- regression rate;
- negative-case pass rate;
- over-broad activation/context pollution where applicable.

T3 must not materially underperform B2.

### Product-value gate — mandatory

At least one predeclared material advantage over B2 must survive, for example:

- intervention-selection quality relative to independent adjudication;
- lower reviewer time;
- fewer correction cycles / lower edit distance;
- more correct `no_change` or `needs_evidence` decisions;
- better scoping/negative-case design;
- provenance shown to be operationally useful in independent use.

### Complexity gate — mandatory

Account for:

- onboarding/setup time;
- proposal/review overhead;
- token/context overhead;
- persistence/registry burden;
- realization maintenance burden.

A checklist or thin script with equivalent outcomes at materially lower complexity defeats the full standalone product hypothesis.

## Ablation interpretation

Compare T1, T2, and T3.

Use the result to shrink the product when appropriate:

- T1 ~= T3 -> evidence presentation is the main value; shrink toward a GitHub/evidence utility.
- T2 ~= T3 -> recommendation is valuable, but full realization/runtime machinery may not be.
- T3 wins mainly through positive/negative cases -> prioritize validation support rather than exporter breadth.
- no material advantage over B1/B2 -> narrow or stop.

Do not preserve subsystems because they are already implemented.

## External replication

After the internal confirmatory gate passes, recruit unrelated maintainers/teams already using coding agents.

Use their own historical/live corrections rather than teaching the LessonWeaver taxonomy first.

Observe:

- unaided comprehension;
- onboarding/review time;
- intervention choices;
- whether they deliberately choose `no_change`/deterministic enforcement;
- which product parts they bypass;
- whether they voluntarily reuse LessonWeaver on a later correction.

Broad promotion waits for this replication gate.

## Final decision template

Publish exactly one recommendation:

### CONTINUE STANDALONE

All behavior, safety, product-value, complexity, and replication gates pass.

### NARROW

A smaller subsystem captures the measurable value better than the full architecture.

### MERGE SELECTED CAPABILITY

A useful evidence/eval/contract component belongs in another Weaver tool rather than a standalone LessonWeaver product.

### ARCHIVE

The strongest simple baseline is equivalently effective or safer/cheaper.

A negative/narrow result is successful incubation when it prevents further unsupported investment.

## Launch evidence if the product graduates

Use a representative case from the preregistered confirmatory corpus, not a post-hoc showcase.

Include:

- before/after behavioral receipt;
- B1/B2 comparison;
- one `no_change` or deterministic-enforcement example;
- reviewer/context/complexity costs;
- failed/negative cases and uncertainty;
- explicit non-claims.

Do not market pilot results as confirmatory evidence.