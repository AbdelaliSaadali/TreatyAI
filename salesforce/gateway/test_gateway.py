import json
import unittest
from gateway import dispatch, Rejection, Limiter, ROUTE, MAX_BYTES
TOKEN='synthetic-test-token-'+'x'*40
class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]; self.limiter=Limiter(); self.headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'}
        self.data={'scenario_id':'salesforce-demo','customer_id':'C-1042','proposals':[{'proposal_id':'TEST-1','idempotency_key':'idem-test-001','customer_id':'C-1042','agent_id':'service-agent','action_type':'issue_credit','amount_mad':100}]}
    def forward(self,raw): self.calls.append(raw); return 200,b'{"status":"mock-only"}'
    def call(self,**kw):
        args=dict(method='POST',path=ROUTE,headers=self.headers,raw=json.dumps(self.data).encode(),service_token=TOKEN,limiter=self.limiter,forward=self.forward); args.update(kw); return dispatch(**args)
    def reject(self,code,**kw):
        with self.assertRaises(Rejection) as cm: self.call(**kw)
        self.assertEqual(code,cm.exception.status); self.assertFalse(self.calls)
    def test_valid_fixed_scope_forwarded_once(self): self.assertEqual(200,self.call()[0]); self.assertEqual(1,len(self.calls))
    def test_missing_auth(self): self.reject(401,headers={'Content-Type':'application/json'})
    def test_invalid_auth(self): self.reject(401,headers={'Authorization':'Bearer invalid','Content-Type':'application/json'})
    def test_no_secret_disables_service(self): self.reject(503,service_token='')
    def test_routes_never_forward(self):
        for path in ('/api/demo/reset','/api/ai/configure',ROUTE+'?x=1',ROUTE+'/','/api/overview'): self.reject(404,path=path)
    def test_wrong_method(self): self.reject(405,method='GET')
    def test_size_limit(self): self.reject(413,raw=b'x'*(MAX_BYTES+1))
    def test_content_type(self): self.reject(415,headers={**self.headers,'Content-Type':'text/plain'})
    def test_bad_json_and_duplicate_keys(self):
        for raw in (b'not-json',b'{"customer_id":"x","customer_id":"y"}',b'[]',b'{"x":NaN}'): self.reject(422,raw=raw)
    def test_customer_and_agent_scope(self):
        self.data['proposals'][0]['customer_id']='C-1043'; self.reject(422)
        self.data['proposals'][0]['customer_id']='C-1042'; self.data['proposals'][0]['agent_id']='admin'; self.reject(422)
    def test_duplicate_keys(self): self.data['proposals']*=2; self.reject(422)
    def test_per_agent_amount_and_action_scope(self):
        self.data['proposals'][0]['amount_mad']=151; self.reject(422)
        self.data['proposals'][0]['amount_mad']=0; self.data['proposals'][0]['action_type']='resolve_case'; self.reject(422)
    def test_upstream_failure_no_retry(self):
        attempts=[]
        def fail(raw): attempts.append(1); raise TimeoutError('private')
        with self.assertRaises(Rejection) as cm:self.call(forward=fail)
        self.assertEqual(502,cm.exception.status); self.assertEqual(1,len(attempts))
    def test_rate_limit_and_expiry(self):
        now=[0]; rate=Limiter(limit=2,clock=lambda:now[0]);self.assertTrue(rate.accept('test'));self.assertTrue(rate.accept('test'));self.assertFalse(rate.accept('test'));now[0]=61;self.assertTrue(rate.accept('test'))

class HTTPBoundaryTests(unittest.TestCase):
    """Actual loopback HTTP, mocked upstream; never contacts TreatyAI/Salesforce."""
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer
        from gateway import Handler
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,method,path,body=b'',headers=None):
        import http.client
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        conn.request(method,path,body=body,headers=headers or {})
        response=conn.getresponse();result=response.status,response.read(),dict(response.getheaders());conn.close();return result
    def test_hidden_routes_and_no_cors(self):
        for path in ('/api/demo/reset','/api/ai/configure','/api/overview'):
            status,body,headers=self.request('POST',path)
            self.assertEqual(404,status);self.assertNotIn('Access-Control-Allow-Origin',headers)
    def test_http_missing_auth(self):
        from unittest.mock import patch
        with patch.dict('os.environ',{'TREATYAI_GATEWAY_TOKEN':TOKEN}):
            self.assertEqual(401,self.request('POST',ROUTE,b'{}',{'Content-Type':'application/json'})[0])
    def test_http_authenticated_request_and_redacted_failure(self):
        from unittest.mock import patch
        data={'scenario_id':'salesforce-demo','customer_id':'C-1043','proposals':[{'proposal_id':'MKT-1','idempotency_key':'idem-test-mkt','customer_id':'C-1043','agent_id':'marketing-agent','action_type':'send_marketing','channel':'email'}]}
        headers={'Content-Type':'application/json','Authorization':'Bearer '+TOKEN}
        with patch.dict('os.environ',{'TREATYAI_GATEWAY_TOKEN':TOKEN}):
            with patch('gateway.forward_to_backend',return_value=(200,b'{"status":"mock_only"}')) as upstream:
                self.assertEqual(200,self.request('POST',ROUTE,json.dumps(data).encode(),headers)[0]);upstream.assert_called_once()
            with patch('gateway.forward_to_backend',side_effect=RuntimeError('private-secret-should-not-leak')):
                status,body,_=self.request('POST',ROUTE,json.dumps(data).encode(),headers)
                self.assertEqual(502,status);self.assertNotIn(b'private-secret',body)

if __name__=='__main__': unittest.main()
