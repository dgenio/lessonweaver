# LessonWeaver roadmap

LessonWeaver is in **product incubation**. The roadmap is organized around falsifying or validating one product thesis rather than expanding subsystems in parallel.

See [`../INCUBATION.md`](../INCUBATION.md) for graduation and kill criteria and issue #111 for the experiment specification.

## Phase 1 — restore semantic integrity

Goal: make reviewed decisions control what is produced.

Required work is limited to the minimum needed for a trustworthy experiment:

- #373 — minimal `AgentChangeProposal` domain model;
- #266 — action-respecting realization;
- #171 — typed review state and compatibility migration;
- minimum #308 evidence-boundary hardening required by the experiment.

Exit criteria:

- reject and `no_change` create no durable change artifact;
- non-Skill decisions never silently create a `SkillCard`;
- reviewed intervention controls realization;
- experimental evidence is bounded/sanitized as documented;
- legacy compatibility is sufficient not to contaminate the experiment with migration failures.

Do not complete unrelated architecture work merely because it is adjacent.

## Phase 2 — one offline beachhead

Goal: exercise the complete decision loop using one evidence source.

- #105 — import GitHub PR-review correction evidence;
- produce a proposal;
- review it;
- realize one of `no_change`, `instruction_patch`, `skill`, or `deterministic_check`;
- define positive/negative evaluation cases;
- record a result.

Exit criterion:

```text
realistic PR correction fixture
-> AgentChangeProposal
-> reviewed realization
-> positive/negative cases
-> recorded outcome
```

Generic trace/framework adapters remain deferred.

## Phase 3 — pilot, not proof

Run the 12–20 case methodology-calibration pilot in #111.

Use it to:

- estimate model/runtime outcome variance;
- identify intervention-taxonomy ambiguity;
- refine operational definitions;
- detect unusable metrics;
- determine confirmatory case/repeated-run requirements;
- test the experiment harness.

Pilot outcomes are exploratory and must not become the launch claim.

## Phase 4 — preregister the confirmatory experiment

Before viewing aggregate confirmatory results, freeze and version:

- hypotheses;
- primary/secondary metrics;
- superiority/non-inferiority margins;
- eligibility/exclusion rules;
- intervention taxonomy;
- strongest human and checklist baselines;
- repeated-run strategy;
- treatment assignment/counterbalancing;
- analysis and uncertainty reporting;
- confirmatory corpus or holdout commitment.

Use independent/blinded intervention adjudication where feasible and preserve reviewer disagreement.

## Phase 5 — confirmatory experiment

LessonWeaver competes against an experienced human with the **same intervention repertoire**, not only against no-change/manual-instruction/manual-Skill baselines.

Mandatory gate classes:

1. behavior — recurrence and task success;
2. safety — regressions and negative cases;
3. product value — at least one meaningful predeclared advantage;
4. complexity — benefit remains worthwhile after workflow/maintenance overhead.

All four must pass under the predeclared rules for the standalone direction to continue unchanged.

## Phase 6 — ablate the product

Compare:

- evidence packet only;
- evidence + LessonWeaver recommendation;
- full proposal + realization + eval workflow.

Use the result to remove or sideline architecture that does not create measured value.

Examples:

- evidence packet ~= full workflow -> shrink toward a GitHub evidence/change-proposal utility;
- recommendation captures most value -> avoid mandatory registry/runtime machinery;
- eval/negative-case generation drives the win -> prioritize that capability rather than exporter breadth.

A smaller evidence-supported product is a successful incubation result.

## Phase 7 — external replication

Only after the internal confirmatory gate passes, recruit unrelated maintainers/teams using their own coding-agent corrections.

Broad distribution waits until users can:

- understand the evidence/proposal without maintainer coaching;
- obtain measurable value on their own cases;
- voluntarily reuse the workflow on a later correction;
- reveal which parts they replace with native Git/agent tooling.

## Phase 8 — adoption after graduation

Only after internal + external gates pass:

- #89 — GitHub-native review UX if external use demonstrates demand;
- #26 — lifecycle events if operational use needs them;
- #355 — evidence-backed positioning and when-not-to-use guidance;
- launch demo/article grounded in preregistered representative cases;
- reconsider deferred sources/integrations based on actual demand.

## Deferred until evidence justifies reopening

- historical PR/CI mining;
- AgentEvent/OpenTelemetry sources;
- OpenCode/framework-specific adapters;
- runtime retrieval as mandatory architecture;
- ContextWeaver integration work not needed by the experiment;
- new exporter destinations;
- automated promotion;
- organization governance;
- broad marketing/distribution work.

## Roadmap decision gate

Continue the standalone product only if #111 supports all of:

- non-inferior behavior vs the strongest human baseline;
- no material safety disadvantage;
- at least one meaningful predeclared product-value advantage;
- worthwhile complexity-adjusted benefit;
- external replication showing unaided reuse.

Otherwise choose the evidence-supported result: narrow, move a component elsewhere, or archive.

## Backlog/WIP rule

Before graduation, new P0/P1 product work must either:

- unblock the experiment;
- make the experiment trustworthy; or
- fix an adoption-blocking defect observed during external replication.

Everything else is deferred, regardless of how inexpensive AI-assisted implementation appears.