# LessonWeaver incubation contract

LessonWeaver is an **incubating product hypothesis**, not a proven self-improving-agent system.

The repository should optimize for learning whether the product deserves to exist in its current form, not for maximizing feature throughput.

## Product hypothesis

For recurring coding-agent failures that have already been corrected in review, an evidence-backed proposal workflow can help a team choose and validate the **smallest appropriate durable intervention** better or more efficiently than a simple human process.

Initial intervention space:

- no durable change;
- repository instruction patch;
- reusable Skill;
- deterministic test, hook, CI check, or workflow gate.

A Skill is one possible realization, not the product's default object.

## Beachhead

The incubation beachhead is intentionally narrow:

> A coding agent makes a mistake in a GitHub pull request, a human corrects it, and the team needs to decide whether anything durable should change so that class of failure is less likely to recur.

The first evidence source is GitHub PR-review correction evidence. Generic framework traces, OpenTelemetry, additional exporters, organization governance, and broad runtime-retrieval architecture remain deferred.

## Current experiment

The source of truth is issue #111.

The sequence is:

1. restore minimum semantic integrity required for the experiment;
2. build one offline GitHub PR-correction vertical slice;
3. run a 12–20 case **pilot** to debug the methodology and estimate variance;
4. preregister/freeze the confirmatory design;
5. run the confirmatory experiment against equally capable baselines;
6. ablate evidence presentation vs recommendation vs full workflow;
7. replicate with unrelated maintainers before broad promotion.

The pilot is exploratory and must not become the launch claim.

## Strongest baseline

LessonWeaver must compete against an experienced human who sees equivalent evidence and may choose from the **same intervention repertoire**:

- `no_change`;
- `instruction_patch`;
- `skill`;
- `deterministic_check`.

A tiny decision-checklist baseline is also required. If a checklist or thin script performs equivalently at much lower complexity, the correct outcome is to shrink the product.

## Evidence hierarchy

### Behavior — mandatory

LessonWeaver must be non-inferior to the strongest human baseline on:

- target-failure recurrence;
- overall task success.

### Safety — mandatory

It must not materially worsen:

- regression rate;
- negative-case performance;
- over-broad activation/context pollution where applicable.

### Product value — mandatory

At least one predeclared material advantage must survive against the strongest human baseline, such as:

- better intervention-selection quality relative to independent adjudication;
- lower reviewer time/correction cycles;
- more correct `no_change` / `needs_evidence` decisions;
- better scoping/negative cases;
- operationally useful provenance demonstrated by users rather than merely liked in principle.

### Complexity — mandatory

The benefit must remain worthwhile after setup, review, context/token, persistence, and maintenance overhead.

## Graduation criteria

The standalone product graduates only when all are true:

1. behavior gate passes;
2. safety gate passes;
3. at least one meaningful product-value advantage survives against the strongest human baseline;
4. the advantage remains complexity-adjusted worthwhile;
5. ablation shows which capabilities actually create the value;
6. unrelated maintainers can obtain and voluntarily reuse the value without maintainer coaching.

Stars, internal benchmark scores, feature count, or same-maintainer demos are not graduation criteria.

## Narrow / kill criteria

Narrow, merge selected capabilities elsewhere, or archive the standalone direction when evidence shows that:

- a decision checklist or human best-intervention process is equivalently effective;
- most value comes only from presenting correction evidence clearly;
- recommendation adds little beyond human judgment;
- proposal overhead exceeds avoided review/debugging cost;
- registry/runtime loading is unnecessary for the beachhead;
- LessonWeaver mainly reproduces the same change with extra metadata;
- behavioral or safety gates fail despite positive subjective feedback;
- unrelated users do not voluntarily reuse the workflow.

A smaller outcome is a successful incubation result when supported by evidence.

Possible successful narrowed forms include:

- GitHub-native PR-correction -> reviewed change-proposal utility;
- evidence/adjudication helper;
- positive/negative-case helper;
- selected contracts moved into another Weaver component.

## Independence and experimental integrity

For the confirmatory experiment:

- intervention gold decisions should have at least two reviewers where feasible;
- reviewers should not see LessonWeaver's recommendation before adjudicating the gold decision;
- disagreement should be preserved/reported rather than forced into false consensus;
- pass thresholds and analysis rules must be frozen before aggregate confirmatory outcomes are inspected;
- model/runtime/environment versions and repeated-run strategy must be recorded;
- retrieval/application success must be separated from behavioral success.

## WIP rule

Before graduation, a proposed P0/P1 product feature must answer one of:

- Does this unblock the existential experiment?
- Does this make the experiment trustworthy?
- Does this fix an adoption-blocking defect observed during external replication?

Otherwise defer it.

Do not preserve already-built architecture merely because removing or sidelining it would feel like lost work.

## Canonical references

- #104 — product-validation epic
- #111 — falsification experiment and launch gate
- #356 — public evidence-first roadmap
- #373 — minimal `AgentChangeProposal`
- #266 — action-respecting realization
- #171 — typed review state
- #105 — GitHub PR-review correction evidence

This file is a concise incubation contract. When it conflicts with speculative feature roadmaps, the experiment and its kill/graduation gates take precedence.