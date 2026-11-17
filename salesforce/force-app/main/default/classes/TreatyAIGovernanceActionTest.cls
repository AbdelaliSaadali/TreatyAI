@IsTest
private class TreatyAIGovernanceActionTest {
    private class TreatyAIMock implements HttpCalloutMock {
        public HTTPResponse respond(HTTPRequest req) {
            System.assertEquals('POST', req.getMethod());
            System.assertEquals(
                'callout:TreatyAI_API/api/decisions/coordinate',
                req.getEndpoint()
            );
            Map<String, Object> body =
                (Map<String, Object>) JSON.deserializeUntyped(req.getBody());
            System.assertEquals('C-1042', body.get('customer_id'));

            HttpResponse res = new HttpResponse();
            res.setStatusCode(200);
            res.setHeader('Content-Type', 'application/json');
            res.setBody(
                '{"status":"committed","decision_id":"DEC-TEST","verification":{"passed":true},'
                + '"receipt":{"receipt_hash":"test-receipt-hash"}}'
            );
            return res;
        }
    }

    @IsTest
    static void testSuccessfulGovernanceCallout() {
        Test.setMock(HttpCalloutMock.class, new TreatyAIMock());
        TreatyAIGovernanceAction.RequestInput input =
            new TreatyAIGovernanceAction.RequestInput();
        input.scenarioId = 'customer-journey';
        input.customerId = 'C-1042';
        input.decisionContractJson =
            '{"proposals":[{"proposal_id":"TEST-PROP-1"}]}';

        Test.startTest();
        List<TreatyAIGovernanceAction.ResponseOutput> results =
            TreatyAIGovernanceAction.coordinate(
                new List<TreatyAIGovernanceAction.RequestInput>{input}
            );
        Test.stopTest();

        System.assertEquals(1, results.size());
        System.assertEquals('committed', results[0].status);
        System.assertEquals(true, results[0].verified);
        System.assertEquals('DEC-TEST', results[0].decisionId);
        System.assertEquals('test-receipt-hash', results[0].receiptHash);
    }

    @IsTest
    static void testInvalidInputFailsClosed() {
        TreatyAIGovernanceAction.RequestInput input =
            new TreatyAIGovernanceAction.RequestInput();
        input.scenarioId = 'customer-journey';
        input.customerId = 'C-1042';
        input.decisionContractJson = 'not-json';

        List<TreatyAIGovernanceAction.ResponseOutput> results =
            TreatyAIGovernanceAction.coordinate(
                new List<TreatyAIGovernanceAction.RequestInput>{input}
            );
        System.assertEquals('integration_error', results[0].status);
        System.assertEquals(false, results[0].verified);
    }
}
