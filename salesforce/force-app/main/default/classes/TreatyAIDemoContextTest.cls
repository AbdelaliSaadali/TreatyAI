@IsTest
private class TreatyAIDemoContextTest {
    static Account seed(String customer,Boolean consent) {
        Account a=new Account(Name='TreatyAI DEMO - Test Synthetic',AccountNumber='TREATYAI-'+customer,Description=JSON.serialize(new Map<String,Object>{'synthetic'=>true,'customer_id'=>customer,'shared_allowance_mad'=>150,'marketing_consent'=>consent}));insert a;
        insert new Case(AccountId=a.Id,Subject='TreatyAI DEMO: Test complaint',Status='New',Origin='Web',Priority='High');return a;
    }
    static TreatyAIDemoContext.Output read(String idValue) { TreatyAIDemoContext.Input x=new TreatyAIDemoContext.Input();x.customerId=idValue;return TreatyAIDemoContext.read(new List<TreatyAIDemoContext.Input>{x})[0]; }
    @IsTest static void readsLiveFixtureAndCase() {
        seed('C-1042',true);Test.startTest();TreatyAIDemoContext.Output out=read('C-1042');Test.stopTest();
        System.assertEquals('synthetic_context',out.status);Map<String,Object> facts=(Map<String,Object>)JSON.deserializeUntyped(out.contextJson);
        System.assertEquals(true,facts.get('open_critical_case'));System.assertEquals(150,facts.get('shared_allowance_mad'));System.assertEquals(true,facts.get('marketing_consent'));System.assert(out.explanation.contains('unverified'));
    }
    @IsTest static void readsWithdrawnConsentWithoutApproval() { seed('C-1043',false);Map<String,Object> facts=(Map<String,Object>)JSON.deserializeUntyped(read('C-1043').contextJson);System.assertEquals(false,facts.get('marketing_consent'));System.assertEquals('NONE - context is not governance approval',facts.get('authorization')); }
    @IsTest static void unknownCustomerRejected() { Test.startTest();System.assertEquals('context_unavailable',read('C-9999').status);System.assertEquals(0,Limits.getQueries());Test.stopTest(); }
    @IsTest static void missingFixtureRejected() {System.assertEquals('context_unavailable',read('C-1042').status);}
    @IsTest static void unmarkedFixtureRejected() {Account a=seed('C-1042',true);a.Description='{"synthetic":false,"customer_id":"C-1042"}';update a;System.assertEquals('{}',read('C-1042').contextJson);}
    @IsTest static void duplicateFixtureRejected() {seed('C-1042',true);seed('C-1042',true);System.assertEquals('context_unavailable',read('C-1042').status);}
    @IsTest static void nullAndOversizedInput() {System.assertEquals(0,TreatyAIDemoContext.read(null).size());List<TreatyAIDemoContext.Input> xs=new List<TreatyAIDemoContext.Input>();for(Integer i=0;i<6;i++){TreatyAIDemoContext.Input x=new TreatyAIDemoContext.Input();x.customerId='C-1042';xs.add(x);}Test.startTest();for(TreatyAIDemoContext.Output out:TreatyAIDemoContext.read(xs))System.assertEquals('context_unavailable',out.status);System.assertEquals(0,Limits.getQueries());Test.stopTest();}
}
