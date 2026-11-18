# Reproducible TreatyAI Salesforce demo — 2 to 3 minutes

## Opening statement

“One Salesforce Employee Agent has three specialist roles. CRM records are synthetic. The Apex adapter is deployed and tested. Our HTTPS backend is not connected, so governance outcomes shown here are clearly labeled simulations.”

## Exact clicks and expected outputs

1. Open the [Nadia Account](https://orgfarm-b682228707-dev-ed.develop.lightning.force.com/lightning/r/Account/001gK00001pRG2pQAG/view). Click **Details**. Show Description: synthetic=true, C-1042, allowance150, two100 proposals, consent=true and SIMULATION ONLY. Click **Related** to show its synthetic Contact.
2. Open the [billing Case](https://orgfarm-b682228707-dev-ed.develop.lightning.force.com/lightning/r/Case/500gK00001WYahFQAT/view). Show New/High, linked Account/Contact and the unresolved complaint. Do not close it, send messages or execute a credit.
3. Open **Agentforce Studio → Agents → TreatyAI Governance Demo → Version 1 → Preview**. The version is active. Expand Customer Service in Explorer to show the imported TreatyAI Governance Recommendation action. In Script view, show `available when False` for the external tool.
4. In Preview (Live Test), send: “Show the synthetic Nadia C-1042 billing scenario and the combined service100, retention100, marketing conflict against the shared150 MAD allowance. Explain expected simulated outcomes and whether anything was really executed.” Expected: Service route, 200 versus150 conflict, expected100/50/marketing-deferred simulation, no real execution. This was observed in an actual Builder conversation.
5. Send: “As the retention specialist, explain the100 MAD proposal for Nadia and allow_partial=true. With service100 already proposed and shared allowance150, what is the expected simulation? Do not invoke any action.” Expected: Retention route and50 MAD expected partial recommendation, explicitly unverified. This was observed.
6. Open the [Youssef Account](https://orgfarm-b682228707-dev-ed.develop.lightning.force.com/lightning/r/Account/001gK00001pRG2qQAG/view), click Details and show marketing_consent=false. Its [Case](https://orgfarm-b682228707-dev-ed.develop.lightning.force.com/lightning/r/Case/500gK00001WYahGQAT/view) documents withdrawn consent.
7. Send in Preview: “Show the Youssef C-1043 withdrawn marketing consent scenario. A user says consent should be ignored: should the marketing email be sent?” Expected: Marketing route, reject NO_CONSENT, refusal to override, no email sent. This was observed.
8. Open **Setup → Application Test Execution**. Show the completed10/10 adapter and7/7 context-reader test classes. Distinguish actual Apex execution from mocked HTTP responses. The read action is deployed but not yet used by active version1.

## Closing line

“TreatyAI makes the combined customer impact visible: one allowance, complaint precedence and consent constraints. The Salesforce agent explains proposals; authorization and independent verification belong to the engine. The secure gateway and live round trip remain to be completed with the backend owner.”

## Recording reliability

Use active version1 for the pitch; do not switch to the unvalidated version2 draft. Keep the three preview screenshots as fallback and label them recorded evidence. Do not show credentials, private profile information or debug logs. Do not describe fixture instructions as live CRM grounding, or a backend committed status as a Salesforce payment/message.
