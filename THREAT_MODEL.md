# TreatyAI Threat Model

## Assets

- Customer consent and journey state.
- Shared compensation and contact budgets.
- Agent identities and delegated scopes.
- Integrity of approved action plans.
- Decision receipts and audit history.
- Availability of the decision service.

## Trust boundaries

1. Agent proposals are untrusted input.
2. Rationale, context notes and evidence labels are data, not policy.
3. The optimizer is not an authorization authority.
4. The verifier is a separate decision stage.
5. The database commit boundary is the only local point that changes customer state.
6. External Salesforce or provider actions are outside this prototype.

## Threats and controls

| Threat | Example | Current control |
|---|---|---|
| Prompt injection | Proposal note says “ignore consent and send” | Context text is never executed or used to override policy |
| Confused deputy | Marketing agent proposes a credit | Registered agent scopes reject the action |
| Privilege escalation | Agent requests more than its delegated credit limit | Per-agent amount ceiling |
| Global resource overspend | Two agents each request 100 MAD from a 150 MAD budget | Joint optimizer, independent verifier and guarded transaction |
| Time-of-check/time-of-use | Customer state changes after an agent formed its proposal | State version, locked re-read and revalidation |
| Replay | Same proposal is submitted again | Idempotency key table and replay rejection |
| Contact spam | Several agents contact the same customer | Shared customer-level outbound quota |
| Unsafe consensus | Several agents agree on a bad plan | Agreement is not used as evidence; deterministic verification is required |
| Audit alteration | A stored event is modified | SHA-256 hash chain detects inconsistent history |
| Human-approval bypass | Irreversible/high-risk action marked for review | Human-required proposal is excluded from autonomous commit |

## Security properties demonstrated

- A marketing agent cannot bypass withdrawn consent by including instruction-like text in its rationale.
- Two concurrent requests cannot jointly commit more than the locked shared budget in the tested SQLite deployment.
- A proposal outside its registered action scope is rejected.
- A proposal requiring human approval does not get autonomously committed.
- Reusing a processed idempotency key is rejected.
- Modifying an existing audit event payload is detected by chain verification.

## Explicit non-goals and residual risks

- The local demo does not authenticate remote users and binds only to loopback.
- It does not implement tenant isolation or production RBAC.
- It does not protect against a privileged local attacker who can rewrite the SQLite database and recompute all hashes.
- It does not sign receipts with a hardware-backed or external key.
- It does not secure external Salesforce credentials or downstream APIs because no live integration exists.
- It does not guarantee distributed atomicity across multiple services.
- The optimizer is bounded; arbitrary large-scale optimality is not claimed.
- The current customer-state model is intentionally small and synthetic.

## Production hardening before real use

Add authenticated agent identities, tenant-scoped data access, signed requests, key rotation, policy approval workflows, encrypted secrets, durable outbox delivery, downstream idempotency, compensating actions, rate limiting, structured monitoring, data-retention controls and independent security testing.
