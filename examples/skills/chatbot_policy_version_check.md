# Chatbot Policy Version Check

## Description
Verify the active policy version before answering customer policy questions.

## Use when
- Answering policy, refund, billing, or eligibility questions.
- The trace includes policy_version or expected_policy_version metadata.

## Do not use when
- The answer does not depend on policy or procedural content.

## Instructions
- Check the current policy version before giving a definitive answer.
- Escalate when the retrieved policy version conflicts with expected metadata.
- State uncertainty instead of answering from stale policy memory.

## Anti-patterns
- Answering a policy question from cached or remembered rules only.
- Ignoring evaluation feedback that names a newer policy version.

## Evidence
- trace: trace-chatbot-policy-001
