# TreatyAI Salesforce DX Scaffold

This folder contains source for a future custom Agentforce Apex action.

## Files

- sfdx-project.json — Salesforce DX source project definition.
- force-app/main/default/classes/TreatyAIGovernanceAction.cls — Invocable Apex callout adapter to the TreatyAI decision endpoint.
- force-app/main/default/classes/TreatyAIGovernanceActionTest.cls — HttpCalloutMock tests for a success path and invalid payload rejection.
- Matching metadata XML files.

## Current status

**Source authored, not compiled, not deployed, not tested in a Salesforce org.**

Do not call this a working Agentforce integration until a real Developer Edition org is connected and the Apex tests pass there.

## Create a free Agentforce Developer Edition

Visit https://developer.salesforce.com/signup and create a Developer Edition with Agentforce and Data 360. Salesforce's current free Developer Edition includes Agentforce and a cloud-hosted Agentforce Vibes IDE, so installing Salesforce CLI locally is not required for the first integration steps.

## Prerequisites for deployment

1. An authorized Agentforce Developer Edition org.
2. A secured HTTPS deployment of TreatyAI reachable from Salesforce; 127.0.0.1 on your Mac cannot be called by Salesforce cloud.
3. A Salesforce External Credential and Named Credential named TreatyAI_API.
4. Strong service authentication, customer authorization and tenant isolation at the TreatyAI gateway.
5. Real authoritative CRM mapping for contact consent, open cases and compensation allowances.
6. Review of the Apex action fields and any custom object schema before deployment.
7. A locked-down, reviewable production policy and external transaction/outbox design.

The existing local endpoint is not authenticated and must never be placed on the public internet unchanged.

## Planned deployment

- Open Agentforce Vibes IDE in the Developer Edition org.
- Import or upload the source project.
- Configure the authenticated Named Credential with the API base URL.
- Validate Apex compilation, execute all Apex tests and inspect code coverage.
- Add the Invocable Apex method as a custom Agentforce Action.
- Connect specialist agents to TreatyAI for governance of their proposed decisions.
- Test full end-to-end round trips, customer-level permissions, retries and rollback.

## Official references

- https://developer.salesforce.com/signup
- https://developer.salesforce.com/docs/ai/agentforce/guide/agent-invocablemethod.html
- https://developer.salesforce.com/docs/platform/apex-dev/references/apex-dev/apex-classes-annotation-invocablemethod.html
- https://developer.salesforce.com/docs/platform/apex-dev/references/apex-dev/apex-callouts.html

Deployment work requires access to the actual Salesforce org.
