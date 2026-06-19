# Protected Invariants

This project can grow LLM-assisted and embedding-backed extensions, but those
features must attach around the deterministic core rather than replacing it.
The boundaries below protect the design choices that make lessonweaver safe to
use in agent workflows.

## Hard Invariants

- **The core import graph stays dependency-free.** Importing `lessonweaver` must
  not import third-party packages. Runtime integrations belong in `examples/`
  or optional extras, not in `src/lessonweaver/`.
- **The core stays network-free and LLM-free.** `detection.py`, `interview.py`,
  `lint.py`, `retrieval.py`, `analysis.py`, `compile.py`, `loader.py`, and
  `governance.py` must be deterministic local code. They must not call models,
  embedding APIs, telemetry services, or remote registries.
- **Default detect, retrieve, and load paths are deterministic.**
  `LessonDetector.detect`, `SkillRetriever.retrieve`, and
  `SkillLoader.load_for_task` must return stable results for the same inputs.
  Randomness, clock reads, network calls, and hidden model calls do not belong
  in those default paths.
- **Review gates are mandatory before activation.** Assist output may create
  `LessonCandidate` input, but activation still flows through review,
  `OperationalLesson`, `SkillCard`, linting, and governed promotion. No feature
  may silently mark generated guidance active.
- **Export remains explicit.** Exporters render text and never write files
  implicitly; callers write only after an explicit user action.
- **Trace and registry data stays auditable.** Model fields are stable unless a
  migration is provided, and registry writes remain explicit JSON artifacts that
  reviewers can inspect.

## Extension Rule

ML and LLM features must be optional layers:

- Put third-party providers behind explicit interfaces and optional extras in
  `[project.optional-dependencies]`.
- Keep defaults off unless a command or API parameter opts in clearly.
- Preserve deterministic fallbacks for users without model or embedding
  dependencies.
- Treat model output as untrusted evidence or draft content. It can suggest,
  cluster, summarize, or prefill review material; it cannot bypass review,
  linting, or promotion.
- Record enough provenance for reviewers to tell which provider or heuristic
  produced an assist result.

## Do-Not-Rewrite List

- **Lexical retrieval is a baseline by design.** `retrieval.py` ranks active
  skills with deterministic token overlap. Embedding retrieval may layer on via
  a separate interface, but the lexical path remains the fallback and regression
  target.
- **Conservative detection thresholds are intentional.** `detection.py` should
  prefer false negatives over noisy guidance. Detection changes must be backed
  by the detection-eval corpus, not intuition.
- **The filesystem registry is the durable reference implementation.**
  Alternative registries can be added after scalability evidence, but the JSON
  filesystem path remains the inspectable baseline.
- **Simple dataclasses remain the contract surface.** Replacing the domain
  model with a framework-specific schema or runtime object graph would make
  artifacts harder to audit and migrate.

## Revisit Conditions

These invariants are not a veto on future work. Revisit one only with evidence:

- A benchmark or labeled eval shows the deterministic baseline cannot meet the
  documented target.
- A migration plan protects existing registry artifacts and exported skill
  cards.
- A new dependency is optional, isolated, and tested without network access.
- The default path remains deterministic and review-gated after the change.
