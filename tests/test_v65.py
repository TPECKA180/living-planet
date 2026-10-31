import copy,unittest
from unittest.mock import patch
from planet.engine import World,RuleError,PRICES
from planet.brain import Brain
from planet.military_ai import validate_military
from planet.decision_format import decision_schema

class WarRecruitmentTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2);self.w.day=1;self.s,self.peer=self.w.states
        self.s.stocks.update(money=10000,metal=1000,resource=1000,food=1000)
        self.w.set_war(self.s.id,self.peer.id,'Проверка военных приказов')
        self.ctx=self.w.context(self.s)
    def decision(self,actions=None,choice='mobilize'):
        return dict(owner=self.s.id,origin_patch='6.4',thinking='Реально готовим оборону страны.',notes=self.s.notes,plan=self.s.plan,
                    actions=actions or [],diplomacy=[dict(to=self.peer.id,text='Предлагаем конкретные условия прекращения огня.')],
                    military_response=dict(choice=choice,reason='Нанимаем настоящую армию на свободной своей клетке для обороны.',revisit_day=self.w.day+1))
    def test_wartime_regular_recruitment_really_spawns_army_and_pays(self):
        option=self.ctx['military']['recruitment_options'][-1];before=self.s.stocks.copy();count=len(self.w.units)
        self.w.execute(self.s,option['action'])
        self.assertEqual(len(self.w.units),count+1);self.assertEqual(self.w.units[-1]['type'],'army')
        for key,cost in option['cost'].items():self.assertEqual(before[key]-self.s.stocks[key],cost)
    def test_army_action_is_movement_and_never_creates_army(self):
        before=len(self.w.units)
        with self.assertRaises(RuleError):self.w.execute(self.s,dict(type='army',args=dict(cell=self.w.positions(self.s.id)[0],strength=5)))
        self.assertEqual(before,len(self.w.units))
    def test_scouts_do_not_count_as_combat_armies(self):self.assertEqual(self.ctx['military']['combat_count'],0)
    def test_declaring_new_war_requires_real_military_response_too(self):
        self.w.wars=[];ctx=self.w.context(self.s)
        d=self.decision([dict(type='declare_war',args=dict(partner=self.peer.id,reason='Проверка объявления войны'))]);d.pop('military_response')
        with self.assertRaises(ValueError):validate_military(d,ctx)
    def test_conscripton_price_matches_executable_recruitment(self):
        self.s.tech.append('conscription');option=self.w.context(self.s)['military']['recruitment_options'][0]
        self.assertEqual(option['cost']['money'],45);before=self.s.stocks['money'];self.w.execute(self.s,option['action']);self.assertEqual(before-self.s.stocks['money'],45)
    def test_recruitment_strength_limits_respect_army_technology(self):
        self.assertEqual(max(o['action']['args']['strength'] for o in self.ctx['military']['recruitment_options']),5)
        self.s.tech.append('army');ctx=self.w.context(self.s)
        self.assertEqual(max(o['action']['args']['strength'] for o in ctx['military']['recruitment_options']),10)
    def test_war_stops_automatic_scout_spending(self):
        self.s.operations.update(explore=False,recruit=True,unit_limit=50,reserve_money=0)
        self.w.units=[u for u in self.w.units if u['owner']!=self.s.id]
        before=self.s.stocks.copy();self.w.run_operations()
        self.assertFalse(any(u['owner']==self.s.id and u['type']=='scout' for u in self.w.units))
        self.assertFalse(any(u['owner']==self.s.id and u['type']=='army' for u in self.w.units));self.assertEqual(before,self.s.stocks)
    def test_peaceful_scout_service_still_recruits(self):
        self.w.wars=[];self.s.operations.update(explore=False,recruit=True,unit_limit=50,reserve_money=0)
        self.w.units=[u for u in self.w.units if u['owner']!=self.s.id];self.w.run_operations()
        self.assertTrue(any(u['owner']==self.s.id and u['type']=='scout' for u in self.w.units))
    def test_promise_or_scout_hire_does_not_satisfy_mobilization(self):
        with self.assertRaises(ValueError):validate_military(self.decision(),self.ctx)
        action=copy.deepcopy(self.ctx['military']['recruitment_options'][0]['action']);action['args']['unit']='scout'
        with self.assertRaises(ValueError):validate_military(self.decision([action]),self.ctx)
    def test_wartime_schema_requires_military_response_only_when_at_war(self):
        schema=decision_schema(self.s,self.ctx,PRICES)['json_schema']['schema']
        self.assertIn('military_response',schema['required'])
        self.w.wars=[];schema=decision_schema(self.s,self.w.context(self.s),PRICES)['json_schema']['schema']
        self.assertNotIn('military_response',schema['properties'])
    def test_empty_war_promise_gets_only_orders_repaired_and_real_army_is_created(self):
        d=self.decision();d.pop('military_response');brain=Brain(dict(decision_repair_attempts=1))
        update=dict(actions=[self.ctx['military']['recruitment_options'][0]['action']],
                    construction_review=dict(choice='defer',project_id=None,reason='Во время войны средства направлены в боевое формирование.',revisit_day=self.w.day+1),
                    economic_review=dict(mode='none',reason='Для найма хватает собственных средств, переводы не нужны.',orders=[]),
                    military_response=self.decision()['military_response'])
        with patch.object(brain,'complete',return_value=update) as complete:fixed=brain.prepare_execution(self.w,self.s,d)
        self.assertEqual(complete.call_count,1)
        for key in ('notes','plan','thinking','diplomacy'):self.assertEqual(d[key],fixed[key])
        self.w.apply_decision(self.s,fixed)
        self.assertTrue(any(u['owner']==self.s.id and u['type']=='army' for u in self.w.units))
    def test_concrete_deferral_when_broke_does_not_force_free_army(self):
        self.s.stocks['money']=0;self.s.stocks['metal']=0;d=self.decision(choice='defer')
        d['military_response']['reason']='Денег и металла нет; сохраняем позиции, закупку планируем после дохода завтра.'
        brain=Brain({});before=self.w.data()
        with patch.object(brain,'complete',side_effect=AssertionError('No forced new model request')):fixed=brain.prepare_execution(self.w,self.s,d)
        self.assertEqual(fixed['actions'],[]);self.assertEqual(before,self.w.data())
    def test_border_wall_and_tower_options_prioritize_enemy_border(self):
        p=next(p for p in self.w.positions(self.s.id) if not self.w.cell(p).building and self.w.cell(p).terrain!='water')
        q=next(q for q in self.w.adjacent(p) if self.w.cell(q).terrain!='water');self.w.cell(q).owner=self.peer.id
        options=[p for p in self.w.construction_context(self.s)['projects'] if p['building'] in ('wall','tower')]
        self.assertTrue(options)
        for option in options:
            self.assertEqual(option['priority'],115)
            self.assertTrue(any(self.w.cell(q).owner==self.peer.id for q in self.w.adjacent(option['cell'])))
    def test_recruitment_sites_exclude_radiation(self):
        p=self.ctx['military']['recruitment_sites'][0];self.w.cell(p).radiation=20
        self.assertNotIn(p,self.w.recruitment_sites(self.s))
        with self.assertRaises(RuleError):self.w.execute(self.s,dict(type='unit',args=dict(cell=p,unit='army',strength=1)))
    def test_modern_recruitment_templates_match_real_cost_and_crew(self):
        from planet.modern_catalog import TECHNOLOGIES,MODERN_RESOURCES
        self.s.tech.extend(TECHNOLOGIES);self.s.era=2
        self.s.stocks.update({k:10**9 for k in list(self.s.stocks)+list(MODERN_RESOURCES)})
        p=self.w.positions(self.s.id)[0];self.w.cell(p).population=10000
        options=[o for o in self.w.context(self.s)['military']['recruitment_options'] if o['action']['type']=='recruit_modern']
        self.assertTrue(options);option=options[0];before=self.s.stocks.copy()
        self.w.execute(self.s,option['action'])
        for key,cost in option['cost'].items():self.assertEqual(before[key]-self.s.stocks[key],cost)
        self.assertEqual(self.w.units[-1]['crew'],option['crew'])

if __name__=='__main__':unittest.main()
