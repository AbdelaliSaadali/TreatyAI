@IsTest
private class TreatyAIGovernanceActionTest {
    static String hashValue() { return 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'; }
    static TreatyAIGovernanceAction.RequestInput input() {
        TreatyAIGovernanceAction.RequestInput x=new TreatyAIGovernanceAction.RequestInput();
        x.scenarioId='salesforce-test'; x.customerId='C-1042';
        x.decisionContractJson='{"proposals":[{"proposal_id":"TEST-001","idempotency_key":"test-key-001","customer_id":"C-1042","agent_id":"service-agent","action_type":"issue_credit","amount_mad":100,"proposed_at":"2026-11-18T12:00:00Z"}]}'; return x;
    }
    static Map<String,Object> body(String state, Boolean passed) {
        return new Map<String,Object>{'status'=>state,'decision_id'=>'DEC-TEST','scenario_id'=>'salesforce-test','customer_id'=>'C-1042','verification'=>new Map<String,Object>{'passed'=>passed},'receipt'=>new Map<String,Object>{'status'=>state,'decision_id'=>'DEC-TEST','scenario_id'=>'salesforce-test','customer_id'=>'C-1042','receipt_hash'=>hashValue()}};
    }
    class GatewayMock implements HttpCalloutMock {
        Integer code; String payload; Boolean fail;
        GatewayMock(Integer c,String b,Boolean f) {code=c;payload=b;fail=f;}
        public HttpResponse respond(HttpRequest req) {
            System.assertEquals('POST',req.getMethod());
            System.assertEquals('callout:TreatyAI_API/api/decisions/coordinate',req.getEndpoint());
            System.assertEquals('application/json',req.getHeader('Content-Type'));
            Map<String,Object> data=(Map<String,Object>)JSON.deserializeUntyped(req.getBody());
            System.assertEquals('C-1042',data.get('customer_id')); System.assertEquals('salesforce-test',data.get('scenario_id'));
            if(fail) throw new CalloutException('Synthetic timeout');
            HttpResponse res=new HttpResponse();res.setStatusCode(code);res.setBody(payload);return res;
        }
    }
    static void mock(Integer code,Map<String,Object> data) {Test.setMock(HttpCalloutMock.class,new GatewayMock(code,JSON.serialize(data),false));}
    static TreatyAIGovernanceAction.ResponseOutput run(TreatyAIGovernanceAction.RequestInput x) {return TreatyAIGovernanceAction.coordinate(new List<TreatyAIGovernanceAction.RequestInput>{x})[0];}
    static void closed(TreatyAIGovernanceAction.ResponseOutput out) {System.assertEquals('integration_error',out.status);System.assertEquals(false,out.verified);System.assertEquals('',out.decisionId);System.assertEquals('',out.receiptHash);}
    @IsTest static void committedRecommendation() {
        mock(200,body('committed',true));Test.startTest();TreatyAIGovernanceAction.ResponseOutput out=run(input());Test.stopTest();
        System.assertEquals('committed',out.status);System.assertEquals(true,out.verified);System.assertEquals('DEC-TEST',out.decisionId);System.assertEquals(hashValue(),out.receiptHash);System.assert(out.explanation.contains('no Salesforce action executed'));
    }
    @IsTest static void nonApprovalStates() {
        Test.startTest();for(String state:new List<String>{'awaiting_human','halted','no_action'}) {mock(200,body(state,true));TreatyAIGovernanceAction.ResponseOutput out=run(input());System.assertEquals(state,out.status);System.assertEquals(false,out.verified);}Test.stopTest();
    }
    @IsTest static void failedVerifier() {mock(200,body('committed',false));System.assertEquals(false,run(input()).verified);}
    @IsTest static void httpFailuresDoNotLeak() {
        Test.startTest();for(Integer code:new List<Integer>{401,409,422,503}) {Test.setMock(HttpCalloutMock.class,new GatewayMock(code,'private-detail',false));TreatyAIGovernanceAction.ResponseOutput out=run(input());System.assertEquals('provider_error',out.status);System.assertEquals(false,out.verified);System.assert(!out.explanation.contains('private-detail'));}Test.stopTest();
    }
    @IsTest static void timeoutFailsClosed() {Test.setMock(HttpCalloutMock.class,new GatewayMock(200,'',true));closed(run(input()));}
    @IsTest static void malformedAndMissingReceipt() {
        Test.setMock(HttpCalloutMock.class,new GatewayMock(200,'not-json',false));closed(run(input()));Map<String,Object> data=body('committed',true);data.remove('receipt');mock(200,data);closed(run(input()));
    }
    @IsTest static void receiptMismatchAndUnknownStatus() {
        Map<String,Object> data=body('committed',true);((Map<String,Object>)data.get('receipt')).put('customer_id','C-OTHER');mock(200,data);closed(run(input()));mock(200,body('unexpected',true));closed(run(input()));
    }
    @IsTest static void invalidInputsWithoutCallout() {
        Test.startTest();System.assertEquals(0,TreatyAIGovernanceAction.coordinate(null).size());closed(run(null));
        for(String data:new List<String>{'not-json','[]','{}','{"proposals":[]}'}) {TreatyAIGovernanceAction.RequestInput x=input();x.decisionContractJson=data;closed(run(x));}
        TreatyAIGovernanceAction.RequestInput x=input();x.customerId='bad customer';closed(run(x));System.assertEquals(0,Limits.getCallouts());Test.stopTest();
    }
    @IsTest static void scopeAndDuplicateRejection() {
        Test.startTest();TreatyAIGovernanceAction.RequestInput x=input();x.decisionContractJson=x.decisionContractJson.replace('C-1042','C-OTHER');closed(run(x));
        x=input();Map<String,Object> data=(Map<String,Object>)JSON.deserializeUntyped(x.decisionContractJson);List<Object> proposals=(List<Object>)data.get('proposals');proposals.add(proposals[0]);x.decisionContractJson=JSON.serialize(data);closed(run(x));System.assertEquals(0,Limits.getCallouts());Test.stopTest();
    }
    @IsTest static void oversizedInvocationRejectsAll() {
        List<TreatyAIGovernanceAction.RequestInput> inputs=new List<TreatyAIGovernanceAction.RequestInput>();for(Integer i=0;i<6;i++) inputs.add(input());
        Test.startTest();List<TreatyAIGovernanceAction.ResponseOutput> outs=TreatyAIGovernanceAction.coordinate(inputs);System.assertEquals(6,outs.size());for(TreatyAIGovernanceAction.ResponseOutput out:outs) closed(out);System.assertEquals(0,Limits.getCallouts());Test.stopTest();
    }
}
