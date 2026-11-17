# Groq AI Integration — Developer Notes

## Current implementation

TreatyAI now supports two paths in the same Mac application:

1. Offline deterministic proposal generation and TreatyBench, which require no API key.
2. Real Groq-hosted language-model proposal generation, mediation, optional credit-counteroffer negotiation, and deterministic verification.

The live path calls GroqCloud over HTTPS. The HTTP client requests strict JSON-schema output and low reasoning effort, checks finish_reason=stop, and refuses truncated or malformed responses. It does not download model weights or add an ML runtime to the Mac.

## Activate without exposing the credential in source

Open the local UI at http://127.0.0.1:8765/#agents and paste the API key into the password input. Click Save to Keychain.

The backend rejects cross-origin credential requests, validates the credential using Groq's official Models endpoint, checks that supported structured-output models are available, and stores the credential in the macOS login Keychain. It does not echo the key, store it in source code, or include it in a Git commit.

Alternative: set GROQ_API_KEY in the process environment before launching the server.

Note: macOS Keychain protects the credential at rest. The native macOS security utility receives the credential momentarily as a process argument during initial setup. This is for local developer use, not hardened multi-user server deployment.

## Model choice

- Default: openai/gpt-oss-20b.
- Optional: openai/gpt-oss-120b.
- Both use Groq's strict JSON-schema structured outputs.
- To select the larger model, set TREATYAI_GROQ_MODEL to openai/gpt-oss-120b before starting the app.

Each request is schema-constrained. The server still validates identity-independent attributes, amount limits, action types, evidence references, schema fields and the final business decision. JSON-schema conformity alone is not treated as authorization.

## Multi-agent workflow

1. Load authoritative synthetic CRM snapshot and scenario facts.
2. Run separate Groq specialist calls concurrently for service, retention and marketing (or marketing and retention in the consent scenario).
3. Convert every acceptable model recommendation into a trusted server-constructed DecisionContract. Model text cannot assign its own identity, authorization, idempotency key or customer-state version.
4. Compute a deterministic conflict graph and proposed safe plan.
5. Ask a separate Groq mediator to analyze the conflicts and propose an advisory settlement.
6. In Deep mode, send proposed reduced amounts back to relevant credit specialists. Only accepted reductions, never increases, can be incorporated.
7. Rebuild the conflict graph, optimize a feasible plan and run the independent deterministic verifier.
8. Under a SQLite write lock, revalidate the plan against the current customer snapshot and commit only feasible synthetic actions.
9. Save the complete structured negotiation transcript and metrics in the decision record. SHA-256-link its canonical representation in the decision receipt and append-only event chain.

The model does not write to SQLite or invoke Salesforce directly. Only one live negotiation may run at a time per local application process; competing requests return HTTP 429.

## Fail-closed behavior

- No key: the live endpoint returns HTTP 503 and does not mutate customer state.
- Invalid key: provider verification fails before storage or the live request returns HTTP 503.
- Provider timeout, 429 or other API failure: live endpoint returns an error; no partial negotiation commits.
- Malformed model output or unauthorized action/evidence: strict validation rejects it; no commit.
- Consent withdrawn: a proposed marketing action is rejected by deterministic policy even if the model proposes it.
- Competing credits: global budget and delegated agent constraints are independently verified.
- Customer state changed during inference: the transaction reacquires the latest locked state and re-evaluates the plan.
- Replay: idempotency table rejects already-processed proposals.
- Audit tampering: receipt verification checks event anchoring and the full persisted AI trace hash.

## Test status

The local unit/integration suite tests the entire workflow using mocked provider responses, including prompt injection, validation failure, trace tampering and transaction safety.

A real Groq model call is only verified after the user enters an active key in the local UI and the application successfully completes a live scenario. A key being saved in Keychain alone is not evidence that a full Groq negotiation has run.

## Privacy and cost

Synthetic customer profiles and task descriptions are transmitted to GroqCloud when live inference runs. Do not submit real personal or confidential customer data in this research prototype. Groq usage is subject to the credential owner's plan, limits and billing; the app records token counts but does not estimate actual monetary charges.

## Official reference

- https://console.groq.com/docs/models
- https://console.groq.com/docs/structured-outputs
- https://console.groq.com/docs/openai
- https://console.groq.com/docs/rate-limits
