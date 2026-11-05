import copy,json,tempfile,unittest
from pathlib import Path
from planet.engine import World,Store,RuleError
from planet.intelligence import action_schema,CONTRACTS
from planet.decision_format import decision_schema
from planet.prompt_packing import shared_schema
from planet.modern_catalog import RESOURCE_NAMES,TECHNOLOGIES
from planet.local_execution import prepare_locally

class PopulationAndTrade756(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2);self.s,self.b=self.w.states
        for s in self.w.states:s.operations.update(recruit=False,explore=False)
        self.own=self.w.positions(self.s.id)
    def population(self):return sum(self.w.cell(p).population for p in self.own)
    def modern(self):
        self.s.tech=list(TECHNOLOGIES);self.s.era=2;self.s.modern=dict(entered_day=0,unrest=0,debt=0)
        self.s.stocks.update(dict.fromkeys(RESOURCE_NAMES,1000000))
    def test_fractional_growth_survives_sqlite_and_credits_exactly_once(self):
        # 3 -> 3 -> 3 -> 3 -> 4, carrying .3/.6/.9/.2.
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.sqlite3')
            for day,expected in enumerate((3,3,3,4),1):
                self.w.day=day;self.w.passive_population_growth(self.s)
                self.assertEqual(self.population(),expected)
                before=self.w.data();self.w.passive_population_growth(self.s);self.assertEqual(self.w.data(),before)
                store.save(self.w);self.w=store.load();self.s=self.w.states[0]
            self.assertEqual(self.s.modern['growth_remainder_tenths'],2)
    def test_growth_places_at_most_capacity_and_never_water_or_radiation(self):
        self.modern()
        for p in self.own:self.w.cell(p).population=20
        self.w.cell(self.own[0]).terrain='water';self.w.cell(self.own[0]).population=0
        self.w.cell(self.own[1]).radiation=100;self.w.cell(self.own[1]).population=0
        before=self.population();self.w.passive_population_growth(self.s)
        self.assertEqual(self.population(),before)
        self.assertGreater(self.s.modern['last_population_growth']['blocked_by_housing'],0)
        self.w.cell(self.own[2]).population=0;self.w.day+=1;self.w.passive_population_growth(self.s)
        self.assertEqual(self.w.cell(self.own[2]).population,20)
        self.assertEqual(self.w.cell(self.own[0]).population,0);self.assertEqual(self.w.cell(self.own[1]).population,0)
    def test_modern_zero_population_can_use_paid_campaign_without_loading_injection(self):
        self.modern()
        for p in self.own:self.w.cell(p).population=0
        restored=World.restore(self.w.data());self.assertEqual(sum(c.population for c in restored.cells if c.owner==self.s.id),0)
        status=self.w.population_status(self.s);self.assertTrue(status['recovery_orders'][0]['affordable'])
        before=dict(self.s.stocks);self.w.execute(self.s,status['recovery_orders'][0]['action'])
        self.assertEqual(self.population(),100)
        for k,v in dict(money=2500,food=4000,resource=500).items():self.assertEqual(self.s.stocks[k],before[k]-v)
    def test_modern_paid_small_settlement_recovers_zero_but_first_era_still_needs_two(self):
        for p in self.own:self.w.cell(p).population=0
        action=dict(type='settle',args=dict(cell=self.own[0],amount=2))
        self.assertRaises(RuleError,self.w.execute,self.s,action)
        self.modern();before=dict(self.s.stocks);self.w.execute(self.s,action)
        self.assertEqual(self.population(),2);self.assertEqual(self.s.stocks['money'],before['money']-100)
    def test_fractional_crisis_does_not_round_one_death_per_sparse_cell(self):
        self.modern();self.s.tech.remove('environmental_recovery');self.w.day=10
        self.s.stocks.update(water=0,medicine=0,consumer_goods=0)
        # 3 single residents with 8% mortality: .24 accumulated, not all three killed.
        self.w.modern_income(self.s);self.assertEqual(self.population(),3)
        self.assertAlmostEqual(self.s.modern['mortality_remainder'],.24)
        self.w.day+=1;self.w.modern_income(self.s);self.assertEqual(self.population(),3)
        self.assertAlmostEqual(self.s.modern['mortality_remainder'],.48)
    def test_schema_partner_enum_never_contaminates_resource_reason_or_global_contract(self):
        ctx=dict(state=self.s.id,states=[dict(id=s.id) for s in self.w.states])
        for kind in ('trade','transfer','offer_exchange','supply_pact','pledge','relationship'):
            args=action_schema([kind],ctx)['anyOf'][0]['properties']['args']['properties']
            self.assertEqual(args['partner']['enum'],[self.b.id])
            for key in ('resource','reason','memo','mode','kind'):
                if key in args:self.assertNotIn('enum',args[key])
        self.assertNotIn('enum',CONTRACTS['trade'][0]['resource'])
    def test_local_preparation_and_real_secure_trade_move_both_balances_once(self):
        decision=dict(thinking='Предлагаем реальную продажу.',actions=[],economic_review=dict(mode='execute',reason='Выгодная продажа реального металла.',orders=[dict(type='trade',args=dict(partner=self.b.id,resource='metal',amount=5,price=2))]))
        ready=prepare_locally(self.w,self.s,decision,{})
        self.assertEqual(ready['execution_preflight']['failed'],0)
        before=[dict(s.stocks) for s in self.w.states]
        for action in ready['actions']:self.w.execute(self.s,action)
        self.assertEqual(self.s.stocks,before[0]);self.assertEqual(self.b.stocks,before[1])
        self.w.execute(self.b,dict(type='accept_trade',args=dict(offer_id=1)))
        self.assertEqual(self.s.stocks['metal'],before[0]['metal']-5);self.assertEqual(self.b.stocks['metal'],before[1]['metal']+5)
        self.assertEqual(self.s.stocks['money'],before[0]['money']+10);self.assertEqual(self.b.stocks['money'],before[1]['money']-10)
        after=self.w.data();self.assertRaises(RuleError,self.w.execute,self.b,dict(type='accept_trade',args=dict(offer_id=1)));self.assertEqual(self.w.data(),after)
        self.assertEqual(len(self.w.settlements),2)
    def test_income_applies_passive_growth_both_eras_and_deactivated_country_cannot_grow(self):
        self.modern();self.w.cell(self.own[0]).building='housing_block';self.w.cell(self.own[0]).population=100;self.w.day=1
        before=self.population();self.w.income();self.assertEqual(self.population(),before+before//10)
        self.s.eliminated=True;self.w.day+=1;before=self.population();self.w.passive_population_growth(self.s);self.assertEqual(self.population(),before)

if __name__=='__main__':unittest.main()
