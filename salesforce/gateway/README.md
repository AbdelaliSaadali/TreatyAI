# Restricted synthetic-demo gateway — proposed, not deployed

This is a separate sidecar, not a change to TreatyAI's Python engine. It only binds **127.0.0.1:8766** and forwards exactly POST /api/decisions/coordinate to the existing loopback backend on 8765. Never tunnel directly to 8765. The backend owner must review and approve the actual host, process and network configuration before this is run outside the temporary mock tests.

## Hosting assessment

For this SQLite-based hackathon demo, the least disruptive option is a reviewed sidecar on the backend owner's machine behind an explicitly configured named HTTPS tunnel. A real Cloudflare account/domain and owner's approval are prerequisites, not items already provisioned. Restrict ingress to the exact path and add a catch-all 404. Cloudflare documents [path-specific ingress and catch-all rules](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/).

A separate hosted copy is possible after owner approval, but it must have durable SQLite storage and expose only the sidecar. [Render's free service](https://render.com/docs/free) sleeps after 15 minutes and has no persistent disk; that combination is a poor fit for a reliable audit/idempotency demo and a 15-second Apex timeout. Paid storage or another approved host would be needed. No spending or account creation was performed.

A Worker can enforce additional ingress rules, but cannot directly reach another person's loopback backend. Its [rate-limit binding](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/) uses per-location counters and is not a globally strict quota.

## Security boundary and limits

- Gateway verifies a separate TREATYAI_GATEWAY_TOKEN and maps it to one fixed synthetic demo service principal. That service is authorized only for the fixed customers/roles/actions in SCOPES. It does **not** cryptographically identify three independent specialist agents. Real per-agent identities or tenants require a stronger identity gateway and authorization policy.
- TREATYAI_INTEGRATION_TOKEN remains a separate upstream bearer credential, not the Groq key. The gateway does not trust incoming Authorization for upstream forwarding.
- Exact path and method, content type, size (100 KB), unambiguous Content-Length, no chunked framing, duplicate JSON-key rejection, fixed customer/role/action scope, identifier/key uniqueness and bounded per-agent amount are checked. Full typed contract, authoritative consent, aggregate budget, freshness and durable idempotency remain the existing backend's responsibilities. The gateway does not approve an action.
- Ten authenticated requests/minute/process; a single sidecar process is assumed. This is not a distributed rate limiter or protection against all denial-of-service attacks. Apply additional ingress authentication/rate limits and concurrency limits before publication.
- Fixed loopback upstream; environment proxies and redirects disabled; response size bounded; ten-second upstream timeout; no automatic retry. Error details are redacted; payloads and bearer credentials are not logged.
- A timeout/502 may mean the backend committed before the response was lost. Preserve the original keys and reconcile manually; never create fresh keys and blindly retry.
- TLS must terminate at the approved ingress; this script alone does not create HTTPS or a public URL. No actual TLS, tunnel or public authentication has been verified.

## Owner-reviewed deployment inputs

The owner must provide an approved host and privately provision strong, distinct gateway and backend service tokens (at least 32 characters). Do not paste them in chat, source, shell history, screenshots or logs. Use the platform's secret manager or protected process environment. Do not start the sidecar against a backend whose scope/fixture state has not been reviewed.

After review, a named tunnel ingress file would have the following shape; placeholders are intentionally not real destinations:

```yaml
tunnel: APPROVED_TUNNEL_ID
credentials-file: /protected/path/to/tunnel-credentials.json
ingress:
  - hostname: APPROVED_HOSTNAME
    path: ^/api/decisions/coordinate$
    service: http://127.0.0.1:8766
  - service: http_status:404
```

Review edge authentication, request limits and route rules before deployment. The tunnel configuration and publication require the owner's explicit approval and the browser's action-time access review where applicable.

## Salesforce configuration after a real gateway exists

Create an External Credential using the supported custom authentication/header mechanism with a named principal restricted to the demo service. Store the gateway token as a protected authentication parameter and construct the Authorization bearer header there. Create Named Credential **TreatyAI_API** pointing to the approved HTTPS base URL and referencing that External Credential. Review the exact External Credential principal/class/agent access before assigning any permission; no broad profile grants are needed merely to create metadata. Follow the [official Named Credentials guide](https://developer.salesforce.com/docs/platform/named-credentials/guide/nc-about.html).

Keep the gateway tool unavailable until configuration and owner approval are complete. Real end-to-end testing must use synthetic records and the original idempotency keys. Check success, missing/invalid auth, withdrawn consent, combined budget, human review, no_action, halted, replay and upstream loss with the actual service before claiming connectivity.

## Tests actually run

```sh
python3 -m unittest discover -s salesforce/gateway -v
```

17 tests passed on 18 November 2026. Three tests use real temporary loopback HTTP; all upstream responses are mocked. They do not prove real backend policy enforcement or live Salesforce authentication.
