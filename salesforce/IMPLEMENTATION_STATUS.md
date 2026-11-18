# TreatyAI Salesforce implementation — 18 November 2026

Base: v0.3.0, commit 594e5792150a0c21415ba24a58ac630c36755fa9. The newer org-validated adapter ZIP was preserved; no Python engine or main-branch files were changed.

## Completed and observed in Salesforce

- One Employee Agent: **TreatyAI Governance Demo**, version 1 active after explicit user confirmation. It contains Service, Retention and Marketing specialist subagents plus routing/off-topic handling. These are not three independently deployed agents.
- Existing **TreatyAI Governance Recommendation** imported into the Service subagent. Exact three-input/five-output Apex contract preserved. Its tool has `available when False`, so the external gateway cannot be selected in this offline release. Its imported action definition requires user confirmation for future use. No new permission sets or profiles were assigned.
- Three actual Builder Preview conversations passed: Nadia combined budget conflict, Youssef withdrawn consent including an override attempt, and partial retention. Responses explicitly identify simulation, absence of gateway verification, and absence of business execution. See evidence/agent-preview-responses.json.
- Two synthetic Accounts, two Contacts, two Cases created by the idempotent scripts/apex/treatyai-seed.apex script. No actual emails, phone numbers, financial transactions or outbound messages were used.
- Account.AccountNumber maps synthetic IDs; Account.Description stores clearly labeled demo facts: consent, shared allowance, proposals, contact limit and expected simulation. These are demonstration facts, not a production consent registry or financial ledger. The org did not expose Contact.HasOptedOutOfEmail; the initial seed compile failed, was corrected and then executed successfully.
- Existing TreatyAIGovernanceActionTest re-run: **10/10 passed** with mocked callouts. Previously observed class coverage: **100% (91/91)**. This does not prove gateway integration or full branch coverage.
- New TreatyAIDemoContext and TreatyAIDemoContextTest compiled. **7/7 tests passed in Salesforce**. The reader uses WITH USER_MODE and with sharing, accepts only C-1042/C-1043, requires a unique marked synthetic Account, and reads actual Case state. It performs no DML or callouts. Tests use isolated Salesforce test records; it has not yet been invoked by the active agent against the persistent demo records.
- No extra Flow is needed to duplicate the existing invocable Apex contract. No TreatyAI Flow was created.

## Implemented locally, not deployed or live-tested

- agent-source/pending-version-2-NOT-SAVED-OR-VALIDATED.agent adds fixed-ID CRM read actions to the specialists. **It has not been saved, parsed or tested in Builder.** Version 2 was cloned from version 1 in the org before the attempted edit was blocked. Version 1 remains active and uses embedded synthetic examples; it does not query CRM.
- The .agent sources are source-level captures/drafts, not a full Metadata API export. The actual generated developer name is TreatyAI_Governance_DemoTreatyAI_Governance_Demo; preserve it when resuming in this org. Do not silently rename it or create another agent.
- gateway/gateway.py: separate loopback sidecar proposal; no backend source modifications. **17 local tests passed**, including actual temporary loopback HTTP with a mocked upstream. The real backend was not contacted. This is not a production security certification.

## Blocked and remaining

- Browser review stopped the version-2 edit with a usage-limit error. The failed write was not executed. Resume Builder only when browser review is available; review and validate the pending script, test actual CRM reads, commit it, and obtain explicit activation confirmation for version 2. Do not bypass the blocked browser operation through CLI, APIs, another browser or indirect execution.
- Backend owner's approval and access are still required for any sidecar/tunnel deployment on their Mac or another host. No gateway was published, URL invented, backend environment changed or service credentials requested in chat.
- Named Credential TreatyAI_API and its External Credential remain unconfigured. No live Agentforce-to-TreatyAI traffic, actual backend consent/budget test, authentication test against the real service, or real financial/marketing dispatch occurred.
- GitHub upstream branch creation returned 403 Resource not accessible by integration. User then authenticated in the in-app browser; fork irfanWh/TreatyAI and feature/salesforce-agentforce were created there. See delivery report for final push/PR result. Never infer push success from repository permissions alone.

## Resume safely

1. Confirm current agent version and retain version 1 as fallback. Open the existing version-2 draft rather than creating a second project.
2. Validate the pending source in Builder. Confirm fixed CRM IDs, user-mode queries and disabled gateway condition. Test read failure, withdrawn consent, open Case and changed allowance. Never treat model-generated explanations as policy enforcement.
3. Capture an actual CRM action trace before describing the agent as grounded in live CRM.
4. Review gateway/README.md with the backend owner, then configure a real approved HTTPS destination and secrets through protected configuration.
5. Perform one synthetic end-to-end batch, preserve its idempotency keys, reconcile timeout/409 against the original receipt, and do not automatically retry.
6. Only a separate authorized dispatcher could apply real Salesforce business changes. None exists in this release.
