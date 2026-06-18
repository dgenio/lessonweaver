# Langfuse Import

`LangfuseTraceImporter` maps exported Langfuse JSON into the lessonweaver trace
schema without importing the Langfuse SDK or calling the Langfuse API.

Langfuse supports JSON export from the UI and scheduled blob-storage exports.
The [UI export docs](https://langfuse.com/docs/api-and-data-platform/features/export-from-ui)
and [blob export docs](https://langfuse.com/docs/api-and-data-platform/features/export-to-blob-storage)
describe trace, observation, enriched observation, and score rows; lessonweaver
preserves unmapped fields under metadata rather than guessing.

## Supported Shape

Use a JSON object with a trace plus its observations and scores:

```json
{
  "source": "langfuse",
  "trace": {"id": "trace-1", "name": "Handle refund request"},
  "observations": [
    {"id": "obs-1", "type": "GENERATION", "input": {}, "output": {}},
    {"id": "obs-2", "type": "SPAN", "level": "ERROR", "status_message": "Tool failed"}
  ],
  "scores": [
    {"name": "human_review", "value": 0, "comment": "Reviewer corrected the answer."}
  ]
}
```

## Convert, Detect, Review

```python
import json
from pathlib import Path
from lessonweaver import LangfuseTraceImporter

payload = json.loads(Path("langfuse-export.json").read_text())
bundle = LangfuseTraceImporter().import_trace(payload)
Path("lessonweaver-trace.json").write_text(json.dumps(bundle.to_dict(), indent=2))
```

```bash
lessonweaver detect lessonweaver-trace.json --sanitize --save --registry-root .lessonweaver
lessonweaver interview <candidate-id> --registry-root .lessonweaver
```

Feedback comments become `human_correction` events, and failed/zero scores
become failed `evaluation_result` events so normal detection can mine them.
