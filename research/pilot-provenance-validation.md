# LessonWeaver pilot provenance validation

Status: **provenance audit of the raw candidate pool**, not gold adjudication.

This note corrects an important possible misreading of `research/pilot-corpus-candidates.md`: the 13 entries there are a **raw evidence pool**, not 13 cases that already satisfy #105's strict human-PR-correction beachhead.

The first follow-up audit inspected review timelines for representative candidates and nearby external-contributor PRs. It confirms that the pilot needs explicit provenance strata rather than a binary "real/synthetic" label.

## Provenance strata

### A — strict human-review correction

Use for the intended #105/#111 human-correction beachhead only when all are evidenced:

1. the changed code was produced or materially implemented by a coding agent;
2. a human reviewer raised the concrete correction in GitHub PR review/comment history;
3. a later commit/change addressed that correction;
4. exact repository, PR, review-comment, commit, path, and follow-up references are preserved.

This is the preferred stratum for the confirmatory corpus.

### B — automated-review correction

The PR is agent-assisted and an automated reviewer (for example Copilot or Codex) raised the concrete defect; a subsequent change addressed it.

These are valuable **pilot methodology** cases because the before→review→fix evidence is real and reproducible, but they must not be represented as human corrections.

### C — self-audit / re-audit correction

A maintainer/agent re-audited its own PR and found/fixed a concrete defect without a prior independent review comment containing the correction.

Useful for importer/adjudication mechanics and for testing intervention taxonomy; not evidence that #105's human-review source path is already available historically.

### D — supporting recurrence/lesson evidence only

The PR documents or formalizes a recurring pitfall, but the reviewed PR itself is not the original correction sequence.

Useful as supporting recurrence evidence only. It must not be counted as a primary correction case unless the original PR/review event is linked separately.

## Audited examples

| Source | Provenance result | Evidence |
| --- | --- | --- |
| ChainWeaver #537 | **D — supporting evidence only** | The inspected PR review timeline contains a Copilot overview with no concrete review correction. The PR is useful as a recorded lesson about a prior release-tag-guard mistake, but the original correction event must be located before it can become a primary case. |
| ChainWeaver #518 malformed-config overwrite | **C — self/re-audit** | The destructive malformed-config behavior was reported in a later `dgenio` issue comment as a "fresh audit of the previous head" and then fixed. This is strong real defect evidence, but the audited event is not a human reviewer comment that preceded the fix. |
| AgentFence #183 `/dev/tty` fallback | **B — automated review** | Copilot review comments identified that proxy approval could fall back to JSON-RPC stdin. A later `dgenio` response says "Good catch" and records the strict `/dev/tty` fix plus tests. The correction source is Copilot, not a human reviewer. |
| VibeGuard #268 triple-quoted-span recall regression | **B — automated review** | Copilot review explicitly identified that whole-line skipping hid executable patterns such as `os.system("""rm -rf /tmp""")`. A later `dgenio` response records span masking plus an exact regression test. The correction source is Copilot. |
| LessonWeaver #244 external contributor | **B — automated review** | External contributor work was corrected after a Codex review about propagating failed Claude `tool_result` status to the corresponding tool call. The contributor fixed it and added coverage, but the correction source is Codex. |
| LessonWeaver #250 external contributor | **B — automated review** | External contributor work was corrected after Codex identified over-broad migration of underscore-prefixed provenance metadata. The contributor narrowed migration to known keys and added regression coverage. Correction source is Codex. |
| LessonWeaver #239 external contributor | **human review present; agent-authorship unproven** | `dgenio` added human-account review comments identifying incorrect `ValueError` handling and missing symmetric coverage. The PR author is external (`wyf027`). This is **not yet A** because the available evidence inspected so far does not establish that the implementation itself was coding-agent-authored. Preserve it as a human-review lead rather than assuming agent authorship. |

## Correction to the raw pool count

The merged raw file contains 13 PR candidates across three repositories. After this provenance audit:

- **do not say "13 human correction cases"**;
- CW-537 should not count as a primary correction sequence until the original event is found;
- several high-quality cases are clearly **B** or **C** rather than **A**;
- the currently audited history does **not yet establish enough stratum-A cases for a confirmatory human-correction corpus**.

That is a useful finding. It means the experiment must recruit or capture the missing evidence rather than relaxing the definition after the fact.

## Pilot use

The methodology-calibration pilot may use strata B and C if each run is labelled explicitly. They are useful for testing:

- #105 evidence normalization/provenance shape;
- proposal construction;
- intervention taxonomy;
- positive/negative evaluation case generation;
- ablation harness;
- run variance and reviewer-time instrumentation.

When reporting pilot results, stratify by correction source and never pool B/C into a headline "human review" effect.

Stratum D can support recurrence/context but should not be treated as the index correction.

## Confirmatory requirement

The confirmatory product test should prefer stratum A.

If historical public data cannot supply enough A cases, use a **prospective capture/recruitment phase** rather than weakening #105:

1. recruit unrelated maintainers/teams already using coding agents;
2. capture a real PR correction at the time it occurs;
3. preserve the agent-authorship evidence and exact human review event;
4. wait for follow-up/recurrence evidence where required;
5. keep the case hidden from LessonWeaver recommendation generation until independent gold adjudication is complete.

This prospective recruitment can also become the bridge to the later external-replication gate.

## Gold labels remain unset

None of the provenance classification above selects the durable intervention.

Do not infer:

- `instruction_patch` from a review comment;
- `deterministic_check` just because a regression test was added;
- `skill` because a mistake sounds reusable;
- recurrence from a single corrected PR.

Intervention and recurrence labels remain subject to the independent adjudication rules in #111 / `docs/product-experiment.md`.

## Next actions

1. Add `correction_source` / provenance-stratum fields to the eventual #105 evidence representation or experiment manifest; do not bury this distinction in free text.
2. Continue resolving exact review-comment/commit/path provenance for raw candidates that remain useful.
3. Search for the original correction behind CW-537 before using it as a primary case.
4. Use B/C cases for pilot mechanics only when labelled.
5. Recruit prospective A cases before freezing the confirmatory corpus if historical A evidence remains insufficient.

## Non-claims

This audit does not establish that automated reviews are worse or less useful than human reviews. It only protects the causal/product question from silently changing from "human correction" to "any reviewer signal" because automated history is easier to obtain.