import copy,json,unittest
from unittest.mock import patch
from planet.configuration import DEFAULTS
from planet.runtime_config import upgrade_config
from planet.brain import Brain,RULES,context_error,AutomaticRetry
from planet.engine import World,PRICES,RuleError
from planet.local_execution import prepare_locally
from planet.intelligence import CONTRACTS,action_schema

class CapacityTests(unittest.TestCase):
    def test_defaults_and_one_time_upgrade_restore_requested_limits(self):
        self.assertEqual(DEFAULTS['input_tokens'],56000);self.assertEqual(DEFAULTS['max_tokens'],196608);self.assertEqual(DEFAULTS['context_window'],262144)
        cfg=dict(runtime_patch='7.5.0',max_tokens=28000,input_tokens=56000,context_window=196608)
        self.assertTrue(upgrade_config(cfg));self.assertEqual(cfg['max_tokens'],196608);self.assertEqual(cfg['context_window'],262144)
        cfg['max_tokens']=200000;cfg['input_tokens']=90000;self.assertFalse(upgrade_config(cfg));self.assertEqual(cfg['input_tokens'],90000)
    def test_full_requested_answer_is_sent_without_third_window_cap(self):
        brain=Brain(dict(model='m',stream=False,context_window=262144,max_tokens=131072,input_tokens=56000));calls=[]
        def send(path,payload):
            calls.append(payload);return dict(choices=[dict(message=dict(content='{"ok":true}'),finish_reason='stop')])
        with patch.object(brain,'request',side_effect=send):self.assertEqual(brain.complete(RULES,dict(stocks={'money':1}),'m'),{'ok':True})
        self.assertEqual(calls[0]['max_tokens'],131072)
    def test_small_server_reports_actual_budget_without_rewriting_user_config(self):
        cfg=dict(model='m',stream=False,context_window=262144,max_tokens=131072,input_tokens=56000);before=copy.deepcopy(cfg);events=[];brain=Brain(cfg,observer=lambda kind,text='',**data:events.append((kind,data)))
        result=dict(choices=[dict(message=dict(content='{"ok":true}'),finish_reason='stop')])
        with patch.object(brain,'prepare_model',return_value=('m',110848)),patch.object(brain,'request',return_value=result):brain.complete(RULES,dict(stocks={}),'m')
        row=next(data for kind,data in events if kind=='request_start');self.assertEqual(row['requested_output'],131072);self.assertEqual(row['actual_output'],131072);self.assertEqual(row['window'],110848);self.assertEqual(cfg,before)
    def test_length_at_requested_ceiling_recovers_once(self):
        brain=Brain(dict(model='m',stream=False,context_window=262144,max_tokens=131072,input_tokens=56000));calls=[]
        def send(path,payload):
            calls.append(payload);return dict(choices=[dict(message=dict(content='{' if len(calls)==1 else '{"ok":true}'),finish_reason='length' if len(calls)==1 else 'stop')])
        with patch.object(brain,'request',side_effect=send):
            self.assertEqual(brain.complete(RULES,dict(stocks={}),'m'),{'ok':True})
        self.assertEqual(len(calls),2);self.assertTrue(all(p['max_tokens']==131072 for p in calls))
    def test_allocator_errors_trigger_capacity_recovery_not_auth_retry(self):
        self.assertTrue(context_error('Failed to allocate CUDA KV buffer'));self.assertTrue(context_error('Memory allocation failed'));self.assertFalse(context_error('HTTP401 Unauthorized'))
    def test_stream_requests_real_usage_and_calibrates_input(self):
        brain=Brain(dict(model='m',stream=True,calibrate_context=True,context_window=262144,max_tokens=131072,input_tokens=56000));calls=[]
        def send(payload):
            calls.append(payload);return dict(choices=[dict(message=dict(content='{"ok":true}'),finish_reason='stop')],usage=dict(prompt_tokens=1000,completion_tokens=8))
        with patch.object(brain,'stream_request',side_effect=send):brain.complete(RULES,dict(notes='Длинные записи. '*2000),'m')
        self.assertEqual(calls[0]['stream_options'],dict(include_usage=True));self.assertGreater(brain.token_ratios['m'],2)
    def test_unsupported_stream_usage_retries_once_without_losing_input(self):
        brain=Brain(dict(model='m',stream=True,context_window=262144,max_tokens=131072,input_tokens=56000));calls=[]
        def send(payload):
            calls.append(payload)
            if len(calls)==1:raise RuntimeError('HTTP400 stream_options unsupported')
            return dict(choices=[dict(message=dict(content='{"ok":true}'),finish_reason='stop')])
        with patch.object(brain,'stream_request',side_effect=send):self.assertEqual(brain.complete(RULES,dict(stocks={'money':1}),'m'),{'ok':True})
        self.assertEqual(len(calls),2);self.assertNotIn('stream_options',calls[1]);self.assertEqual(calls[0]['messages'],calls[1]['messages'])
    def test_empty_api_envelope_and_null_usage_are_recoverable(self):
        brain=Brain(dict(model='m',stream=False,context_window=262144,max_tokens=131072,input_tokens=56000));calls=[]
        def send(path,payload):
            calls.append(payload)
            return dict(choices=[]) if len(calls)==1 else dict(choices=[dict(message=dict(content='{"ok":true}'),finish_reason='stop')],usage=None)
        with patch.object(brain,'request',side_effect=send):self.assertEqual(brain.complete(RULES,dict(stocks={}),'m'),{'ok':True})
        self.assertEqual(len(calls),2);self.assertEqual(calls[0]['messages'],calls[1]['messages'])
    def test_missing_message_stays_bounded_and_recoverable(self):
        brain=Brain(dict(model='m',stream=False,context_window=262144,context_retry_attempts=2))
        with patch.object(brain,'request',return_value=dict(choices=[{}])) as send:
            with self.assertRaisesRegex(__import__('planet.brain',fromlist=['AutomaticRetry']).AutomaticRetry,'choices/message'):brain.complete(RULES,{},'m')
        self.assertEqual(send.call_count,2)
    def test_custom_larger_limits_survive_upgrade(self):
        cfg=dict(runtime_patch='7.5.0',max_tokens=200000,input_tokens=80000,context_window=524288);upgrade_config(cfg)
        self.assertEqual((cfg['max_tokens'],cfg['input_tokens'],cfg['context_window']),(200000,80000,524288))

