# TreatyAI

**Cross-Agent Decision Governance & Verified Execution**

> Many agents. One governed outcome.

TreatyAI is a local proof of concept for governing business decisions proposed by multiple autonomous agents. Instead of trusting each agent in isolation, it evaluates the combined impact of their actions, enforces customer-wide business invariants, searches for a feasible resolution, independently verifies that resolution, and commits it through a serialized execution boundary.

It is designed as a governance layer that can complement an orchestrator such as Salesforce Agentforce. It is not another general-purpose agent orchestration framework.

## What is implemented

- **Decision Contracts** — validated, bounded action proposals with agent identity, delegated action, customer, amount, priority, evidence, idempotency key and expected customer-state version.
- **Conflict Graph** — pairwise relationships for shared compensation budgets, customer-journey precedence and outbound contact contention.
- **Deterministic Policy Engine** — delegated scopes, per-agent monetary limits, customer consent, critical-case precedence, contact-frequency limits and human-approval boundaries.
- **Constrained Resolution** — bounded beam search over full and partial action variants. Hard constraints are never traded for utility.
- **Independent Verifier** — recomputes authority, budget, consent, contact and idempotency checks from the selected plan.
- **Transactional Commit** — SQLite BEGIN IMMEDIATE, guarded state updates, state-version checks and re-evaluation of stale proposals.
- **Idempotency Protection** — processed proposal keys are recorded and replays are rejected.
- **Decision Receipts** — evidence-linked outcomes, policy/engine versions, verification results and SHA-256 receipt hashes.
- **Hash-Linked Audit Events** — append-only event records with a verifiable SHA-256 chain.
- **TreatyBench** — reproducible synthetic cases comparing independent per-action approval with global decision coordination.
- **Concurrency Demonstration** — two simultaneous compensation proposals contend for one shared budget.

## Honest scope boundary

This prototype is fully functional as a **local deterministic simulation**. The decision engine, optimizer, verifier, SQLite transaction, audit records, benchmark and dashboard run for real.

The following are simulated or future integration work:

- The four business agents are deterministic proposal generators, not autonomous LLMs.
- Customer records, cases, campaign events and budgets are synthetic.
- There is no live Salesforce org, Agentforce connection, Marketing Cloud connection or external action dispatch.
- No LLM API key is needed. No model is downloaded.
- A future Salesforce adapter can call the documented HTTP contracts, but a native Agentforce action has not yet been configured or tested.

This separation is intentional: the core safety mechanism is testable without a Salesforce account or external credentials.

## Quick start

Requirements: Python 3.10+, and the packages in requirements.txt.

    cd ~/Desktop/Projects/TreatyAI
    ./run.sh

Open:

- App: http://127.0.0.1:8765
- API reference: http://127.0.0.1:8765/api/docs
- Health: http://127.0.0.1:8765/api/health

The server binds to 127.0.0.1 only. It is not exposed to the local network.

If the Python packages are not already available:

    python3 -m pip install -r requirements.txt

The project uses the existing Python environment to avoid duplicating large dependencies in a new virtual environment. For isolated or production deployment, use a dedicated environment and pinned dependency lock.

To use a different port:

    TREATYAI_PORT=8766 ./run.sh

Stop the server with Ctrl+C.

## Recommended demonstration

1. Open **Decision room**.
2. Select **Customer journey conflict**.
3. Click **Run coordination**.
4. Inspect the conflict graph: two credits compete for a shared 150 MAD allowance, while marketing conflicts with an open critical case.
5. Inspect the outcome: the service proposal receives 100 MAD, retention is adjusted to 50 MAD, and marketing is deferred.
6. Inspect the independent verifier and the generated decision receipt.
7. Click **Run concurrency test**. Two 100 MAD proposals are submitted concurrently against one 150 MAD budget. The second request is re-evaluated against the latest state; the combined committed amount must remain at or below 150 MAD.
8. Open **TreatyBench** and run the 30-case synthetic benchmark.
9. Open **Decision receipts** and verify the audit chain.

