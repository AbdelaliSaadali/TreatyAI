# TreatyAI Architecture

## 1. System boundary

TreatyAI sits between autonomous business agents and the business systems that execute their proposed actions.

    Agentforce / agent framework (future adapter)
            |
            | Decision Contract
            v
    Integration Gateway (local FastAPI API)
            |
            v
    Decision Engine
      ├── Identity & delegated authority
      ├── Conflict graph
      ├── Deterministic policy checks
      ├── Constrained plan optimizer
      └── Independent verifier
            |
            v
    Transactional execution boundary
      ├── State-version revalidation
      ├── Idempotency check
      ├── Atomic shared-resource update
      └── Decision receipt
            |
            v
    SQLite state + hash-linked audit events

The browser dashboard is a read/control client for the local simulation. It does not make authorization decisions.

## 2. Decision Contract

Each proposal contains:

- Proposal and idempotency identifiers.
- Agent identity and customer identity.
- Typed action and bounded action parameters.
- Priority and utility score.
- Whether partial resolution is permitted.
- Reversibility and human-approval flags.
- Proposal timestamp and optional expiry.
- Expected customer-state version.
- Evidence references and a bounded rationale/context note.

Unknown fields are rejected by Pydantic. Identifiers have a restricted character set. Monetary amounts and text fields are bounded.

Rationale and context are treated as untrusted data. They are never evaluated as executable policy.

## 3. Decision lifecycle

### Prepare

The API validates the contracts, reads the customer snapshot and constructs the conflict graph. The persistence layer then starts a SQLite BEGIN IMMEDIATE transaction and re-reads the customer row under the write lock.

### Analyze

The policy engine checks:

- Registered agent identity.
- Delegated action scope.
- Per-agent monetary limit.
- Customer marketing consent.
- Open critical case.
- Customer-wide outbound contact allowance.
- Human approval requirements.

The conflict graph adds relationships for shared compensation, journey precedence and contact-frequency contention.

### Resolve

The bounded optimizer explores compatible action variants. Credit proposals may offer a reduced amount only when allow_partial is true. Hard constraints are applied before utility is considered.

The current objective maximizes the sum of proposal utility after partial-resolution penalties. It is a demonstration objective, not a learned preference model.

### Verify

A separate function re-evaluates the selected plan against the customer snapshot. It does not trust the optimizer's rationale. The verifier checks delegated authority, cumulative budget, outbound quota, consent/journey rules and unique execution keys.

### Commit

Within the same SQLite write transaction, the system:

1. Rejects previously processed idempotency keys.
2. Re-evaluates proposals against the latest locked customer state.
3. Records stale proposal versions that were revalidated.
4. Rechecks the global plan.
5. Performs a guarded update using the current state version, remaining budget and contact quota.
6. Stores the decision, receipt and audit events.
7. Records idempotency results.

If any guarded update fails, the transaction rolls back.

This is a single-database transaction. A production connector would require an outbox, downstream idempotency and compensating workflows for external side effects.

## 4. Concurrency model

SQLite BEGIN IMMEDIATE serializes write transactions. Each request re-reads the shared customer state after acquiring the write lock. The final SQL update also includes guards for:

- The exact state version observed.
- Sufficient remaining compensation.
- Available contact capacity.

The concurrency test launches two separate worker threads. Both propose 100 MAD against one 150 MAD allowance. The first transaction can commit 100 MAD; the second is re-evaluated against the remaining 50 MAD and can only commit a permitted partial amount. The aggregate must never exceed 150 MAD.

This demonstrates correctness for the local SQLite boundary, not distributed concurrency across multiple services or database clusters.

## 5. Decision receipt and audit chain

A receipt records:

- Decision and scenario identifiers.
- Customer identifier.
- Policy and engine versions.
- State version before and after commit.
- Stale proposals revalidated.
- Verification checks.
- Action outcomes and compensation total.
- Timestamp and previous event hash.

Each audit event stores the previous event hash and a SHA-256 digest over the previous hash, event type, canonical payload and timestamp. GET /api/audit/verify recomputes the chain.

The chain is tamper-evident, not tamper-proof. Production use should add key-backed signatures and independent external anchoring.

## 6. Persistence

SQLite is used to keep the demo lightweight and self-contained. The database is created at data/treatyai.sqlite3. No database server, Docker image or external service is required.

Tables:

- customers
- decisions
- events
- idempotency
- benchmarks

The demo data is synthetic. Reset demo changes customer state but intentionally preserves the audit history.

## 7. Optimizer

The current optimizer uses bounded beam search over a small set of candidate variants for each proposal. It prunes plans that exceed the shared compensation allowance or contact capacity.

For the hackathon use case, this keeps the implementation understandable and fast. For a PFE extension, compare it with CP-SAT/SMT formulations, prove soundness properties, measure approximation quality, and benchmark larger proposal sets.

## 8. Integration boundary

The generic POST /api/decisions/coordinate endpoint accepts a DecisionBatch containing one customer identifier and 1–20 validated agent proposals. This is the integration boundary for a future Salesforce adapter: an Agentforce action can submit its proposal batch, then consume the verified decision and receipt. This repository currently has no Salesforce credentials or live adapter. No external action is sent from the prototype.
