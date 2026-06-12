# LangSmith Import

`LangSmithTraceImporter` maps exported LangSmith run data into the lessonweaver
trace schema without importing the LangSmith SDK or calling the LangSmith API.

LangSmith [bulk data export](https://docs.langchain.com/langsmith/data-export)
writes trace data matching the documented
[run/span data format](https://docs.langchain.com/langsmith/run-data-format).
The importer consumes those run records plus optional feedback records and
preserves unmapped run fields under metadata.

## Supported Shape

Use a JSON object with `runs` and optional `feedback`:

```json
{
  "source": "langsmith",
  "runs": [
    {
      "id": "run-root",
      "trace_id": "trace-1",
      "name": "Refund agent",
      "run_type": "chain",
      "inputs": {},
      "outputs": {},
      "status": "success"
    },
    {
      "id": "run-tool",
      "trace_id": "trace-1",
      "run_type": "tool",
      "error": "Tool used stale policy.",
      "status": "error"
    }
  ],
  "feedback": [
    {"run_id": "run-root", "key": "human_review", "score": 0, "comment": "Check current policy."}
  ]
}
```

## Convert, Detect, Review

```python
import json
from pathlib import Path
from lessonweaver import LangSmithTraceImporter

payload = json.loads(Path("langsmith-runs.json").read_text())
bundle = LangSmithTraceImporter().import_trace(payload)
Path("lessonweaver-trace.json").write_text(json.dumps(bundle.to_dict(), indent=2))
```

```bash
lessonweaver detect lessonweaver-trace.json --sanitize --save --registry-root .lessonweaver
lessonweaver interview <candidate-id> --registry-root .lessonweaver
```

Run errors become `error` events. Feedback comments become `human_correction`
events, and failing feedback scores become failed `evaluation_result` events.
