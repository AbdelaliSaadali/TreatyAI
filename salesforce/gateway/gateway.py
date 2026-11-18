"""Reviewable synthetic-demo sidecar. Bind loopback; HTTPS ingress is external.
Never point a tunnel at the backend itself. No backend source changes.
"""
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
import threading
import time
import urllib.request
import urllib.error

ROUTE = '/api/decisions/coordinate'
MAX_BYTES = 100_000
MAX_RESPONSE = 1_000_000
SCOPES = {
    'C-1042': {'service-agent': {'issue_credit'}, 'retention-agent': {'issue_credit'}, 'marketing-agent': {'send_marketing'}},
    'C-1043': {'marketing-agent': {'send_marketing'}},
}
PROPOSAL_FIELDS = {'proposal_id','idempotency_key','agent_id','customer_id','action_type','amount_mad','channel','priority','utility','allow_partial','reversible','requires_human','proposed_at','expires_at','expected_state_version','evidence','rationale','context_note'}

class Rejection(Exception):
    def __init__(self, status): self.status = status

class Limiter:
    def __init__(self, limit=10, clock=time.monotonic):
        self.limit, self.clock = limit, clock
        self.events, self.lock = defaultdict(deque), threading.Lock()
    def accept(self, principal):
        with self.lock:
            now = self.clock(); queue = self.events[principal]
            while queue and queue[0] <= now - 60: queue.popleft()
            if len(queue) >= self.limit: return False
            queue.append(now); return True

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate JSON key')
        result[key] = value
    return result

def validate_payload(raw):
    try:
        data = json.loads(raw, object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(data, dict) or set(data) != {'scenario_id','customer_id','proposals'}: raise ValueError()
        customer = data['customer_id']
        if customer not in SCOPES or data['scenario_id'] not in {'salesforce-demo','customer-journey','consent-boundary'}: raise ValueError()
        proposals = data['proposals']
        if not isinstance(proposals,list) or not 1 <= len(proposals) <= 20: raise ValueError()
        ids, keys = set(), set()
        for p in proposals:
            if not isinstance(p,dict) or set(p) - PROPOSAL_FIELDS: raise ValueError()
            if p.get('customer_id') != customer: raise ValueError()
            role, action = p.get('agent_id'), p.get('action_type')
            if action not in SCOPES[customer].get(role,set()): raise ValueError()
            pid, key = p.get('proposal_id'), p.get('idempotency_key')
            if not isinstance(pid,str) or not 3 <= len(pid) <= 64 or pid in ids: raise ValueError()
            if not isinstance(key,str) or not 8 <= len(key) <= 96 or key in keys: raise ValueError()
            ids.add(pid); keys.add(key)
            amount = p.get('amount_mad',0)
            if isinstance(amount,bool) or not isinstance(amount,(float,int)) or not 0 <= amount <= 100: raise ValueError()
            if action == 'issue_credit' and amount <= 0: raise ValueError()
            if action != 'issue_credit' and amount != 0: raise ValueError()
            if action == 'send_marketing' and p.get('channel') not in ('email','sms'): raise ValueError()
            # Authority grants are this fixed service scope, never model text.
            # Consent, aggregate budget and freshness are enforced by the backend.
        return data
    except (ValueError, TypeError, KeyError): raise Rejection(422) from None

def dispatch(method, path, headers, raw, service_token, limiter, forward):
    if path != ROUTE: raise Rejection(404)
    if method != 'POST': raise Rejection(405)
    if not isinstance(service_token,str) or len(service_token) < 32: raise Rejection(503)
    expected = ('Bearer ' + service_token).encode()
    actual = str(headers.get('Authorization','')).encode()
    if not hmac.compare_digest(actual, expected): raise Rejection(401)
    if not limiter.accept('salesforce-demo'): raise Rejection(429)
    if headers.get('Content-Type','').split(';',1)[0].strip().lower() != 'application/json': raise Rejection(415)
    if len(raw) > MAX_BYTES: raise Rejection(413)
    data = validate_payload(raw)
    # Exactly one forward. No automatic retries: timeout may have committed.
    try: return forward(json.dumps(data,allow_nan=False).encode())
    except Rejection: raise
    except Exception: raise Rejection(502) from None

def forward_to_backend(raw):
    token = os.environ.get('TREATYAI_INTEGRATION_TOKEN','')
    if len(token) < 32: raise Rejection(503)
    # Fixed loopback upstream; no attacker-controlled URL, path or headers.
    req = urllib.request.Request('http://127.0.0.1:8765' + ROUTE, data=raw,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}, method='POST')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(req,timeout=10) as response:
            payload = response.read(MAX_RESPONSE+1)
            if len(payload)>MAX_RESPONSE: raise Rejection(502)
            parsed = json.loads(payload)
            if not isinstance(parsed,dict): raise Rejection(502)
            return response.status,payload
    except urllib.error.HTTPError as exc:
        # Do not leak upstream error details, tokens, headers or stack traces.
        raise Rejection(exc.code if exc.code in (401,409,422,503) else 502) from None

class Handler(BaseHTTPRequestHandler):
    limiter = Limiter()
    def log_message(self,*args): pass  # No payloads, credentials, URLs or PII in logs.
    def respond(self,status,payload):
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Connection','close')
        if status == 429: self.send_header('Retry-After','60')
        self.end_headers(); self.wfile.write(payload); self.close_connection=True
    def do_POST(self):
        self.connection.settimeout(5)
        try:
            if self.path != ROUTE: raise Rejection(404)
            # Reject ambiguous framing, chunked bodies and unbounded reads.
            lengths = self.headers.get_all('Content-Length',[])
            if len(lengths)!=1 or not lengths[0].isdigit() or self.headers.get('Transfer-Encoding'): raise Rejection(400)
            length=int(lengths[0])
            if length>MAX_BYTES: raise Rejection(413)
            raw=self.rfile.read(length)
            if len(raw)!=length: raise Rejection(400)
            status,payload=dispatch(self.command,self.path,self.headers,raw,os.environ.get('TREATYAI_GATEWAY_TOKEN',''),self.limiter,forward_to_backend)
            self.respond(status,payload)
        except Rejection as exc: self.respond(exc.status,json.dumps({'error':'integration request rejected','status':exc.status}).encode())
        except Exception: self.respond(502,b'{"error":"integration unavailable"}')
    def do_GET(self): self.respond(404,b'{"error":"not found"}')
    do_PUT=do_DELETE=do_PATCH=do_OPTIONS=do_GET

def main():
    for key in ('TREATYAI_GATEWAY_TOKEN','TREATYAI_INTEGRATION_TOKEN'):
        if len(os.environ.get(key,''))<32: raise SystemExit('Required service credentials are not configured; not starting.')
    ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()

if __name__=='__main__': main()
