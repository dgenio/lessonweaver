# CLI reference

Generated from the `lessonweaver` argparse command tree. Update it with:

```bash
python scripts/generate_cli_reference.py
```

## Usage

```text
usage: lessonweaver [-h]
                    {detect,import-failure-case,cluster,eval-detection,interview,resume-interview,answer,approve,review-trace,export-skill,export-lesson,export-file,lint,analyze-skills,retrieve,load,explain-load,validate-skill,promote-skill,log-usage,report-stale,cleanup-skills}
                    ...
```

## Subcommands

### `analyze-skills`



```text
usage: lessonweaver analyze-skills [-h] skills_dir
```

| Argument | Help |
| --- | --- |
| `skills_dir` | Required. |

### `answer`



```text
usage: lessonweaver answer [-h] [--free-text FREE_TEXT]
                           [--registry-root REGISTRY_ROOT] [--session SESSION]
                           candidate_id question_id chosen_option_id
```

| Argument | Help |
| --- | --- |
| `candidate_id` | Required. |
| `question_id` | Required. |
| `chosen_option_id` | Required. |
| `--free-text` |  |
| `--registry-root` |  |
| `--session` | Record this answer into a resumable review session at this path |

### `approve`



```text
usage: lessonweaver approve [-h] [--dry-run] [--registry-root REGISTRY_ROOT]
                            [--approved-by APPROVED_BY] [--name NAME]
                            [--lesson-id LESSON_ID] [--skill-id SKILL_ID]
                            [--allow-incomplete-review]
                            candidate_id
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `candidate_id` | Required. |
| `--registry-root` |  |
| `--approved-by` |  |
| `--name` |  |
| `--lesson-id` |  |
| `--skill-id` |  |
| `--allow-incomplete-review` | Override the review gate; records the unanswered questions in metadata |

### `cleanup-skills`



```text
usage: lessonweaver cleanup-skills [-h] [--dry-run]
                                   [--registry-root REGISTRY_ROOT] [--now NOW]
                                   [--write]
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `--registry-root` |  |
| `--now` | ISO 8601 timestamp to evaluate expiry against (default: current time) |
| `--write` | Apply the safe automated subset (deprecate expired skills through the lifecycle) |

### `cluster`



```text
usage: lessonweaver cluster [-h] [--threshold THRESHOLD] [--sanitize]
                            trace_paths [trace_paths ...]
```

| Argument | Help |
| --- | --- |
| `trace_paths` | Required. |
| `--threshold` | Jaccard similarity threshold to group candidates (default: 0.4) |
| `--sanitize` | Scrub sensitive content (secrets and PII) before detection |

### `detect`



```text
usage: lessonweaver detect [-h] [--dry-run] [--output OUTPUT]
                           [--registry-root REGISTRY_ROOT] [--save]
                           [--sanitize]
                           trace_path
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `--output` | Write output to this file instead of stdout |
| `trace_path` | Required. |
| `--registry-root` |  |
| `--save` | Save candidates to the registry |
| `--sanitize` | Scrub sensitive content (secrets and PII) before detection |

### `eval-detection`



```text
usage: lessonweaver eval-detection [-h] [--min-precision MIN_PRECISION]
                                   [--min-recall MIN_RECALL]
                                   [--compare-results COMPARE_RESULTS]
                                   [--with-clustering]
                                   corpus_path
```

| Argument | Help |
| --- | --- |
| `corpus_path` | Required. |
| `--min-precision` | Exit non-zero if precision falls below this floor (CI gate) |
| `--min-recall` | Exit non-zero if recall falls below this floor (CI gate) |
| `--compare-results` | Exit non-zero if the JSON report differs from this recorded results file |
| `--with-clustering` | Report recall with and without clustering repeated weak signals |

### `explain-load`



```text
usage: lessonweaver explain-load [-h] [--registry-root REGISTRY_ROOT]
                                 [--agent-type AGENT_TYPE]
                                 [--tools [TOOLS ...]] [--scope SCOPE]
                                 [--risk-level RISK_LEVEL]
                                 [--budget-chars BUDGET_CHARS]
                                 [--max-skills MAX_SKILLS]
                                 [--inclusion-level {none,name_only,summary,full,full_with_checklist}]
                                 [--include-non-active] [--snippet]
                                 task