Use **Reset demo** before repeating the flagship scenario. Reset restores the synthetic customer state but deliberately preserves the historical decision and audit records.

## API surface

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/health | Runtime and local storage health |
| GET | /api/overview | Customer snapshots, counters and audit status |
| GET | /api/agents | Registered simulated agent identities |
| GET | /api/policies | Versioned policy registry |
| GET | /api/scenarios | Available synthetic scenarios |
| POST | /api/scenarios/{id}/run | Prepare, verify and commit a scenario |
| POST | /api/demo/reset | Restore demo customer state |
| POST | /api/concurrency/run | Run the simultaneous shared-budget test |
| POST | /api/bench/run | Execute 30 TreatyBench cases |
| GET | /api/bench/latest | Retrieve the latest benchmark |
| GET | /api/decisions | List decision records |
| GET | /api/decisions/{id} | Retrieve a complete decision |
| GET | /api/receipts | List decision receipts |
| GET | /api/events | Read audit events and integrity status |
| GET | /api/audit/verify | Verify the event hash chain |

FastAPI's OpenAPI UI is available at /api/docs.

## Run the tests

    python3 -m unittest discover -s tests -v

The test suite covers:

- Global budget enforcement and partial resolution.
- Critical-case precedence.
- Withdrawn consent and instruction-like prompt content.
- Delegated agent scope.
- Human-approval boundaries.
- Benchmark invariant checks.
- Idempotency replay rejection.
- Concurrent shared-budget commits.
- Audit-chain verification and tamper detection.

## Project layout

    TreatyAI/
    ├── main.py                 # FastAPI routes and local orchestration
    ├── models.py               # Decision Contract schema and validation
    ├── engine.py               # Conflict graph, policy checks, optimizer, verifier, benchmark
    ├── db.py                   # SQLite persistence, transaction boundary, receipts and audit chain
    ├── static/
    │   ├── index.html          # Single-page application shell
    │   ├── styles.css          # Responsive dashboard styling
    │   └── app.js              # Browser interactions and API client
    ├── tests/
    │   └── test_engine.py      # Engine, persistence and concurrency tests
    ├── data/                   # Local SQLite database (git-ignored)
    ├── requirements.txt
    ├── run.sh
    ├── ARCHITECTURE.md
    ├── THREAT_MODEL.md
    └── DEMO_SCRIPT.md

## Design principles

1. **Models propose; code disposes.** Agent explanations never authorize an action.
2. **Global constraints beat local utility.** A locally valid action can be rejected if the combined plan is invalid.
3. **No agreement-as-proof.** The optimizer proposes a plan; a separate verifier checks it.
4. **Re-read before commit.** Plans are recomputed against the latest locked customer state.
5. **Make replay safe.** Every proposal has an idempotency key.
6. **Explain every outcome.** Rejections, deferrals and adjustments have reason codes and evidence references.
7. **Measure safe completion, not just blocking.** A system that rejects every action is not useful.

## Important limitations

- The beam-search optimizer is bounded and is not a proof of global optimality for arbitrary large action sets.
- The SQLite transaction demonstrates single-database serialization. It is not a distributed transaction across Salesforce and external providers.
- Hash chaining makes accidental or unsophisticated modification detectable; it is not a digital signature or protection against an attacker who can rewrite the database and recompute the chain.
- The current benchmark validates the encoded synthetic scenarios, not production performance or arbitrary agent systems.
- The demo does not provide tenant isolation, production authentication, secrets management, external action dispatch, or operational monitoring.

## Roadmap

- Salesforce Agentforce action adapter and a real Developer Org integration.
- Policy-as-code integration (for example, OPA/Rego) with reviewed policy bundles.
- Stronger optimization and formal constraint modeling.
- Outbox pattern and compensating workflows for external side effects.
- Signed receipts, key rotation and external audit anchoring.
- Broader TreatyBench datasets, mutation tests and baseline comparisons.
- Multi-tenant identity, RBAC and production deployment controls.

---

**TreatyAI is a research-oriented engineering prototype. It should not be connected to production customer data or allowed to execute real financial or marketing actions.**
