/**
 * Salesforce-side integration scaffold for a free Agentforce Developer Edition.
 *
 * Requires a Named Credential named TreatyAI_API pointed to an authenticated
 * HTTPS gateway. NEVER point it at the unprotected local-only development API.
 * Recommendation-only adapter; no Salesforce business records are mutated.
 * Gateway must enforce principal identity, customer scope and tenant policy.
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
        if (requests == null) return outputs;
        for (RequestInput input : requests) {
            ResponseOutput output = new ResponseOutput();
            output.status = 'not_executed';
            output.verified = false;
            output.decisionId = '';
            output.receiptHash = '';
            output.explanation = 'No verified decision was returned.';

            try {
                // Bound synchronous latency and reject the whole oversized batch before callouts.
                if (requests.size() > 5 || Limits.getCallouts() >= Limits.getLimitCallouts()) {
                    throw new TreatyAIContractException('Callout capacity exceeded.');
                }
                if (input == null || String.isBlank(input.scenarioId)
                    || String.isBlank(input.customerId)
                    || String.isBlank(input.decisionContractJson)) {
                    throw new TreatyAIContractException('Required fields are missing.');
                }

                if (input.scenarioId.length() > 64 || input.customerId.length() > 64
                    || !Pattern.matches('[A-Za-z0-9_.:-]{3,64}', input.customerId)
                    || input.decisionContractJson.length() > 100000) {
                    throw new TreatyAIContractException('Invalid input bounds.');
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
                List<Object> proposals = (List<Object>) contract.get('proposals');
                if (proposals.isEmpty() || proposals.size() > 20) {
                    throw new TreatyAIContractException('Invalid proposal count.');
                }
                Set<String> proposalIds = new Set<String>();
                Set<String> keys = new Set<String>();
                for (Object item : proposals) {
                    Map<String, Object> proposal = (Map<String, Object>) item;
                    String proposalId = (String) proposal.get('proposal_id');
                    String key = (String) proposal.get('idempotency_key');
                    if (proposal.get('customer_id') != input.customerId
                        || String.isBlank(proposalId) || String.isBlank(key)
                        || !proposalIds.add(proposalId) || !keys.add(key)) {
                        throw new TreatyAIContractException('Invalid scope or duplicate identifiers.');
                    }
                }
                // These inputs are not identity proof; the gateway must authorize them.
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
                    String status = (String) result.get('status');
                    String decisionId = (String) result.get('decision_id');
                    String hash = receipt == null ? null : (String) receipt.get('receipt_hash');
                    if (!new Set<String>{'committed', 'awaiting_human', 'no_action', 'halted'}.contains(status)
                        || String.isBlank(decisionId) || String.isBlank(hash)
                        || !Pattern.matches('[a-fA-F0-9]{64}', hash)
                        || result.get('customer_id') != input.customerId
                        || result.get('scenario_id') != input.scenarioId
                        || receipt.get('decision_id') != decisionId
                        || receipt.get('customer_id') != input.customerId
                        || receipt.get('scenario_id') != input.scenarioId
                        || receipt.get('status') != status) {
                        throw new TreatyAIContractException('Incomplete or mismatched receipt.');
                    }
                    output.status = status;
                    output.verified = verification != null
                        && (Boolean) verification.get('passed') == true
                        && status == 'committed';
                    output.decisionId = String.valueOf(result.get('decision_id'));
                    output.receiptHash = receipt == null
                        ? '' : String.valueOf(receipt.get('receipt_hash'));
                    output.explanation = output.verified
                        ? 'Backend reports verification of synthetic state only; no Salesforce action executed. Receipt hash is not independently authenticated here.'
                        : 'The independent verifier did not approve the plan.';
                }
            } catch (Exception integrationFailure) {
                // Do not leak payload contents, authentication details or stack traces.
                output.status = 'integration_error';
                output.verified = false;
                output.decisionId = '';
                output.receiptHash = '';
                output.explanation = 'TreatyAI integration failed closed; no Salesforce side effects.';
            }
            outputs.add(output);
        }
        return outputs;
    }

    public class TreatyAIContractException extends Exception {}
}
