import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store
from planet.local_execution import prepare_locally
from planet.local_chronicle import chapter_event
from planet.runtime_config import upgrade_config
from main import Runner

class LocalExecutionTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2);self.w.day=1;self.s,self.peer=self.w.states
        self.s.stocks.update(money=2000,resource=1000,food=500,science=1000,metal=1000)
    def decision(self,actions=None):return dict(owner=self.s.id,thinking='План развития.',notes=self.s.notes,plan=self.s.plan,actions=actions or [],diplomacy=[])
    def project(self):return next(p for p in self.w.context(self.s)['construction']['projects'] if p['building']=='castle' and p['level']==1)
    def test_short_reason_does_not_require_model_and_selected_build_really_pays(self):
        project=self.project();d=self.decision();d['construction_review']=dict(choice='build',project_id=project['project_id'],reason='ок',revisit_day=1)
        before=self.s.stocks['money'];fixed=prepare_locally(self.w,self.s,d,{})
        self.w.apply_decision(self.s,fixed);self.assertEqual(self.w.cell(project['cell']).building,'castle');self.assertEqual(before-self.s.stocks['money'],200)
        self.assertEqual(fixed['construction_review']['reason'],'ок')
    def test_bare_promise_does_not_choose_project_or_create_free_building(self):
        d=self.decision();d['construction_review']=dict(choice='build',project_id=None,reason='')
        fixed=prepare_locally(self.w,self.s,d,{});self.assertEqual(fixed['actions'],[]);self.assertTrue(fixed['local_preparation']['issues'])
    def test_unaffordable_order_is_rejected_by_engine_without_payment(self):
        p=self.project();self.s.stocks['money']=10;d=self.decision([dict(type='build',args=dict(cell=p['cell'],building='castle',level=1))])
        fixed=prepare_locally(self.w,self.s,d,{});before=self.s.stocks.copy();self.w.apply_decision(self.s,fixed)
        self.assertEqual(before,self.s.stocks);self.assertEqual(self.s.decision_outcome['accepted'],0);self.assertEqual(len(self.s.decision_outcome['rejected']),1)
    def test_honest_orders_compiled_once_even_without_prose(self):
        order=dict(type='transfer',args=dict(partner=self.peer.id,resource='money',amount=10));d=self.decision([order])
        d['economic_review']=dict(mode='execute',reason='',orders=[order]);before=self.peer.stocks['money']
        fixed=prepare_locally(self.w,self.s,d,{});self.assertEqual(len(fixed['actions']),1);self.w.apply_decision(self.s,fixed);self.assertEqual(self.peer.stocks['money']-before,10)
    def test_deceptive_letters_do_not_manufacture_transfer(self):
        d=self.decision();d['diplomacy']=[dict(to=self.peer.id,text='Обещаем отправить деньги.')];d['economic_review']=dict(mode='deceive',reason='',orders=[])
        fixed=prepare_locally(self.w,self.s,d,{});self.assertEqual(fixed['actions'],[])
    def test_real_risk_acknowledgement_is_not_replaced_with_a_fabricated_reason(self):
        self.s.stocks['food']=10
        for p in self.w.positions(self.s.id):self.w.cell(p).terrain='mountain'
        d=self.decision([dict(type='transfer',args=dict(partner=self.peer.id,resource='food',amount=10,allow_risk=True,reason=''))])
        fixed=prepare_locally(self.w,self.s,d,{});before=self.s.stocks.copy();self.w.apply_decision(self.s,fixed)
        self.assertTrue(self.s.decision_outcome['rejected']);self.assertEqual(before,self.s.stocks)
    def test_overflow_does_not_silently_replace_existing_orders(self):
        unit=next(u for u in self.w.units if u['owner']==self.s.id);d=self.decision([dict(type='hold',args=dict(unit_id=unit['id'])) for _ in range(12)])
        d['construction_review']=dict(choice='build',project_id=self.project()['project_id'],reason='')
        fixed=prepare_locally(self.w,self.s,d,{});self.assertEqual(len(fixed['actions']),12);self.assertFalse(any(a['type']=='build' for a in fixed['actions']));self.assertTrue(fixed['local_preparation']['issues'])
    def test_legacy_end_of_day_finishes_with_all_inference_methods_disabled(self):
        self.w.in_day=True;self.w.phase='preparing';self.w.cursor=2;d=self.decision();d['construction_review']=dict(choice='defer',project_id=None,reason='');self.w.pending_decisions={self.s.id:d}
        with tempfile.TemporaryDirectory() as folder:
            runner=Runner(self.w,Store(Path(folder)/'world.sqlite3'),dict(local_execution=True,deep_strategy=True,review_relations=True))
            with patch.object(runner.brain,'complete',side_effect=AssertionError('No inference')),patch.object(runner.brain,'prepare_execution',side_effect=AssertionError('No model reviewer')),patch.object(runner.brain,'russify',side_effect=AssertionError('No translator')),patch.object(runner.brain,'review_strategy',side_effect=AssertionError('No second strategy')):runner.work()
            self.assertEqual(runner.world.phase,'manager');self.assertEqual(runner.world.state(self.s.id).notes,d['notes'])
    def test_local_chapter_is_seeded_and_never_selects_a_privileged_country(self):
        self.w.day=40;self.assertEqual(chapter_event(self.w),chapter_event(World.restore(self.w.data())));self.assertIsNone(chapter_event(self.w)['target'])
    def test_manager_stage_never_asks_model_in_local_mode(self):
        self.w.day=40;self.w.phase='manager';self.w.in_day=True
        with tempfile.TemporaryDirectory() as folder:
            runner=Runner(self.w,Store(Path(folder)/'world.sqlite3'),dict(local_chronicle=True,manager_every=10))
            with patch.object(runner.brain,'manager',side_effect=AssertionError('No chapter model')):runner.work()
            self.assertEqual(runner.world.phase,'idle');self.assertFalse(runner.world.in_day);self.assertEqual(runner.world.chapter,1)
    def test_upgrade_enables_local_mode_without_resetting_user_limits(self):
        cfg=dict(runtime_patch='6.8',max_tokens=32768,context_window=98304,reflective_learning=False)
        self.assertTrue(upgrade_config(cfg));self.assertTrue(cfg['local_execution']);self.assertTrue(cfg['local_chronicle']);self.assertEqual(cfg['max_tokens'],196608);self.assertFalse(cfg['reflective_learning'])
        cfg['local_chronicle']=False;self.assertFalse(upgrade_config(cfg));self.assertFalse(cfg['local_chronicle'])

if __name__=='__main__':unittest.main()
