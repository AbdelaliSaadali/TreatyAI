/**
 * Salesforce-side integration scaffold for a free Agentforce Developer Edition.
 *
 * Requires a Named Credential named TreatyAI_API pointed to an authenticated
 * HTTPS gateway. NEVER point it at the unprotected local-only development API.
 * This Apex source is NOT deployed or Salesforce-compiled yet.
 */
public with sharing class TreatyAIGovernanceAction {
    public class RequestInput {
        @InvocableVariable(
            label='Scenario Identifier'
            description='Business scenario identifier, for audit.'
            required=true
        )
        public String scenarioId;

        @InvocableVariable(
            label='Customer Identifier'
            description='Authorized customer identifier. Must be validated by integration policy.'
            required=true
        )
        public String customerId;

        @InvocableVariable(
            label='Decision Contract Batch JSON'
            description='Typed proposals in TreatyAI DecisionBatch format. The gateway validates all fields.'
            required=true
        )
        public String decisionContractJson;
    }

    public class ResponseOutput {
        @InvocableVariable(label='Decision Status')
        public String status;

        @InvocableVariable(label='Verifier Passed')
        public Boolean verified;

        @InvocableVariable(label='Decision Identifier')
        public String decisionId;

        @InvocableVariable(label='Receipt Hash')
        public String receiptHash;

        @InvocableVariable(label='Explanation')
        public String explanation;
    }

    @InvocableMethod(
        label='Coordinate Agent Decisions with TreatyAI'
        description='Submit typed business agent intentions for independent policy verification and a governance receipt.'
        callout=true
    )
    public static List<ResponseOutput> coordinate(List<RequestInput> requests) {
        List<ResponseOutput> outputs = new List<ResponseOutput>();
        for (RequestInput input : requests) {
            ResponseOutput output = new ResponseOutput();
            output.status = 'not_executed';
            output.verified = false;
            output.decisionId = '';
            output.receiptHash = '';
            output.explanation = 'No verified decision was returned.';

            try {
                if (input == null || String.isBlank(input.scenarioId)
                    || String.isBlank(input.customerId)
                    || String.isBlank(input.decisionContractJson)) {
                    throw new TreatyAIContractException('Required fields are missing.');
                }

                Object decoded = JSON.deserializeUntyped(input.decisionContractJson);
                if (!(decoded instanceof Map<String, Object>)) {
                    throw new TreatyAIContractException('Contract must be a JSON object.');
                }
                Map<String, Object> contract = (Map<String, Object>) decoded;
                if (!contract.containsKey('proposals')
                    || !(contract.get('proposals') instanceof List<Object>)) {
                    throw new TreatyAIContractException('Contract must contain proposal list.');
                }
                // Source customer/scenario IDs from the action inputs, not the model body.
                contract.put('scenario_id', input.scenarioId);
                contract.put('customer_id', input.customerId);

                HttpRequest request = new HttpRequest();
                request.setEndpoint('callout:TreatyAI_API/api/decisions/coordinate');
                request.setMethod('POST');
                request.setHeader('Content-Type', 'application/json');
                request.setTimeout(15000);
                request.setBody(JSON.serialize(contract));

                HttpResponse response = new Http().send(request);
                if (response.getStatusCode() != 200) {
                    output.status = 'provider_error';
                    output.explanation = 'Governance service did not return an approval. HTTP '
                        + String.valueOf(response.getStatusCode()) + '.';
                } else {
                    Map<String, Object> result =
                        (Map<String, Object>) JSON.deserializeUntyped(response.getBody());
                    Map<String, Object> verification =
                        (Map<String, Object>) result.get('verification');
                    Map<String, Object> receipt =
                        (Map<String, Object>) result.get('receipt');
                    output.status = String.valueOf(result.get('status'));
                    output.verified = verification != null
                        && (Boolean) verification.get('passed') == true;
                    output.decisionId = String.valueOf(result.get('decision_id'));
                    output.receiptHash = receipt == null
                        ? '' : String.valueOf(receipt.get('receipt_hash'));
                    output.explanation = output.verified
                        ? 'Verified locally; inspect the full receipt in TreatyAI.'
                        : 'The independent verifier did not approve the plan.';
                }
            } catch (Exception exception) {
                // Do not leak payload contents, authentication details or stack traces.
                output.status = 'integration_error';
                output.verified = false;
                output.explanation = 'TreatyAI integration failed closed; no Salesforce side effects.';
            }
            outputs.add(output);
        }
        return outputs;
    }

    public class TreatyAIContractException extends Exception {}
}
