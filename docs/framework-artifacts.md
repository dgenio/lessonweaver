# Framework Artifacts

Reviewed candidates can be rendered as framework-targeted JSON artifacts with
`export_framework_artifact(candidate, framework=...)`. The exporter chooses the
artifact type from the reviewed candidate's `recommended_action_type`, with
`metadata["failure_mode"] = "handoff"` or `"routing"` producing a handoff rule
for workflow-change candidates.

Every artifact includes governance metadata: scope, owner, approver, status,
risk, confidence, evidence trace/event ids, expiry, review metadata, and a
default `does_not_apply_when` condition.

## OpenAI Agents SDK

Use prompt lessons for instruction fragments and guardrails for input/output
checks:

```python
artifact = export_framework_artifact(candidate, framework="openai-agents")
```

## LlamaIndex

Use retrieval-rule artifacts to describe when a lesson should influence
retrieval or response synthesis:

```python
artifact = export_framework_artifact(candidate, framework="llamaindex")
```

## LangChain and LangGraph

Use workflow-change artifacts for node updates and handoff-rule artifacts for
routing failures:

```python
candidate.metadata["failure_mode"] = "handoff"
artifact = export_framework_artifact(candidate, framework="langgraph")
```

## Generic Runtime JSON

Use `framework="generic"` for dashboards, deployment manifests, or custom agent
runtimes:

```python
artifact = export_framework_artifact(candidate)
```

The output is advisory and review-derived. It must not auto-inject unreviewed
instructions into a runtime.
