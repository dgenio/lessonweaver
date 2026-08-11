# LessonWeaver pilot corpus candidates

Status: **exploratory candidate pool**, not confirmatory evidence and not gold-labelled.

This file seeds the pilot described in #111 with real review→fix sequences from agent-assisted pull requests. It deliberately does **not** decide what the durable intervention should have been. Intervention labels belong to later independent adjudication.

## Selection rules

A PR enters this candidate pool only when the available PR body/comment history contains evidence of:

1. an agent-assisted implementation or review/fix workflow;
2. a concrete correction raised during review/audit rather than a generic “looks good” discussion; and
3. a subsequent change, resolution, or documented fix responding to that correction.

For the pilot we keep **one principal correction per PR** to reduce within-PR correlation.

This is still a candidate pool. Before a case enters the pilot, #105/#111 should verify:

- correction actor and provenance;
- exact review comment / commit / file references;
- that the correction is eligible under the GitHub-PR-review beachhead;
- privacy/licensing suitability;
- whether the occurrence is genuinely recurring, a single observation, or unknown.

A review-bot correction may be useful for methodology/debugging but must not be silently represented as a human correction in the confirmatory corpus.

## Candidate summary

| ID | Repository / PR | Principal correction | Follow-up evidence | Correction actor | Recurrence | Gold intervention |
| --- | --- | --- | --- | --- | --- | --- |
| CW-537 | [ChainWeaver #537](https://github.com/dgenio/ChainWeaver/pull/537) | A review-driven release-tag guard compared the tag SHA with the wrong merge value and would reject ordinary valid data | PR documents the bad guard and the later correction after checking it against normal repository data | maintainer review documented; verify exact comment | single observation | **unset** |
| CW-518 | [ChainWeaver #518](https://github.com/dgenio/ChainWeaver/pull/518) | Observe-integration config handling could destructively overwrite malformed JSON instead of failing safely | Later review/audit led to non-destructive handling plus related integration-hardening fixes | review/audit; exact actor pending | single observation | **unset** |
| CW-516 | [ChainWeaver #516](https://github.com/dgenio/ChainWeaver/pull/516) | Domain/model hardening review found an unsafe mutable-default / duplicate-identity edge in the new batch | Follow-up commit added the relevant fail-fast/model guard and regression coverage | review/audit; exact actor pending | single observation | **unset** |
| CW-462 | [ChainWeaver #462](https://github.com/dgenio/ChainWeaver/pull/462) | LLM proposer budget batching/truncation could still exceed the declared budget | Review response changed the path to fail/raise when the budget cannot be honored and tightened per-batch validation | review/audit; exact actor pending | single observation | **unset** |
| CW-460 | [ChainWeaver #460](https://github.com/dgenio/ChainWeaver/pull/460) | JSONC comment stripping could corrupt ordinary URL strings containing comment-like text | Review led to safer parsing plus regression coverage rather than treating raw substring stripping as valid JSONC handling | review/audit; exact actor pending | single observation | **unset** |
| CW-467 | [ChainWeaver #467](https://github.com/dgenio/ChainWeaver/pull/467) | FlowServer rate-limiter state could grow without a practical bound | Review led to bounded-state handling and associated tests/hardening | review/audit; exact actor pending | single observation | **unset** |
| CW-469 | [ChainWeaver #469](https://github.com/dgenio/ChainWeaver/pull/469) | OpenCode integration metadata could bypass the intended redaction path | Review led to metadata redaction and related contract fixes | review/audit; exact actor pending | single observation | **unset** |
| AF-192 | [AgentFence #192](https://github.com/dgenio/AgentFence/pull/192) | Release publishing could proceed into a bad path when publisher tokens were empty | Maintainer response says the review was addressed; release now fails explicitly on empty publisher tokens | review source pending; maintainer fix response present | single observation | **unset** |
| AF-183 | [AgentFence #183](https://github.com/dgenio/AgentFence/pull/183) | Interactive proxy prompting could fall back to stdin when no controlling terminal existed | Maintainer response: “Good catch”; proxy now requires `/dev/tty` and errors/instructs `--no-interactive` when unavailable | review source pending; maintainer fix response present | single observation | **unset** |
| VG-268 | [VibeGuard #268](https://github.com/dgenio/VibeGuard/pull/268) | Initial docstring suppression skipped any line touching a triple-quoted span, hiding real code such as `os.system("""rm -rf""")` | Review response replaced whole-line skipping with span-content masking and added a regression test for the exact case | review source pending; maintainer fix response present | single observation | **unset** |
| VG-264 | [VibeGuard #264](https://github.com/dgenio/VibeGuard/pull/264) | Ignore-precedence docs/implementation handling could misrepresent `.gitignore` as able to negate hard ignores; ignore-line stripping also broke gitignore semantics | Review response corrected the two-layer precedence model, preserved pathspec whitespace semantics, and added parser tests | review source pending; maintainer fix response present | single observation | **unset** |
| VG-258 | [VibeGuard #258](https://github.com/dgenio/VibeGuard/pull/258) | `changed_files` and `diff_text` could describe different comparisons, leaking full-scan findings in an empty/dirty diff scenario | Review response reproduced the bug, aligned both comparison paths, tightened strict filtering, and added regression tests | review source pending; maintainer fix response present | single observation | **unset** |
| VG-257 | [VibeGuard #257](https://github.com/dgenio/VibeGuard/pull/257) | Error-handling detection mishandled trailing comments and JS log-then-rethrow bodies, creating incorrect findings | Review response addressed all comments, changed body inspection/gating, and added regression tests | review source pending; maintainer fix response present | single observation | **unset** |

## Candidate notes

### CW-537 — release-tag guard checked against the wrong invariant

Why this is high-value for the pilot:

- the implemented “safety” guard looked reasonable in review;
- it failed when compared with **normal everyday repository data**, not only an exotic adversarial case;
- the PR explicitly records the lesson from the fix-review cycle;
- it is a useful test of whether LessonWeaver should recommend durable guidance, a deterministic regression check, a workflow change, or nothing further.

Do not pre-decide that choice here.

### CW-518 — malformed config must not be destructively repaired

Why useful:

- concrete developer-tool integration failure;
- a malformed user-owned config should not be silently overwritten by a setup helper;
- tests can express both positive and negative cases cleanly;
- provides a strong scoping/“when not to act” example.

Eligibility check: identify the exact review comment and whether the correcting reviewer was human or automated.

### CW-516 — model/identity hardening edge

Why useful:

- illustrates a correction that may belong in a deterministic invariant/test rather than prompt guidance;
- useful for testing the full intervention repertoire rather than only instruction/Skill cases.

Before pilot admission, choose one exact principal correction from the PR timeline (prefer the one with the clearest review comment→fix mapping) and drop the other batch observations.

### CW-462 — declared budget must actually be enforceable

Why useful:

- boundary/invariant failure, not style preference;
- likely has strong negative cases around impossible budgets and incomplete tool subsets;
- helps test whether LessonWeaver overuses textual guidance where deterministic enforcement already exists.

### CW-460 — JSONC parsing corrupted URLs

Why useful:

- compact, reproducible parser failure;
- correction comes from review rather than an abstract feature request;
- likely offers strong positive/negative regression cases;
- useful “deterministic check beats instruction?” candidate without assigning the answer up front.

### CW-467 — rate-limiter state growth

Why useful:

- operational/reliability correction;
- tests whether the product can distinguish a one-off implementation defect from a reusable agent instruction;
- negative cases can protect against over-broad “always bound every dict” guidance.

### CW-469 — metadata redaction gap

Why useful:

- security/privacy-adjacent correction;
- output looked governed while a secondary metadata path could escape the redaction rule;
- potentially useful for testing whether evidence supports deterministic invariant enforcement rather than generic “remember to redact” advice.

### AF-192 — empty release credentials must fail explicitly

Why useful:

- maintainer explicitly reports addressing review feedback;
- release path / fail-closed behavior is concrete and testable;
- a candidate where the smallest durable intervention may be different from an agent instruction.

Before pilot admission, fetch and preserve the exact review-thread reference rather than using only the author's response summary.

### AF-183 — no stdin fallback for interactive proxy approval

Why useful:

- strong security/governance boundary;
- maintainer explicitly says “Good catch” and identifies one root cause across two comments;
- clean before/after policy: interactive approval must use a controlling terminal or fail with a safe alternative.

Before pilot admission, preserve the exact review comments that motivated the `/dev/tty` behavior.

### VG-268 — triple-quoted-span masking vs whole-line suppression

Source follow-up is especially clear: the maintainer says the review found a **substantive recall regression** because skipping every line that touched a triple-quoted span hid real executable code such as `os.system("""rm -rf""")`; the fix masks quoted content while leaving surrounding code scannable and adds a regression test.

Why useful:

- unambiguous before/after failure;
- negative/positive cases exist naturally;
- correction is subtle enough that generic “be careful with docstrings” guidance may be worse than a deterministic test;
- useful for measuring whether LessonWeaver chooses `no_change`/test/instruction/Skill appropriately.

### VG-264 — ignore precedence and faithful gitignore parsing

Maintainer response documents two corrected review areas:

- public wording had implied `.gitignore` could re-include a hard-ignored path, but the implementation is a two-layer model where hard ignores win;
- `.strip()` on ignore lines broke gitignore/pathspec whitespace semantics, so lines are now passed through faithfully with tests.

For the one-correction-per-PR pilot rule, prefer the **gitignore-faithfulness parser correction** because it is more concrete; treat the precedence-doc correction as context only.

### VG-258 — diff scope leaked findings because two git comparisons diverged

Maintainer response says the review found a real bug: in a dirty working-tree case `changed_files` came from one fallback comparison while `diff_text` came from another empty comparison, and the empty text then skipped strict filtering, leaking full-scan findings.

The fix aligns the comparison logic and applies the strict filter whenever git context exists, with regressions.

Why useful:

- clear causal chain;
- bug escaped an otherwise comprehensive implementation PR;
- likely a strong deterministic-invariant candidate without pre-labelling it;
- gives the pilot a non-security, operational correctness case.

### VG-257 — error-handling rule review corrected both false positives and false negatives

Maintainer response says all review comments were addressed, including:

- Python `except Exception:  # comment` incorrectly treating comment text as a body;
- JS `console.error(e); throw e` being incorrectly flagged because body inspection did not distinguish log-only from log-then-handle;
- diff-mode gating depending on an implicit scanner invariant.

For one principal correction, use the **JS log-then-rethrow body handling** case because it has crisp positive/negative examples and a direct semantic correction.

## Corpus balance and limitations

Current candidate count: **13 PRs across 3 repositories**.

This satisfies the *quantity/repository-count* target for the #111 pilot candidate pool, but not yet the final eligibility standard.

Important limitations:

- all three repositories are in the same dgenio ecosystem;
- many implementations were AI-assisted by the same maintainer;
- several source review authors are not yet resolved in this file;
- every listed occurrence is currently labelled `single observation` unless recurrence can be established from independent evidence;
- this pool is naturally biased toward issues that produced visible follow-up discussion;
- no candidate has an intervention gold label, intentionally.

The pilot should therefore use this pool to debug evidence import/adjudication and estimate variance, **not** to make a public external-validity claim.

## Next evidence work

Before running the pilot:

1. Use #105 to capture exact repository/PR/commit/review-comment/path/follow-up references for each admitted case.
2. Resolve the correction actor for each case; clearly separate human, automated reviewer, and unclear provenance.
3. Drop candidates that cannot meet the intended GitHub PR-review correction eligibility rules rather than weakening the rules post hoc.
4. Have at least two reviewers independently adjudicate recurrence/evidence sufficiency and acceptable intervention set without seeing LessonWeaver's recommendation.
5. Preserve disagreement.
6. Use the pilot to estimate repeated-run requirements for the confirmatory experiment.
7. Recruit external/non-dgenio cases before the confirmatory/external-replication stage; do not treat this convenience sample as representative of the broader coding-agent ecosystem.

## Non-goals

- No claim that any listed mistake is recurrent yet.
- No assignment of `instruction_patch`, `skill`, `deterministic_check`, or `no_change` here.
- No claim that LessonWeaver would have prevented these mistakes.
- No post-hoc marketing examples.
- No synthetic padding just to reach the target count.
