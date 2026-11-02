import copy,unittest
from unittest.mock import patch
from planet.engine import World

class Learning681Tests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=24,count=2);self.w.day=5;self.s,self.peer=self.w.states
        for s in self.w.states:s.stocks={k:0 for k in s.stocks}
        self.s.stocks['food']=100;self.peer.stocks['food']=20
    def review(self,**extra):
        return dict(hypothesis='Рост запаса еды при сохранении снабжения.',metric='food',direction='increase',target_change=10,horizon_days=2,stop_condition='Остановить закупки, если не хватает денежного резерва.',next_action='Сравнить фактический запас еды с ожидаемым.',**extra)
    def settle(self):
        before=self.w.reward_baseline()
        with patch.object(self.w,'economic_forecast',return_value=dict(resources={'metal':{'net':-1}})):self.w.settle_rewards(before)
    def test_daily_rewards_on_consecutive_non_month_days_and_no_duplicate(self):
        self.settle();self.assertEqual(self.w.learning_record(self.s.id)['score'],0)
        self.assertEqual(self.w.learning_record(self.peer.id)['score'],-1)
        old=copy.deepcopy(self.w.learning);self.settle();self.assertEqual(self.w.learning,old)
        self.w.day+=1;self.settle();self.assertEqual(self.w.learning_record(self.peer.id)['score'],-2)
        self.assertEqual(len(self.w.learning_record(self.s.id)['episodes']),2)
    def test_experiment_is_evaluated_by_actual_metric_and_does_not_grant_extra_score(self):
        self.w.start_experiment(self.s,self.review());self.settle()
        self.assertTrue(self.w.learning_record(self.s.id)['active_experiment'])
        self.w.day+=1;self.s.stocks['food']+=12;self.settle();record=self.w.learning_record(self.s.id)
        self.assertIsNone(record['active_experiment']);self.assertTrue(record['experiments'][-1]['achieved']);self.assertEqual(record['experiments'][-1]['actual_change'],12)
        self.assertEqual(record['score'],0)
    def test_identical_review_does_not_reset_deadline_and_revised_review_is_archived(self):
        review=self.review();self.w.start_experiment(self.s,review);due=self.w.learning_record(self.s.id)['active_experiment']['due_day']
        self.w.day+=1;self.w.start_experiment(self.s,review);self.assertEqual(self.w.learning_record(self.s.id)['active_experiment']['due_day'],due)
        revised=copy.deepcopy(review);revised['target_change']=20;self.w.start_experiment(self.s,revised)
        self.assertEqual(self.w.learning_record(self.s.id)['experiments'][-1]['status'],'revised')
    def test_invalid_review_does_not_break_real_actions(self):
        d=dict(thinking='Проверка',notes=self.s.notes,plan=self.s.plan,diplomacy=[],actions=[],learning_review={'metric':'fake'})
        self.w.apply_decision(self.s,d);self.assertIn('review_error',self.w.learning_record(self.s.id))
    def test_unknown_experiment_metadata_is_rejected_without_breaking_round(self):
        review=self.review();review['status']='forged';d=dict(thinking='Проверка',notes=self.s.notes,plan=self.s.plan,diplomacy=[],actions=[],learning_review=review)
        self.w.apply_decision(self.s,d);self.assertIsNone(self.w.learning_record(self.s.id)['active_experiment']);self.assertTrue(self.w.learning_context(self.s.id)['last_review_error'])
    def test_legacy_score_events_and_notes_are_preserved_by_migration(self):
        raw=self.w.data();record=raw['learning'][self.s.id];record.update(score=12.5,notes='Прежняя стратегия',events=[dict(day=1,delta=1,reason='monthly_leader',resource='food')])
        for key in ('episodes','experiments','active_experiment'):record.pop(key)
        restored=World.restore(raw).learning_record(self.s.id)
        for key,value in record.items():self.assertEqual(restored[key],value)
        self.assertEqual(restored['episodes'],[])
    def test_episodes_recall_actions_and_remain_private(self):
        self.s.decision_outcome=dict(day=5,accepted=1,rejected=[],action_results=[dict(type='policy',args={'recruit':False},success=True)])
        self.settle();context=self.w.learning_context(self.s.id)
        self.assertEqual(context['recent_episodes'][0]['actions'][0]['type'],'policy')
        self.assertEqual(len(context['best_examples']),1);self.assertEqual(len(self.w.learning_context(self.peer.id)['recent_episodes'][0]['actions']),0)
    def test_old_reward_scale_is_not_mixed_into_new_best_examples(self):
        record=self.w.learning_record(self.s.id);record['episodes']=[dict(day=1,score_delta=100,actions=[],accepted=0,errors=[])]
        self.settle();context=self.w.learning_context(self.s.id)
        self.assertTrue(all(e['reward_version']=='6.8.1-daily' for e in context['best_examples']))
        self.assertEqual(len(record['episodes']),2)
    def test_rewinding_day_without_rewinding_ledger_does_not_pay_again(self):
        self.settle();before=copy.deepcopy(self.w.learning);self.w.day-=1;self.settle();self.assertEqual(before,self.w.learning)

if __name__=='__main__':unittest.main()
