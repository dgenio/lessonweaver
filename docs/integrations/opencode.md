# OpenCode Integration

lessonweaver can normalize OpenCode plugin/tool event payloads into the
standard trace format, then run the same governed loop as any other trace:

```bash
lessonweaver import-opencode opencode-trace.json --save --registry-root .lessonweaver
lessonweaver interview <candidate-id> --registry-root .lessonweaver
lessonweaver approve <candidate-id> --approved-by reviewer --registry-root .lessonweaver
lessonweaver export-skill skill-<candidate-id> --format agents-md --redact \
  --registry-root .lessonweaver
```

`OpenCodeTraceImporter` is dependency-free. It recognizes payloads with
`source: "opencode"` or an OpenCode schema marker and an ordered `events` list:

```json
{
  "source": "opencode",
  "session_id": "oc-session-1",
  "task": "Review a pull request",
  "events": [
    {"type": "user", "message": "Please review PR #42"},
    {"type": "tool_call", "tool": "git.diff", "input": {"path": "src/app.py"}},
    {"type": "tool_result", "tool": "git.diff", "success": false, "output": "No diff read"},
    {"type": "correction", "message": "Inspect the diff before approving."}
  ]
}
```

The importer maps user/assistant messages, tool calls/results, errors, and
human corrections to lessonweaver events. Unknown fields are preserved under
metadata so reviewers can trace candidates back to the OpenCode payload.
Sensitive event content is redacted by default with `TraceSanitizer`.

OpenCode exports should start with reviewed `AGENTS.md` fragments or runtime
snippets. lessonweaver does not auto-inject unreviewed instructions into
OpenCode sessions.
