# Eval companion

lessonweaver complements eval systems. It mines real traces and reviewed
decisions into artifacts that an eval framework, guardrail system, or workflow
backlog can consume; it does not execute evals or score model output.

Use `export_eval_companion_pack` when you want a coherent bundle of reviewed
non-skill candidates:

```python
from lessonweaver import export_eval_companion_pack

pack = export_eval_companion_pack(reviewed_candidates)
```

The pack contains:

- `evals/*.md` for `RecommendedActionType.EVAL`;
- `guardrails/*.md` for `RecommendedActionType.GUARDRAIL`;
- `workflows/*.md` for `RecommendedActionType.WORKFLOW_CHANGE`;
- `metadata.json` with candidate id, action type, review status, approver,
  risk, scope, confidence, evidence trace ids, and evidence event ids;
- a README that keeps the runner boundary explicit.

Only approved candidates can be exported. Skill candidates remain runtime
guidance and should use the skill exporters instead.
