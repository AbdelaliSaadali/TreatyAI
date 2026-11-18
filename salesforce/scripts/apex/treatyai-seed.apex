// Synthetic CRM fixtures only. No credit, marketing or external execution.
for (Integer n=0; n<2; n++) {
    String key=n==0?'TREATYAI-C-1042':'TREATYAI-C-1043';
    List<Account> existing=[SELECT Id FROM Account WHERE AccountNumber=:key LIMIT 2];
    System.assert(existing.size()<=1,'Duplicate demo key; reconcile manually');
    if (!existing.isEmpty()) continue;
    Boolean flagship=n==0;
    String person=flagship?'Nadia El Amrani':'Youssef Bennani';
    Map<String,Object> facts=new Map<String,Object>{'synthetic'=>true,'customer_id'=>flagship?'C-1042':'C-1043','shared_allowance_mad'=>150,'marketing_consent'=>flagship,'open_critical_case'=>flagship,'communications_last_24h'=>0,'max_communications_per_24h'=>1,'state_version'=>1,'service_proposal_mad'=>100,'retention_proposal_mad'=>100,'allow_partial'=>true,'expected_simulation'=>flagship?'Service 100 MAD; retention 50 MAD; marketing deferred OPEN_CRITICAL_CASE':'Marketing rejected NO_CONSENT','verification'=>'SIMULATION ONLY - no live gateway'};
    Account a=new Account(Name='TreatyAI DEMO - '+person+' (Synthetic)',AccountNumber=key,Description=JSON.serializePretty(facts)); insert a;
    Contact c=new Contact(FirstName=flagship?'Nadia':'Youssef',LastName=flagship?'El Amrani (Synthetic)':'Bennani (Synthetic)',AccountId=a.Id,Description='Synthetic TreatyAI fixture. No real customer; never send messages.'); insert c;
    Case complaint=new Case(AccountId=a.Id,ContactId=c.Id,Subject=flagship?'TreatyAI DEMO: Unresolved critical billing complaint':'TreatyAI DEMO: Withdrawn marketing consent',Status='New',Priority='High',Origin='Web',Description=JSON.serializePretty(facts)); insert complaint;
    System.debug(LoggingLevel.INFO,'TREATYAI_SEED '+key+' Account='+a.Id+' Contact='+c.Id+' Case='+complaint.Id);
}
System.assertEquals(2,[SELECT count() FROM Account WHERE AccountNumber IN ('TREATYAI-C-1042','TREATYAI-C-1043')]);