```

| Argument | Help |
| --- | --- |
| `task` | Required. |
| `--registry-root` |  |
| `--agent-type` |  |
| `--tools` |  |
| `--scope` |  |
| `--risk-level` |  |
| `--budget-chars` |  |
| `--max-skills` |  |
| `--inclusion-level` |  |
| `--include-non-active` | Also consider non-active skills (otherwise only active skills are eligible) |
| `--snippet` | Include the compiled prompt snippet in the output |

### `export-file`



```text
usage: lessonweaver export-file [-h] [--dry-run] --path PATH
                                [--format {markdown,copilot,copilot-repo,copilot-path,claude,claude-skill,claude-rule,claude-md,agents-md,runtime}]
                                [--applies-to APPLIES_TO]
                                [--redact | --no-redact] [--write]
                                [--registry-root REGISTRY_ROOT]
                                skill
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `skill` | Required. |
| `--path` | Target instruction file to create or update Required. |
| `--format` |  |
| `--applies-to` | Glob for the copilot-path applyTo frontmatter (default: **) |
| `--redact, --no-redact` | Redact rendered output before printing (default: on; pass --no-redact to disable) |
| `--write` | Write the merged file (default: preview the diff only) |
| `--registry-root` |  |

### `export-lesson`



```text
usage: lessonweaver export-lesson [-h] [--dry-run] [--output OUTPUT] --format
                                  {eval,guardrail,workflow}
                                  [--registry-root REGISTRY_ROOT]
                                  [--redact | --no-redact] [--json]
                                  candidate
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `--output` | Write output to this file instead of stdout |
| `candidate` | Required. |
| `--format` | Required. |
| `--registry-root` |  |
| `--redact, --no-redact` | Redact rendered output before printing (default: on; pass --no-redact to disable) |
| `--json` | Wrap output in a {"format": ..., "content": ...} JSON envelope |

### `export-skill`



```text
usage: lessonweaver export-skill [-h] [--dry-run] [--output OUTPUT] [--json]
                                 [--format {markdown,json,copilot,copilot_instruction,copilot-repo,copilot-path,claude,claude_skill,claude-skill,claude-rule,claude-md,agents-md,codex,runtime}]
                                 [--applies-to APPLIES_TO]
                                 [--registry-root REGISTRY_ROOT]
                                 [--redact | --no-redact]
                                 skill
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `--output` | Write output to this file instead of stdout |
| `skill` | Required. |
| `--json` | Wrap output in a {"format": ..., "content": ...} JSON envelope |
| `--format` |  |
| `--applies-to` | Glob for the copilot-path applyTo frontmatter (default: **) |
| `--registry-root` |  |
| `--redact, --no-redact` | Redact rendered output before printing (default: on; pass --no-redact to disable) |

### `import-failure-case`



```text
usage: lessonweaver import-failure-case [-h] [--dry-run] [--output OUTPUT]
                                        [--registry-root REGISTRY_ROOT]
                                        [--save]
                                        artifact_path
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `--output` | Write output to this file instead of stdout |
| `artifact_path` | Required. |
| `--registry-root` |  |
| `--save` | Save candidates to the registry |

### `interview`



```text
usage: lessonweaver interview [-h] [--dry-run] [--registry-root REGISTRY_ROOT]
                              [--session SESSION]
                              candidate
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `candidate` | Required. |
| `--registry-root` |  |
| `--session` | Write a new resumable review session to this path |

### `lint`



```text
usage: lessonweaver lint [-h] [--registry-root REGISTRY_ROOT] skill
```

| Argument | Help |
| --- | --- |
| `skill` | Required. |
| `--registry-root` |  |

### `load`



```text
usage: lessonweaver load [-h] [--registry-root REGISTRY_ROOT]
                         [--agent-type AGENT_TYPE] [--tools [TOOLS ...]]
                         [--scope SCOPE] [--risk-level RISK_LEVEL]
                         [--budget-chars BUDGET_CHARS]
                         [--max-skills MAX_SKILLS]
                         [--inclusion-level {none,name_only,summary,full,full_with_checklist}]
                         [--explain]
                         task
```

