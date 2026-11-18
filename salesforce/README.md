# TreatyAI Salesforce integration

This directory contains the org-tested Apex adapter, a read-only synthetic CRM context action, seed script, active Agent Script source, a clearly marked pending version2 draft, a proposed restricted gateway and sanitized evidence.

- [Implementation status](IMPLEMENTATION_STATUS.md): live results and precise limitations.
- [Demonstration procedure](DEMO_PROCEDURE.md): exact clicks and three tested prompts.
- [Gateway](gateway/README.md): owner-review proposal, hosting assessment and local tests.
- [Active version1](agent-source/active-version-1.agent): actual saved Agent Script, not a full Metadata API export.
- [Pending version2](agent-source/pending-version-2-NOT-SAVED-OR-VALIDATED.agent): source only; blocked browser write, not validated or active.

17 Apex methods passed in the real org:10 adapter tests with mocked HTTP and7 context-reader tests with isolated Salesforce data. Seventeen gateway tests passed locally using a mocked upstream, including temporary loopback HTTP. Three actual Agentforce Preview conversations exercised Service, Retention and Marketing. None of these is a live Salesforce-to-TreatyAI round trip.

Apex uses API68.0. Deployment to another org requires review of class access and metadata dependencies. Do not deploy the pending agent draft blindly. Active version1 deliberately disables the external governance tool with a literal false condition. The backend, its main branch and real business systems remain unchanged.

Historical request/response JSON under fixtures/ comes from v0.3.0. It is an archived example, not a fresh live result or a payload to replay with its original keys. Review the gateway's approved scenario list and generate a new authorized test batch only when the backend owner is ready.

Current Salesforce supports source retrieval through AiAuthoringBundle and, at API68, AiAgentDefinition/AiAgentDefinitionVersion. Retrieve the actual version and dependencies when browser review/access becomes available; the files here do not claim a completed metadata export. See [official Salesforce metadata guidance](https://developer.salesforce.com/blogs/2026/11/agentforce-metadata-types-in-winter-27-dive-into-aiagentdefinition).
