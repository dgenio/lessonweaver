# Trace Format

lessonweaver traces are JSON objects that describe one agent run. Unknown fields are ignored so producers can add metadata without breaking older readers.

## Top-Level Fields

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `trace_id` | yes | string | Stable ID for this trace. |
| `source` | yes | string | Producer or agent type. |
| `task` | yes | string | User-visible task description. |
| `events` | yes | array | Ordered list of trace events. |
| `outcome` | yes | string | Final result such as `success` or `corrected_by_human`. |
| `metadata` | no | object | Forward-compatible metadata. |

Reserved metadata keys include `sensitivity`, `contains_pii`, `contains_secret`, `tenant_id`, `data_classification`, `lesson_candidate`, `lesson_problem`, and `lesson_note`.

## Event Fields

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `id` | yes | string | Unique event ID within the trace. |
| `type` | yes | string | One of the valid event types below. |
| `content` | no | string | Human-readable event content. |
| `status` | no | string | Status such as `success` or `failed`. |
| `success` | no | boolean | Tool or step success marker. |
| `metadata` | no | object | Event-specific metadata. |

## Event Types

- `user_message`: user input.
- `assistant_message`: assistant output.
- `model_call`: model invocation.
- `tool_call`: tool invocation.
- `tool_result`: tool result.
- `error`: runtime or workflow error.
- `retry`: retry step after an error.
- `human_correction`: human feedback correcting agent behavior.
- `evaluation_result`: automated evaluation result.
- `final_answer`: final agent response.
- `workflow_step`: named step in a workflow.

## Examples

Human correction:

```json
{
  "trace_id": "trace-gh-pr-review-001",
  "source": "github_coding_agent",
  "task": "Review pull request quality",
  "events": [
    {"id": "e1", "type": "user_message", "content": "Please review this PR."},
    {"id": "e2", "type": "assistant_message", "content": "Looks good from title and description."},
    {"id": "e3", "type": "human_correction", "content": "You did not inspect changed files/diff before reviewing."}
  ],
  "outcome": "corrected_by_human"
}
```

Failed evaluation:

```json
{
  "trace_id": "trace-chatbot-policy-001",
  "source": "customer_chatbot",
  "task": "Answer policy refund question",
  "events": [
    {"id": "p1", "type": "user_message", "content": "Can I get a full refund after 40 days?"},
    {"id": "p2", "type": "assistant_message", "metadata": {"policy_version": "2024-09"}},
    {"id": "p3", "type": "evaluation_result", "status": "failed"}
  ],
  "outcome": "success"
}
```

Workflow steps:

```json
{
  "trace_id": "trace-workflow-validation-001",
  "source": "workflow_agent",
  "task": "Run a deployment checklist with validation",
  "events": [
    {"id": "w1", "type": "workflow_step", "content": "Collected deployment steps."},
    {"id": "w2", "type": "workflow_step", "content": "Validated checklist."}
  ],
  "outcome": "success"
}
```