| Argument | Help |
| --- | --- |
| `task` | Required. |
| `--registry-root` |  |
| `--agent-type` |  |
| `--tools` |  |
| `--scope` |  |
| `--risk-level` |  |
| `--budget-chars` |  |
| `--max-skills` |  |
| `--inclusion-level` |  |
| `--explain` | Explain which skills loaded or were skipped, with reason codes and budget usage |

### `log-usage`



```text
usage: lessonweaver log-usage [-h] [--skill-version SKILL_VERSION]
                              [--outcome OUTCOME] [--positive | --negative]
                              [--notes NOTES] [--id EVENT_ID]
                              [--registry-root REGISTRY_ROOT]
                              skill_id task_context
```

| Argument | Help |
| --- | --- |
| `skill_id` | Required. |
| `task_context` | Required. |
| `--skill-version` |  |
| `--outcome` |  |
| `--positive` |  |
| `--negative` |  |
| `--notes` |  |
| `--id` |  |
| `--registry-root` |  |

### `promote-skill`



```text
usage: lessonweaver promote-skill [-h] [--registry-root REGISTRY_ROOT]
                                  skill_id
                                  {draft,approved,experimental,active,rejected,deprecated}
```

| Argument | Help |
| --- | --- |
| `skill_id` | Required. |
| `target` | Required. |
| `--registry-root` |  |

### `report-stale`



```text
usage: lessonweaver report-stale [-h] [--registry-root REGISTRY_ROOT]
                                 [--now NOW]
```

| Argument | Help |
| --- | --- |
| `--registry-root` |  |
| `--now` | ISO 8601 timestamp to evaluate expiry against (default: current time) |

### `resume-interview`



```text
usage: lessonweaver resume-interview [-h] [--dry-run]
                                     [--registry-root REGISTRY_ROOT]
                                     session_path
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `session_path` | Required. |
| `--registry-root` |  |

### `retrieve`



```text
usage: lessonweaver retrieve [-h] [--registry-root REGISTRY_ROOT]
                             [--scope SCOPE] [--risk-level RISK_LEVEL]
                             [--max MAX]
                             task
```

| Argument | Help |
| --- | --- |
| `task` | Required. |
| `--registry-root` |  |
| `--scope` |  |
| `--risk-level` |  |
| `--max` |  |

### `review-trace`



```text
usage: lessonweaver review-trace [-h] [--dry-run]
                                 [--registry-root REGISTRY_ROOT]
                                 [--candidate CANDIDATE]
                                 [--answer QUESTION=OPTION]
                                 [--free-text QUESTION=TEXT] [--approve]
                                 [--approved-by APPROVED_BY]
                                 [--allow-incomplete-review] [--target TARGET]
                                 [--applies-to APPLIES_TO]
                                 [--redact | --no-redact] [--sanitize]
                                 trace_path
```

| Argument | Help |
| --- | --- |
| `--dry-run` | Preview the command without writing files or registry entries |
| `trace_path` | Required. |
| `--registry-root` |  |
| `--candidate` | Focus a single detected candidate id (required to answer/approve when a trace yields more than one candidate) |
| `--answer` | Apply an MCQ answer, e.g. --answer decision=approve (repeatable) |
| `--free-text` | Attach reviewer free text to a question, e.g. --free-text scope=team (repeatable) |
| `--approve` | Approve the focused candidate after applying answers (enforces the review gate) |
| `--approved-by` |  |
| `--allow-incomplete-review` |  |
| `--target` | Preview an export of the resulting skill in this format |
| `--applies-to` |  |
| `--redact, --no-redact` | Redact rendered output before printing (default: on; pass --no-redact to disable) |
| `--sanitize` | Scrub sensitive content (secrets and PII) before detection |

### `validate-skill`



```text
usage: lessonweaver validate-skill [-h]
                                   [--skills-dir SKILLS_DIR | --registry-root REGISTRY_ROOT]
                                   suite
```

| Argument | Help |
| --- | --- |
| `suite` | Required. |
| `--skills-dir` | Directory of skill JSON files to validate against (default: registry) |
| `--registry-root` | Registry root containing the skills/ directory (default: ~/.lessonweaver/registry) |
