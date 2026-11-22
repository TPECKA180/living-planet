import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store
from planet.learning import decision_signature,ready
from planet.runtime_config import upgrade_config
from main import Runner

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=24,count=2);self.w.day=1;self.s,self.peer=self.w.states
        self.daily_patch=patch.object(self.w,'daily_rewards');self.daily_patch.start();self.addCleanup(self.daily_patch.stop)
    def test_exact_territory_rewards_and_no_repeat_after_restore(self):
        before=self.w.reward_baseline();neutral=next(c for c in self.w.cells if c.owner is None);foreign=next(c for c in self.w.cells if c.owner==self.peer.id)
        neutral.owner=self.s.id;foreign.owner=self.s.id;stocks=copy.deepcopy([s.stocks for s in self.w.states])
        self.w.settle_rewards(before);self.assertEqual(self.w.learning_record(self.s.id)['score'],.505);self.assertEqual(self.w.learning_record(self.peer.id)['score'],-1)
        restored=World.restore(self.w.data());old=restored.data();restored.settle_rewards(before);self.assertEqual(restored.data(),old)
        self.assertEqual(stocks,[s.stocks for s in self.w.states])
    def test_daily_leadership_each_resource_and_negative_net_penalty(self):
        self.daily_patch.stop();self.w.day=7
        for s in self.w.states:s.stocks={k:0 for k in s.stocks}
        self.s.stocks.update(food=100,science=30);self.peer.stocks.update(food=50,science=10)
        def forecast(s):return dict(resources=dict(food=dict(net=-1 if s.id==self.s.id else 0)))
        with patch.object(self.w,'economic_forecast',side_effect=forecast):self.w.settle_rewards(self.w.reward_baseline())
        record=self.w.learning_record(self.s.id);self.assertEqual(record['score'],1)
        self.assertEqual(sum(e['reason']=='daily_leader' for e in record['events']),2);self.assertEqual(sum(e['reason']=='daily_deficit' for e in record['events']),1)
    def test_zero_stocks_not_rewarded_and_ties_split_one_point(self):
        self.daily_patch.stop();self.w.day=7
        for s in self.w.states:s.stocks={k:0 for k in s.stocks};s.stocks['food']=10
        with patch.object(self.w,'economic_forecast',return_value=dict(resources={})):self.w.settle_rewards(self.w.reward_baseline())
        self.assertEqual([self.w.learning_record(s.id)['score'] for s in self.w.states],[.5,.5])
    def test_vassal_rewards_and_release_reacquisition_do_not_farm_points(self):
        before=self.w.reward_baseline();self.s.vassal_of=self.peer.id;self.w.settle_rewards(before)
        self.assertEqual(self.w.learning_record(self.s.id)['score'],-2);self.assertEqual(self.w.learning_record(self.peer.id)['score'],4)
        self.w.day+=1;before=self.w.reward_baseline();self.s.vassal_of=None;self.w.settle_rewards(before)
        self.assertEqual(self.w.learning_record(self.peer.id)['score'],2)
        self.w.day+=1;before=self.w.reward_baseline();self.s.vassal_of=self.peer.id;self.w.settle_rewards(before)
        self.assertEqual(self.w.learning_record(self.peer.id)['score'],2)
    def test_research_and_rejected_order_rewards(self):
        before=self.w.reward_baseline();self.s.tech.append('agriculture');self.s.decision_outcome=dict(day=1,rejected=['Отклонено: невозможно'])
        self.w.settle_rewards(before);self.assertAlmostEqual(self.w.learning_record(self.s.id)['score'],.2)
    def test_learning_context_is_private_and_notes_persist(self):
        self.w.learning_record(self.peer.id)['notes']='SECRET_FOREIGN_PLAN'
        d=dict(thinking='План',notes=self.s.notes,plan=self.s.plan,actions=[],diplomacy=[],learning_notes='Гипотеза: укрепить доход, проверить изменение дефицита завтра, сохранить военный резерв.')
        self.w.apply_decision(self.s,d);self.assertEqual(self.w.learning_record(self.s.id)['notes'],d['learning_notes'])
        self.assertNotIn('SECRET_FOREIGN_PLAN',json.dumps(self.w.context(self.s)))
        self.assertEqual(World.restore(self.w.data()).learning_record(self.s.id)['notes'],d['learning_notes'])
    def test_old_world_initialises_learning_without_touching_old_states_or_map(self):
        raw=self.w.data();raw.pop('learning');restored=World.restore(raw)
        self.assertEqual(raw['states'],restored.data()['states']);self.assertEqual(raw['cells'],restored.data()['cells']);self.assertEqual(restored.learning_record(self.s.id)['score'],0)
    def test_nullable_notes_preserve_full_previous_strategy(self):
        self.w.learning_record(self.s.id)['notes']='Полная прежняя стратегия'
        self.w.apply_decision(self.s,dict(thinking='План',notes=self.s.notes,plan=self.s.plan,actions=[],diplomacy=[],learning_notes=None))
        self.assertEqual(self.w.learning_record(self.s.id)['notes'],'Полная прежняя стратегия')