class MechanicsDefenceTests(unittest.TestCase):
    def test_null_or_list_assessment_does_not_block_valid_paid_transfer(self):
        for bad in (None,[],['broken']):
            with self.subTest(bad=bad):
                w=World(size=24,count=2);a,b=w.states;w.day=1;before=b.stocks['money']
                d=dict(thinking='Проверка',notes=a.notes,plan=a.plan,diplomacy=[],strategic_assessment=bad,actions=[dict(type='transfer',args=dict(partner=b.id,resource='money',amount=1))])
                prepared=prepare_locally(w,a,d,{});w.apply_decision(a,prepared);self.assertEqual(b.stocks['money'],before+1)
    def test_one_bad_unit_order_does_not_reroll_valid_paid_actions(self):
        w=World(size=24,count=2);w.day=1;a,b=w.states;foreign=next(u for u in w.units if u['owner']==b.id)
        d=dict(owner=a.id,thinking='Развитие по собственному плану',notes=a.notes,plan=a.plan,diplomacy=[dict(to='all',text='Обсудим условия.')],actions=[dict(type='transfer',args=dict(partner=b.id,resource='money',amount=1)),dict(type='move',args=dict(unit_id=foreign['id'],target_cell=foreign['cell']))])
        brain=Brain(dict(model='test',local_execution=True,decision_compiler=True));before=a.stocks['money'];other=b.stocks['money']
        with patch.object(brain,'complete',return_value=d) as send:fixed=brain.think(a,w.context(a))
        self.assertEqual(send.call_count,1);self.assertTrue(fixed['action_validation_warnings'])
        w.apply_decision(a,prepare_locally(w,a,fixed,{}));self.assertEqual(a.stocks['money'],before-1);self.assertEqual(b.stocks['money'],other+1);self.assertEqual(a.decision_outcome['accepted'],1);self.assertEqual(len(a.decision_outcome['rejected']),1)
    def test_new_unit_then_move_is_validated_in_execution_order(self):
        w=World(size=24,count=2);w.day=1;a=w.states[0];w.units=[];a.stocks.update(money=1000,metal=1000)
        for c in w.cells:c.owner=None;c.terrain='water';c.building=None;c.population=0;c.wall_hp=None
        for x in (1,2,3,4):c=w.cell([x,2]);c.owner=a.id;c.terrain='grass'
        uid=w.next_unit;before=a.stocks['money'];price=w.unit_price(a)
        d=dict(owner=a.id,thinking='Создаю отряд и перемещаю его',notes=a.notes,plan=a.plan,diplomacy=[dict(to='all',text='Действуем по плану.')],actions=[dict(type='unit',args=dict(cell=[1,2],unit='army',strength=3)),dict(type='move',args=dict(unit_id=uid,target_cell=[3,2]))])
        brain=Brain(dict(model='test',local_execution=True,decision_compiler=True))
        with patch.object(brain,'complete',return_value=d) as send:fixed=brain.think(a,w.context(a))
        self.assertEqual(send.call_count,1);prepared=prepare_locally(w,a,fixed,{})
        self.assertEqual(prepared['execution_preflight']['failed'],0);w.apply_decision(a,prepared);self.assertEqual(w.units[0]['cell'],[3,2]);self.assertEqual(before-a.stocks['money'],price+4)
    def test_local_execution_still_rejects_a_foreign_decision_owner(self):
        w=World(size=24,count=2);a,b=w.states;before=w.data()
        d=dict(owner=b.id,thinking='Неверный владелец',notes=a.notes,plan=a.plan,diplomacy=[dict(to='all',text='Проверка владельца.')],actions=[])
        brain=Brain(dict(model='test',local_execution=True,decision_compiler=True,decision_repair_attempts=2))
        with patch.object(brain,'complete',return_value=d) as send:
            with self.assertRaises(AutomaticRetry):brain.think(a,w.context(a))
        self.assertEqual(send.call_count,2);self.assertEqual(w.data(),before)
    def test_build_selector_uses_exact_own_project_and_normal_payment(self):
        w=World(size=24,count=2);w.day=1;a=w.states[0];a.stocks.update(money=5000,resource=5000);c=w.context(a)
        project=next(p for p in c['construction']['projects'] if p['building']=='castle' and p['level']==1)
        schema=action_schema(['build'],c)['anyOf'][0]['properties']['args']
        self.assertIn(project['project_id'],schema['anyOf'][0]['properties']['project_id']['enum']);self.assertIn('cell',schema['anyOf'][1]['required'])
        d=dict(thinking='Строительство по выбранному проекту',notes=a.notes,plan=a.plan,diplomacy=[],actions=[dict(type='build',args=dict(project_id=project['project_id']))]);before=dict(a.stocks)
        fixed=prepare_locally(w,a,d,{},own_context=c);w.apply_decision(a,fixed)
        self.assertEqual(w.cell(project['cell']).building,'castle')
        for key,cost in project['cost'].items():self.assertEqual(before[key]-a.stocks[key],cost)
    def test_all_actions_handle_malformed_inputs_without_partial_mutation(self):
        seed=World(size=24,count=2).data();total=0
        for kind in PRICES:
            variants=[None,[],{},dict(cell=[999,999])]
            for key in CONTRACTS.get(kind,({},[]))[0]:variants.extend({key:bad} for bad in (None,[],{},'invalid',float('nan')))
            w0=World.restore(seed);a,b=w0.states
            defaults=dict(cell=w0.positions(a.id)[0],target_cell=w0.positions(a.id)[1],partner=b.id,unit_id=next(u['id'] for u in w0.units if u['owner']==a.id),unit='army',building='castle',resource='food',reason='Проверка',tech='army')
            base={}
            for key,schema in CONTRACTS.get(kind,({},[]))[0].items():
                base[key]=defaults.get(key,schema.get('enum',[1 if schema.get('type') in ('integer','number') else False if schema.get('type')=='boolean' else {} if schema.get('type')=='object' else [] if schema.get('type')=='array' else 'test'])[0])
            variants+= [dict(base,**v) if isinstance(v,dict) else v for v in variants.copy()]
            for args in variants:
                with self.subTest(kind=kind,args=args):
                    w=World.restore(seed);before=w.data();total+=1
                    try:w.execute(w.states[0],dict(type=kind,args=args))
                    except (RuleError,TypeError,KeyError):self.assertEqual(w.data(),before)
        self.assertGreaterEqual(total,1760)

if __name__=='__main__':unittest.main()
