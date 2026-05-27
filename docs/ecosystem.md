# Ecosystem Positioning

This page describes how lessonweaver relates to adjacent tools and standards.
It is factual, not promotional: each entry states what lessonweaver **can** do
in that relationship and what it does **not** do or replace.

lessonweaver is an offline, deterministic loop that turns reviewed trace
evidence into governed, reusable operational guidance. It does not orchestrate
agents, run models, or inject anything without human review.

For category-level boundaries (observability vs. evals vs. memory vs.
frameworks), see [comparisons](comparisons.md).

## AGENTS.md

- **Can:** Export reviewed skill content as Markdown that a maintainer can paste
  into `AGENTS.md` (today via the `markdown` or `runtime` export formats).
- **Does not:** Parse, manage, or auto-write `AGENTS.md` files. A dedicated
  `agents-md` export format is planned
  ([#48](https://github.com/dgenio/lessonweaver/issues/48)).

## GitHub Copilot custom instructions

- **Can:** Export Copilot-compatible instruction fragments via
  `export-skill --format copilot`.
- **Does not:** Manage `.github/copilot-instructions.md` or
  `.github/instructions/` for you, and does not commit instructions
  automatically. You review the fragment and decide where it goes.

## Claude Code (CLAUDE.md, .claude/rules/, SKILL.md)

- **Can:** Export Claude-style skill fragments via
  `export-skill --format claude`.
- **Does not:** Replace Claude Code's native configuration, install skills, or
  integrate with Claude Code hooks. Output formats may evolve.

## OpenAI Agents SDK / Codex

- **Can:** Produce reviewed skill content that can be injected into agent
  instructions before a run. A `codex_directory` export format is reserved in
  the `ExportFormat` enum.
- **Does not:** Manage agent configuration, SDK setup, or hosted Agent Builder.
  A runnable adapter example is planned
  ([#21](https://github.com/dgenio/lessonweaver/issues/21)).

## LlamaIndex applications

- **Can:** Produce runtime prompt snippets (`export-skill --format runtime`, or
  `SkillLoader.load_for_task`) for injection into a system prompt before an
  agent/chat-engine call.
- **Does not:** Integrate with LlamaIndex retrieval pipelines or add a LlamaIndex
  dependency. A runnable adapter example is planned
  ([#20](https://github.com/dgenio/lessonweaver/issues/20)).

## Pipecat voice agents

- **Can:** Mine post-call transcripts (any tool that emits the documented
  [trace format](trace-format.md)) into lesson candidates, and produce short
  snippets suitable for latency-sensitive contexts.
- **Does not:** Replace Pipecat's pipeline or real-time features, and adds no
  Pipecat dependency. Voice integration docs are planned
  ([#22](https://github.com/dgenio/lessonweaver/issues/22)).

## Evals frameworks (Braintrust, promptfoo, etc.)

- **Can:** Recommend eval specs and guardrail rules as an action type for a
  reviewed lesson. Dedicated eval/guardrail exporters are planned
  ([#47](https://github.com/dgenio/lessonweaver/issues/47)).
- **Does not:** Run evals, score model output, or integrate with an eval
  runner. lessonweaver complements evals; it does not execute them.

## Observability / tracing tools

- **Can:** Consume traces these tools already produce, once normalized into the
  documented trace format.
- **Does not:** Record, store, or visualize live telemetry. Observability tells
  you *what happened*; lessonweaver turns reviewed evidence into *guidance*.

## Sibling repository tools

- **Can:** Consume structured findings from sibling tools (for example a
  repository checker such as `dgenio/vibeguard`) when their output is mapped to
  the trace format. See [interoperability](interoperability.md).
- **Does not:** Take a hard dependency on any specific sibling tool. All such
  integrations are optional and live in `examples/` or docs, never in core.
