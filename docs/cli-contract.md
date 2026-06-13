# CLI scripting contract

lessonweaver's CLI is intended to be safe for shell scripts, CI jobs, and agent
automation. This page documents the stable surface for version checks, JSON
output, stdout/stderr handling, and exit codes.

## Global flags

- `--version` prints `lessonweaver <version>` and exits `0`. The value is read
  from installed package metadata, with a source-tree fallback for editable
  development checkouts.

## JSON envelopes

Commands that normally print human-oriented text keep that default output. When
`--json` is passed to the commands below, stdout contains exactly one JSON
document with this envelope:

```json
{
  "command": "detect",
  "result": []
}
```

The `command` field is the invoked subcommand name. The `result` field contains
the command's existing machine-readable payload.

Supported `--json` envelope commands:

- `detect`: list of detected lesson candidates.
- `lint`: list of lint findings.
- `analyze-skills`: list of overlap, duplicate, or contradiction findings.
- `retrieve`: list of retrieval matches.
- `explain-load`: load diagnostics.
- `cleanup-skills`: planned cleanup actions plus the applied skill ids.

With `--json`, diagnostics and errors are written to stderr; stdout is reserved
for the JSON payload so callers can pipe it directly into `json.loads`, `jq`, or
CI parsers.

Existing commands that already emitted raw JSON by default keep that behavior
unless `--json` is explicitly documented for them.

## Exit codes

- `0`: command succeeded.
- `1`: expected negative outcome or missing input, such as a validation suite
  failure, an incomplete review gate, a lint error result, or a missing file.
- `2`: malformed JSON or an invalid trace, candidate, skill, or suite payload.

Exit code meanings are stable for scripting. Commands may add new fields to JSON
objects, but existing envelope keys remain backward compatible before `1.0`.
