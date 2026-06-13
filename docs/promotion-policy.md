# Policy-gated promotion

lessonweaver can evaluate whether a reviewed `SkillCard` is eligible for a
governed promotion, but the policy is deliberately narrow. It is a deterministic
gate for low-risk cases, not autonomous self-training.

Use `PromotionPolicy` and `evaluate_promotion` when an automation wants to
recommend or stage a promotion:

```python
from lessonweaver import PromotionPolicy, evaluate_promotion

decision = evaluate_promotion(skill, PromotionPolicy())
print(decision.to_dict())
```

By default, automatic promotion is only permitted when all of these inputs stay
inside the low-risk envelope:

- confidence meets the configured threshold;
- enough evidence traces support the skill;
- risk is low;
- scope is user, project, or team;
- sensitivity is not confidential or restricted;
- action type is `skill`;
- no conflicting lessons are known;
- the target is not `active` unless the policy explicitly permits activation.

The default call is a dry run. It returns a `PromotionDecision` with:

- `allowed` and `requires_human_review`;
- target status and rollback status;
- a human-readable reason;
- audit entries explaining the policy inputs;
- the skill id and dry-run flag.

Dry-run decisions do not mutate the skill. To apply an allowed non-dry-run
decision, call `apply_promotion_decision`; it uses the existing governed
lifecycle transition and records `promotion_decision` plus
`promotion_rollback_status` in skill metadata.

## Human review requirements

The policy forces human review for high-risk, global or organization-wide,
security-sensitive, conflicting, low-confidence, under-evidenced, or disallowed
action-type promotions. Promotion to `active` also requires explicit policy
permission, then still runs the normal lifecycle and lint checks.

## Reversibility

Every decision carries the previous status as `rollback_status`. Applied
promotions store that value in metadata so an operator can deprecate, roll back,
or re-review the skill using the same governed lifecycle instead of silently
changing runtime guidance.
