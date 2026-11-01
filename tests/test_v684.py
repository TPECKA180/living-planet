import copy,json,unittest
from unittest.mock import patch
from planet.brain import Brain,RULES
from planet.context import fit,estimate,ContextCapacityError
from planet.prompt_packing import shared_schema,grouped_map
from planet.decision_format import decision_schema
from planet.engine import World,PRICES
from planet.local_execution import prepare_locally
from planet.runtime_config import upgrade_config

class InputContextTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2);self.w.day=35;self.s,self.peer=self.w.states
        self.s.stocks.update(money=10000,metal=1000,food=2000,resource=1000)
        self.w.set_war(self.s.id,self.peer.id,'Проверка военного контекста')
    def test_map_packing_preserves_every_cell_and_property(self):
        context=self.w.context(self.s);rows=context['map'];packed=grouped_map(rows,self.w.size)
        self.assertIsInstance(packed,dict)
        restored=[]
        for *values,indices in packed['groups']:
            restored.extend([[i%self.w.size,i//self.w.size,*values] for i in indices])
        self.assertEqual(sorted(restored),sorted(rows))
    def test_shared_schema_keeps_all_constraints(self):
        original=decision_schema(self.s,self.w.context(self.s),PRICES,True,strict_actions=True)['json_schema']['schema']
        packed=shared_schema(original);defs=packed.get('$defs',{})
        def expand(value):
            if isinstance(value,dict):
                if '$ref' in value:return expand(defs[value['$ref'].split('/')[-1]])
                return {k:expand(v) for k,v in value.items() if k!='$defs'}
            if isinstance(value,list):return [expand(v) for v in value]
            return value
        self.assertEqual(expand(packed),original)
        self.assertLess(len(json.dumps(packed)),len(json.dumps(original)))
    def test_actual_window_preserves_construction_and_recruitment_in_fallback_json(self):
        context=self.w.context(self.s)
        context['memory']=[dict(notes='Повтор старой хроники. '*1000) for _ in range(40)]
        context['messages']=[dict(day=1,sender=self.peer.id,recipient=self.s.id,text='Старые переговоры. '*300) for _ in range(80)]
        latest=dict(day=34,sender=self.peer.id,recipient=self.s.id,text='Реальные текущие условия: металл по5 за единицу.')
        context['messages'].append(latest);before=copy.deepcopy(context)
        context['_response_schema']=decision_schema(self.s,context,PRICES,True,strict_actions=True)
        brain=Brain(dict(context_window=196608,max_tokens=28000,input_tokens=28000,context_retry_attempts=8))
        brain.schema_support['model']=False
        response=dict(choices=[dict(message=dict(content='{"ok":true}'),finish_reason='stop')])
        with patch.object(brain,'prepare_model',return_value=('model',83066)),patch.object(brain,'stream_request',return_value=response) as send:
            self.assertEqual(brain.complete(RULES,context,'model'),{'ok':True})
        payload=send.call_args.args[0];fitted=json.loads(payload['messages'][1]['content'])
        for key in ('construction','military','stocks','units','technology_catalog','action_sites','mobility','economy','states','relations','commerce','notes','plan'):
            self.assertEqual(fitted[key],before[key],key)
        self.assertIn(latest,fitted['messages']);self.assertIn('output_contract',fitted)
        self.assertLess(sum(estimate(m['content']) for m in payload['messages'])+payload['max_tokens'],83066)
        context.pop('_response_schema');self.assertEqual(context,before)
    def test_insufficient_window_never_falls_back_to_identity_only(self):
        source=self.w.context(self.s);before=copy.deepcopy(source)
        with self.assertRaises(ContextCapacityError):fit('Правила.',source,2048,512)
        self.assertEqual(source,before)
    def test_recent_diplomacy_survives_when_old_letters_are_removed(self):
        latest=dict(day=34,sender=self.peer.id,text='Поставка согласуется только после оплаты.')
        source=dict(day=35,state=self.s.id,notes='Характер',stocks={},construction={'projects':[{'project_id':'p','cell':[1,1],'cost':{'money':200}}]},messages=[dict(day=2,text='Архив. '*1000) for _ in range(30)]+[latest])
        fitted=fit('Правила.',source,8192,2048)
        self.assertIn(latest,fitted['messages']);self.assertEqual(fitted['construction'],source['construction'])
    def test_upgrade_restores_both_requested_budgets(self):
        cfg=dict(runtime_patch='6.8.3',max_tokens=8192,context_window=98304,local_execution=True,local_chronicle=True)
        self.assertTrue(upgrade_config(cfg));self.assertEqual(cfg['input_tokens'],56000)
        self.assertEqual(cfg['max_tokens'],196608);self.assertEqual(cfg['context_window'],262144)
        cfg['input_tokens']=40000;self.assertFalse(upgrade_config(cfg));self.assertEqual(cfg['input_tokens'],40000)
    def decision(self,actions):return dict(thinking='Военная проверка.',notes=self.s.notes,plan=self.s.plan,diplomacy=[],actions=actions)
    def test_war_recruitment_template_creates_and_pays_for_real_army(self):
        context=self.w.context(self.s);self.assertTrue(context['military']['recruitment_priority']['can_recruit_now'])
        order=copy.deepcopy(context['military']['recruitment_options'][0]['action']);order['args']['count']=3
        before=len(self.w.units);money=self.s.stocks['money'];cost=context['military']['recruitment_options'][0]['cost']['money']*3
        ready=prepare_locally(self.w,self.s,self.decision([order]),{})
        self.w.apply_decision(self.s,ready)
        self.assertEqual(len(self.w.units)-before,3);self.assertEqual(money-self.s.stocks['money'],cost)
        self.assertEqual(self.s.decision_outcome['accepted'],1)
    def test_missing_army_produces_feedback_without_free_or_forced_recruitment(self):
        money=self.s.stocks['money'];units=copy.deepcopy(self.w.units)
        ready=prepare_locally(self.w,self.s,self.decision([]),{})
        self.assertTrue(any(item['type']=='war_without_army' for item in ready['local_preparation']['issues']))
        self.assertEqual(ready['actions'],[]);self.assertEqual(self.w.units,units);self.assertEqual(self.s.stocks['money'],money)
