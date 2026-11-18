/** Reads only explicitly marked synthetic fixtures; no DML and no callouts. */
public with sharing class TreatyAIDemoContext {
    public class Input {
        @InvocableVariable(required=true label='Synthetic Customer ID')
        public String customerId;
    }
    public class Output {
        @InvocableVariable public String status;
        @InvocableVariable public String contextJson;
        @InvocableVariable public String explanation;
    }
    @InvocableMethod(label='Read TreatyAI Synthetic CRM Context' description='Read only whitelisted synthetic Account and Case facts in the current user security context; returns no approval.')
    public static List<Output> read(List<Input> inputs) {
        List<Output> outputs=new List<Output>();
        if(inputs==null) return outputs;
        for(Input item:inputs) {
            Output out=new Output();out.status='context_unavailable';out.contextJson='{}';out.explanation='No verified demo context; no action authorized.';
            try {
                if(inputs.size()>5 || item==null || !new Set<String>{'C-1042','C-1043'}.contains(item.customerId)) throw new ContextException('Unsupported fixture');
                String key='TREATYAI-'+item.customerId;
                List<Account> accounts=[SELECT Id,Name,AccountNumber,Description FROM Account WHERE AccountNumber=:key WITH USER_MODE LIMIT 2];
                if(accounts.size()!=1 || !accounts[0].Name.startsWith('TreatyAI DEMO - ')) throw new ContextException('Ambiguous fixture');
                Account account=accounts[0];
                Map<String,Object> facts=(Map<String,Object>)JSON.deserializeUntyped(account.Description);
                if(facts.get('synthetic')!=true || facts.get('customer_id')!=item.customerId) throw new ContextException('Untrusted fixture');
                Decimal budget=(Decimal)facts.get('shared_allowance_mad');
                if(budget==null || budget<0 || !(facts.get('marketing_consent') instanceof Boolean)) throw new ContextException('Incomplete facts');
                List<Case> cases=[SELECT Id,CaseNumber,Subject,Priority,IsClosed FROM Case WHERE AccountId=:account.Id AND Subject LIKE 'TreatyAI DEMO:%' WITH USER_MODE LIMIT 10];
                Boolean critical=false;
                for(Case complaint:cases) if(!complaint.IsClosed && complaint.Priority=='High') critical=true;
                facts.put('open_critical_case',critical);facts.put('account_id',account.Id);facts.put('account_name',account.Name);facts.put('cases',cases);
                facts.put('source','Live Salesforce query of synthetic CRM fixture');facts.put('authorization','NONE - context is not governance approval');
                out.status='synthetic_context';out.contextJson=JSON.serialize(facts);out.explanation='Live CRM read of synthetic records only; governance outcomes remain unverified.';
            } catch(Exception readFailure) { /* Fail closed without exposing record data or error details. */ }
            outputs.add(out);
        }
        return outputs;
    }
    public class ContextException extends Exception {}
}
