# TreatyAI v0.3.0 — Release and Verification Notes

Release date: 17 November 2026
Platform: macOS 15 / Intel MacBook Pro / Python 3.10

## Delivered without Salesforce

- Offline deterministic Decision Room, scoped action contracts, constrained optimizer, pairwise and cumulative conflict graph.
- Independent verifier in a separate Python module, including plan consistency, business permissions, budget, contact limits, consent and idempotency.
- Serialized SQLite transaction with state-version revalidation, guarded updates and idempotency replay prevention.
- Tamper-evident receipt/audit hash chain; AI model trace anchored to receipt.
- Optional Groq multi-agent workflow: independent specialists, advisory mediator, specialist counteroffers and deterministic execution gate.
- Groq strict JSON-schema responses, bounded retry/timeout, incomplete-response rejection and one active inference run at a time.
- Local-only Keychain credential setup after provider verification. No plaintext API key in source files.
- Customer-journey and withdrawn-consent scenarios; simulated 30-case TreatyBench baseline.
- Adversarial verification tests, 180 deterministic randomized safety cases and 45 small exact-optimization oracle comparisons.
- Responsive desktop/mobile UI smoke tested with existing Brave, without installing another browser.
- Protected external DecisionBatch endpoint: disabled until a separate service bearer is configured.
- Salesforce DX Invocable Apex scaffold, Apex mocks, current OpenAPI, request/response examples and teammate handoff package.
- French technical pitch and demo guide.

## Tested

- 41 Python standard-library unittest cases (includes 180 deterministic fuzz subcases and 45 exhaustive small-case oracle comparisons).
- Automated browser smoke: overview, decision room, receipts, policy registry, TreatyBench, AI Agent Lab, and mobile navigation.
- Mocked Groq provider contract and full UI trace. This does NOT imply a real paid/live model call.
- Local HTTP checks, schema-validation errors, security headers and audit-chain verification.
- Source package SHA-256 secret-pattern check and ZIP integrity.

## Live dependencies not yet verified

- The Groq credential has not been configured in the Mac's Keychain, so **no live Groq call is claimed**. To activate it, open the AI Agent Lab and use the one-time Save to Keychain control with the existing Groq credential.
- The Salesforce Developer Edition org is assigned to the teammate; Apex source has not been compiled, deployed or tested there.
- No Salesforce or Marketing Cloud external action dispatch exists in this release.

## Scope and limitations

This is a functional engineering prototype on synthetic CRM data, not a production deployment. External bearer auth is a service-level gate, not individual Salesforce agent authentication. Public deployment still requires verified tenant mapping, authenticated HTTPS gateway, audit retention, real business-state reconciliation, downstream idempotency/outbox, secrets rotation and privacy controls.

SQLite provides serialization for this local single-database demonstration, not distributed atomicity. The optimizer uses bounded beam search and is not globally optimal on arbitrarily large inputs. Hash-linked receipts are tamper-evident but not digitally signed.

## Packaging

- Full project ZIP: TreatyAI-v0.3.0-source.zip
- Salesforce teammate ZIP: TreatyAI-v0.3.0-Salesforce-Handoff.zip

Both archives are stored next to the TreatyAI project folder in Desktop/Projects. They exclude keys, SQLite databases, Git metadata and temporary browser screenshots.

## Reproduce

Start: cd ~/Desktop/Projects/TreatyAI && ./run.sh
Automated tests: python3 -m unittest discover -s tests -v
Optional browser QA: python3 tests/browser_smoke.py
Rebuild both ZIPs: python3 scripts/build_handoff.py

The source is versioned in Git under tag v0.3.0.
