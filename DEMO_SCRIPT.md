# TreatyAI Demo Script

Target length: 4–5 minutes. Use synthetic records only.

## Opening

“Enterprise agents are usually evaluated one at a time. But real business risk appears when their actions interact. Two agents can each stay within their own limit and still violate a customer-wide budget together. TreatyAI governs the combined decision.”

## Scene 1 — The conflict

Open **Decision room** and select **Customer journey conflict**.

“Three agents are acting on one customer. Service proposes 100 MAD compensation. Retention proposes another 100 MAD. Marketing wants to send a promotion while a critical complaint is open. The customer has only 150 MAD remaining.”

Run coordination.

## Scene 2 — The conflict graph

Point to the graph.

“TreatyAI does not ask the agents to vote. It models shared resources and dependencies. The credit proposals share one global budget. Marketing is subject to a customer-journey precedence rule.”

## Scene 3 — Resolution

Point to the outcomes.

“The service action receives 100 MAD. Retention is negotiated down to 50 MAD because partial compensation is allowed. Marketing is deferred until the complaint is resolved. The optimizer finds a feasible plan, but it does not authorize itself.”

## Scene 4 — Independent verification

Point to the verifier.

“A separate verifier rechecks delegated authority, the global budget, contact limits, consent and idempotency. Only after those checks pass can the local transaction commit.”

## Scene 5 — Concurrency

Click **Run concurrency test**.

“Now the harder case: two requests arrive at the same time. Each asks for 100 MAD, but only 150 MAD exists. TreatyAI serializes the critical section, re-reads the latest state and re-evaluates the second proposal. The total committed amount cannot exceed the shared allowance.”

## Scene 6 — Evidence

Open **Decision receipts**, then verify the audit chain.

“Every result has a receipt containing the policy version, state versions, verification checks, outcomes and a hash-linked audit record. We can inspect why each action was approved, adjusted or deferred.”

## Close

“TreatyAI is not another agent orchestrator. It is the decision-governance layer between autonomous intent and business execution. The current prototype proves the local decision engine with deterministic scenarios. A next stage would connect the same contracts to Salesforce Agentforce and evaluate the system against larger enterprise workloads.”

## Claims discipline

- Say “local simulation” when describing agents and CRM data.
- Do not claim a live Salesforce integration.
- Do not call the hash chain immutable or cryptographically signed.
- Do not generalize synthetic benchmark results to production.
- Describe the optimizer as bounded beam search, not a formal proof of optimality.