class ExecutionStageTests(unittest.TestCase):
    def decision(self,w,s):return dict(owner=s.id,thinking='Сохраняем план.',notes=s.notes,plan=s.plan,actions=[],diplomacy=[dict(to='all',text='Обсудим конкретные условия.')])
    def test_fully_prepared_round_runs_without_any_model_or_repair_call(self):
        w=World(size=24,count=2);w.day=1;w.in_day=True;w.phase='resolution';w.cursor=2
        for s in w.states:
            d=self.decision(w,s);d['execution_ready']=dict(day=w.day,signature=decision_signature(d));w.pending_decisions[s.id]=d
        with tempfile.TemporaryDirectory() as folder:
            runner=Runner(w,Store(Path(folder)/'world.sqlite3'),{})
            with patch.object(runner.brain,'complete',side_effect=AssertionError('No inference during resolution')),patch.object(runner.brain,'prepare_execution',side_effect=AssertionError('No repeat preview')),patch.object(runner.brain,'russify',side_effect=AssertionError('No repeat translation')):runner.work()
            self.assertEqual(runner.world.phase,'manager');self.assertEqual(len(runner.world.decisions),2)
    def test_changed_orders_invalidate_prepared_signature(self):
        w=World(size=24,count=2);d=self.decision(w,w.states[0]);d['execution_ready']=dict(day=w.day,signature=decision_signature(d));self.assertTrue(ready(d,w.day))
        d['actions'].append(dict(type='do_nothing',args={}));self.assertFalse(ready(d,w.day))
    def test_old_pending_decision_is_explicitly_preparing_before_repair(self):
        w=World(size=24,count=2);w.day=1;w.in_day=True;w.phase='resolution';w.cursor=2;s=w.states[0];d=self.decision(w,s);w.pending_decisions={s.id:d}
        with tempfile.TemporaryDirectory() as folder:
            runner=Runner(w,Store(Path(folder)/'world.sqlite3'),{})
            def prepare(*args):self.assertEqual(w.phase,'preparing');return d
            with patch.object(runner.brain,'prepare_execution',side_effect=prepare),patch.object(runner.brain,'russify',side_effect=lambda d,m:d):runner.work()
            self.assertEqual(runner.world.phase,'manager')
    def test_configuration_upgrade_above_27000_keeps_larger_limits(self):
        cfg=dict(max_tokens=26000,context_window=196608,runtime_patch='6.6');self.assertTrue(upgrade_config(cfg));self.assertEqual(cfg['max_tokens'],196608);self.assertEqual(cfg['context_window'],262144)
        cfg['max_tokens']=32768;self.assertFalse(upgrade_config(cfg));self.assertEqual(cfg['max_tokens'],32768)

if __name__=='__main__':unittest.main()
