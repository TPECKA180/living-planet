import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store
from planet.local_execution import prepare_locally
from planet.world_history import write_history
from planet.intelligence import normalize_decision
from planet.execution_ai import preview_orders

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=24,count=2);self.w.day=1;self.a,self.b=self.w.states
        for s in self.w.states:s.stocks.update(money=5000,metal=2000,food=2000,resource=2000)
    def decision(self):return dict(owner=self.a.id,thinking='Расчёт',notes=self.a.notes,plan=self.a.plan,actions=[],diplomacy=[])
    def test_selected_military_order_recruits_and_pays_once(self):
        option=self.w.context(self.a)['military']['recruitment_options'][0];order=option['action'];d=self.decision()
        d['military_response']=dict(choice='mobilize',reason='Нужна армия для наступления.',orders=[order,order],revisit_day=2)
        before=self.a.stocks.copy();count=len(self.w.units);fixed=prepare_locally(self.w,self.a,d,{})
        self.assertEqual(len(fixed['actions']),1);self.w.apply_decision(self.a,fixed)
        self.assertEqual(len(self.w.units),count+1)
        for k,v in option['cost'].items():self.assertEqual(before[k]-self.a.stocks[k],v)
        self.assertGreaterEqual(option['max_count'],1)
    def test_army_creation_alias_is_unambiguous(self):
        d=self.decision();d['actions']=[dict(type='army',args=dict(cell=self.w.positions(self.a.id)[0],strength=3))]
        self.assertEqual(normalize_decision(d,self.w.context(self.a))['actions'][0]['type'],'unit')
        d['actions']=[dict(type='army',args=dict(unit_id=1,target_cell=[2,2]))]
        self.assertEqual(normalize_decision(d,self.w.context(self.a))['actions'][0]['type'],'army')
    def test_selected_trade_template_really_transfers(self):
        self.w.execute(self.b,dict(type='trade',args=dict(partner=self.a.id,resource='metal',amount=5,price=2)))
        context=self.w.context(self.a);option=next(o for o in context['commerce']['order_templates'] if o['action']['type']=='accept_trade')
        d=self.decision();d['economic_review']=dict(mode='execute',reason='Нужен металл',orders=[option['action']]);before=self.a.stocks.copy();other=self.b.stocks.copy()
        fixed=prepare_locally(self.w,self.a,d,{},own_context=context);self.w.apply_decision(self.a,fixed)
        self.assertEqual(self.a.stocks['metal'],before['metal']+5);self.assertEqual(self.a.stocks['money'],before['money']-10)
        self.assertEqual(self.b.stocks['money'],other['money']+10);self.assertTrue(self.w.settlements)
    def test_letters_and_hold_do_not_create_free_actions(self):
        d=self.decision();d['diplomacy']=[dict(to=self.b.id,text='Пришлю металл и создам армию')];d['military_response']=dict(choice='hold',reason='Ждём',orders=[])
        fixed=prepare_locally(self.w,self.a,d,{});self.assertEqual(fixed['actions'],[])
    def test_treasury_gets_last_slot_before_extra_construction(self):
        d=self.decision();u=self.w.units[0];d['actions']=[dict(type='hold',args=dict(unit_id=u['id'])) for _ in range(11)]
        d['economic_review']=dict(mode='execute',orders=[dict(type='transfer',args=dict(partner=self.b.id,resource='money',amount=1))])
        p=self.w.context(self.a)['construction']['projects'][0];d['construction_review']=dict(choice='build',project_id=p['project_id'])
        fixed=prepare_locally(self.w,self.a,d,{});self.assertEqual(len(fixed['actions']),12);self.assertEqual(fixed['actions'][-1]['type'],'transfer')
    def test_offensive_option_captures_without_global_superiority(self):
        self.w.units=[]
        for c in self.w.cells:c.terrain='water';c.owner=None;c.population=0;c.building=None;c.wall_hp=None
        for x in (1,2,3):
            c=self.w.cell([x,2]);c.terrain='grass';c.owner=self.a.id if x==1 else self.b.id
        self.w.spawn(self.a.id,[1,2],'army',5);before=copy.deepcopy(self.w.data())
        option=self.w.context(self.a)['military']['offensive_options'][0]
        self.assertTrue(option['opportunity']);self.assertEqual(self.w.data(),before)
        d=self.decision();d['military_response']=dict(choice='maneuver',reason='Захват приграничной территории',orders=option['orders'])
        self.w.apply_decision(self.a,prepare_locally(self.w,self.a,d,{}))
        self.assertTrue(self.w.at_war(self.a.id,self.b.id));self.assertEqual(self.w.cell([2,2]).owner,self.a.id)
    def test_empty_preview_does_not_clone(self):
        with patch.object(World,'restore',side_effect=AssertionError('No clone')):self.assertEqual(preview_orders(self.w,self.a.id,dict(actions=[]))['failed'],0)
    def test_history_factual_idempotent_persistent_and_observer_only(self):
        self.assertIsNone(write_history(self.w));self.w.day=10
        self.a.notes='СЕКРЕТНЫЙ ПЛАН';page=write_history(self.w)
        self.assertEqual(page['facts']['enemy_cells_captured'],0);self.assertNotIn(self.a.notes,page['text']);self.assertIsNone(write_history(self.w))
        self.assertEqual(World.restore(self.w.data()).history_book,[page]);self.assertNotIn('history_book',self.w.context(self.a))
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'world.sqlite3',export=True);store.save(self.w);self.assertEqual(store.load().history_book,[page]);self.assertTrue((Path(folder)/'history_book.json').is_file())
    def test_history_uses_real_movement_and_settlement_counts(self):
        self.w.day=20;self.w.movement_log=[dict(day=11,captured=True,owner=self.a.id,previous_owner=self.b.id),dict(day=10,captured=True,owner=self.a.id,previous_owner=self.b.id)]
        self.w.settlements=[dict(day=20),dict(day=5)];page=write_history(self.w)
        self.assertEqual(page['facts']['enemy_cells_captured'],1);self.assertEqual(page['facts']['receipts'],1);self.assertEqual(page['from_day'],11)

if __name__=='__main__':unittest.main()
