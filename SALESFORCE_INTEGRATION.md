# Salesforce / Agentforce Integration Plan

## Status

**Designed integration boundary; not yet connected to Salesforce.**

This repository has no Salesforce Developer Org, Agentforce credentials, Named Credential, Marketing Cloud account or live Salesforce adapter. The current FastAPI service binds to 127.0.0.1 and is intentionally local-only. Salesforce cloud services cannot call that loopback address.

The generic endpoint is implemented and documented. It now requires a separate TREATYAI_INTEGRATION_TOKEN bearer credential and responds HTTP 503 when it is not configured:

- OpenAPI schema: /api/openapi.json
- API reference: /api/docs
- Decision intake: POST /api/decisions/coordinate

## Intended integration flow

1. A specialized Agentforce agent identifies a possible business action.
2. A custom Agentforce action serializes the intention as a TreatyAI Decision Contract.
3. The integration gateway authenticates the calling Salesforce principal and maps it to a registered TreatyAI agent identity.
4. TreatyAI loads authoritative customer state from the approved data adapter. Agent-provided context is not treated as authoritative policy state.
5. TreatyAI builds the cross-agent conflict graph, applies deterministic policy, optimizes a feasible plan and independently verifies it.
6. The response returns action outcomes, reason codes, state versions and a decision receipt.
7. A separate controlled dispatcher sends only verified, approved actions to Salesforce or Marketing Cloud. External side effects are not performed by the LLM itself.

## Decision intake contract

A request contains one scenario identifier, one customer identifier and between one and twenty proposals. Every proposal has a unique proposal ID and idempotency key, a registered agent identity, an action type, bounded action parameters, evidence references and an expected customer-state version.

Example shape (illustrative values only):

    {
      "scenario_id": "customer-retention",
      "customer_id": "C-1042",
      "proposals": [
        {
          "proposal_id": "AGENT-PROPOSAL-001",
          "idempotency_key": "salesforce-action-unique-key-001",
          "agent_id": "service-agent",
          "customer_id": "C-1042",
          "action_type": "issue_credit",
          "amount_mad": 100,
          "channel": "none",
          "priority": 1,
          "utility": 90,
          "allow_partial": true,
          "reversible": true,
          "requires_human": false,
          "proposed_at": "2026-11-16T12:00:00+00:00",
          "expected_state_version": 4,
          "evidence": ["case:CS-778", "policy:COMPENSATION-V4"],
          "rationale": "Compensate a verified billing disruption.",
          "context_note": "Untrusted descriptive context."
        }
      ]
    }

The endpoint validates the schema and rejects unknown fields. A repeated idempotency key returns HTTP 409. Proposals whose customer state has changed are re-evaluated against the latest locked state before commit.

## Salesforce data mapping (future)

| Salesforce source | TreatyAI use |
|---|---|
| Agentforce agent identity / principal | Map to a registered agent ID and delegated scope |
| Account / Contact | Customer identity and segment |
| Case | Open critical case and service precedence |
| Consent / communication preferences | Authoritative marketing eligibility |
| Custom compensation object or approved ledger | Remaining customer compensation allowance |
| Marketing Cloud Journey event | Downstream campaign dispatch after TreatyAI approval |

Do not use a value supplied only in an agent prompt as the authoritative source for consent, customer budget, authorization or case status.

## Salesforce setup path (future)

1. Provision an approved Salesforce Developer Org with Agentforce capabilities.
2. Deploy TreatyAI behind a public HTTPS endpoint in an approved environment. Do not expose the local development server directly.
3. Add OAuth-based service authentication, agent identity mapping, tenant scoping, rate limiting and request signing.
4. Import the OpenAPI schema through Salesforce External Services or implement an equivalent custom Apex action.
5. Configure an External Credential / Named Credential for the TreatyAI service.
6. Add an Agentforce action that submits the DecisionBatch and interprets the returned status and reason codes.
7. Add a separate outbox-backed dispatcher for approved Salesforce updates and Marketing Cloud journey events.
8. Test retries, timeouts, duplicate delivery, partial failures and compensation/rollback workflows in a sandbox.

## Production requirements before connection

- OAuth 2.0 service authentication and explicit agent identity mapping.
- Tenant isolation and customer-level authorization.
- Signed or otherwise authenticated proposal envelopes.
- Authoritative customer state reads with version checks.
- Durable outbox and downstream idempotency.
- Retry policy, dead-letter handling and compensating actions.
- Policy change review and audit retention.
- No direct external side effects from model-generated tool calls.
- Human approval for high-impact or irreversible operations.

The current prototype demonstrates the decision engine and its HTTP contract only. It does not claim a live Salesforce integration.
