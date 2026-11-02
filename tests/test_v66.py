import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.brain import Brain,AutomaticRetry
from planet.context import fit
from planet.engine import World,Store
from planet.runtime_config import upgrade_config
from planet.military_ai import validate_military
from main import Runner

class Patch66Tests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2);self.w.day=1;self.s,self.peer=self.w.states
        self.s.stocks.update(money=10000,metal=1000,food=1000,resource=1000)
    def war(self):
        self.w.set_war(self.s.id,self.peer.id,'Реальная война для проверки')
        self.s.operations.update(recruit=True,explore=False)
    def decision(self):
        return dict(owner=self.s.id,origin_patch='6.5',thinking='Сохраняем свою стратегию.',notes=self.s.notes,plan=self.s.plan,
                    diplomacy=[dict(to=self.peer.id,text='Обсудим конкретные условия.')],actions=[])
    def test_nested_repair_keeps_error_orders_and_project_while_trimming_archives(self):
        context=self.w.context(self.s);context['memory']=[dict(owner=self.s.id,notes='Долгая история '*300) for _ in range(200)]
        source=dict(own_context=context,day=self.w.day,error='Требуется собственная эпоха II',current_actions=[dict(type='supply_pact',args=dict(partner=self.peer.id,resource='metal',amount=1,price=2))])
        before=copy.deepcopy(source)
        from planet.context import ContextCapacityError
        with self.assertRaises(ContextCapacityError):fit('Исправь только приказы.',source,18000,6000)
        fitted=fit('Исправь только приказы.',source,32768,6000)
        self.assertNotIn('own_context',fitted);self.assertEqual(fitted['error'],source['error']);self.assertEqual(fitted['current_actions'],source['current_actions'])
        self.assertTrue(fitted['construction']['projects']);self.assertEqual(fitted['identity']['id'],self.s.id)
        self.assertLess(fitted['context_info']['estimated_input_tokens']+6000,32768);self.assertEqual(source,before)
    def test_execution_repair_payload_is_flat_and_contains_actual_error(self):
        d=self.decision();d['actions']=[dict(type='research',args=dict(tech='not_a_tech',cell=self.w.positions(self.s.id)[0]))]
        brain=Brain(dict(decision_repair_attempts=1));calls=[]
        def complete(system,payload,model):
            calls.append(payload)
            return dict(actions=[],construction_review=dict(choice='defer',project_id=None,reason='Сначала выбираем доступное исследование из полного каталога.',revisit_day=self.w.day+1),economic_review=dict(mode='none',reason='Сохраняем казну: финансовые приказы сейчас не нужны.',orders=[]))
        with patch.object(brain,'complete',side_effect=complete):brain.prepare_execution(self.w,self.s,d)
        self.assertEqual(len(calls),1);self.assertNotIn('own_context',calls[0]);self.assertIn('stocks',calls[0]);self.assertIn('construction',calls[0]);self.assertIn('error',calls[0])
    def test_response_limit_upgrade_once_preserves_host_keys_and_later_user_settings(self):
        cfg=dict(max_tokens=16384,context_window=196608,host='http://custom/v1',api_key='private',deep_strategy=True)
        self.assertTrue(upgrade_config(cfg));self.assertEqual(cfg['max_tokens'],196608);self.assertEqual(cfg['host'],'http://custom/v1');self.assertEqual(cfg['api_key'],'private');self.assertTrue(cfg['deep_strategy'])
        cfg['max_tokens']=30000;self.assertFalse(upgrade_config(cfg));self.assertEqual(cfg['max_tokens'],30000)
    def test_existing_larger_output_limit_is_kept(self):
        cfg=dict(max_tokens=196608);upgrade_config(cfg);self.assertEqual(cfg['max_tokens'],196608)
    def test_service_retry_retains_partial_order_corrections(self):
        d=self.decision();d['actions']=[dict(type='research',args=dict(tech='not_a_tech',cell=self.w.positions(self.s.id)[0]))]
        update=dict(actions=[dict(type='research',args=dict(tech='another_bad_tech',cell=self.w.positions(self.s.id)[0]))])
        brain=Brain(dict(decision_repair_attempts=1))
        with patch.object(brain,'complete',return_value=update):
            with self.assertRaises(AutomaticRetry) as caught:brain.prepare_execution(self.w,self.s,d)
        self.assertEqual(caught.exception.owner,self.s.id);self.assertEqual(caught.exception.repaired_decision['actions'],update['actions'])
        self.assertEqual(caught.exception.repaired_decision['notes'],d['notes'])
    def test_unified_runner_skips_two_redundant_model_review_stages(self):
        self.w.in_day=True;self.w.phase='planning';self.w.cursor=0;d=self.decision()
        with tempfile.TemporaryDirectory() as temp:
            runner=Runner(self.w,Store(Path(temp)/'world.sqlite3'),dict(unified_execution_review=True))
            with patch.object(runner.brain,'think',return_value=d),patch.object(runner.brain,'review_construction',side_effect=AssertionError('Separate construction call')),patch.object(runner.brain,'review_economy',side_effect=AssertionError('Separate economy call')):runner.work()
            self.assertEqual(self.w.cursor,1);self.assertEqual(self.w.pending_decisions[self.s.id]['notes'],d['notes'])
    def test_automatic_war_minimum_is_removed_in_patch67(self):
        self.w.units=[u for u in self.w.units if u['owner']!=self.s.id];self.w.spawn(self.s.id,self.w.positions(self.s.id)[0],'scout',3)
        self.war();before=self.s.stocks.copy();self.w.run_operations()
        armies=[u for u in self.w.units if u['owner']==self.s.id and u['type']=='army']
        self.assertEqual(len(armies),0);self.assertEqual(before,self.s.stocks)
        self.w.run_operations();self.assertEqual(len([u for u in self.w.units if u['owner']==self.s.id and u['type']=='army']),0)
        for _ in range(3):self.w.day+=1;self.w.run_operations()
        self.assertEqual(len([u for u in self.w.units if u['owner']==self.s.id and u['type']=='army']),0)
    def test_war_muster_can_be_disabled_by_own_policy(self):
        self.war();self.w.execute(self.s,dict(type='policy',args=dict(war_recruit=False)))
        self.w.run_operations();self.assertFalse(any(u['owner']==self.s.id and u['type']=='army' for u in self.w.units))
    def test_war_muster_preserves_reserve_and_ignores_insufficient_funds(self):
        self.war();self.s.stocks['money']=80;self.s.operations['reserve_money']=30;before=self.s.stocks.copy();self.w.run_operations()
        self.assertFalse(any(u['owner']==self.s.id and u['type']=='army' for u in self.w.units));self.assertEqual(before,self.s.stocks)
    def test_recruit_false_or_zero_limit_prevents_forced_muster(self):
        self.war();self.s.operations['recruit']=False;self.w.run_operations()
        self.assertFalse(any(u['owner']==self.s.id and u['type']=='army' for u in self.w.units))
        self.w.day+=1;self.s.operations.update(recruit=True,war_army_limit=0);self.w.run_operations()
        self.assertFalse(any(u['owner']==self.s.id and u['type']=='army' for u in self.w.units))
    def test_enemy_opinion_and_war_plan_are_not_actual_war(self):
        self.w.relation(self.s.id,self.peer.id)['stance']='enemy';self.assertEqual(self.w.conflict_status(self.s.id,self.peer.id),'МИР')
        self.war();self.assertEqual(self.w.conflict_status(self.s.id,self.peer.id),'ВОЙНА');self.assertEqual(self.w.conflict_status(self.peer.id,self.s.id),'ВОЙНА')
        self.w.execute(self.s,dict(type='peace',args=dict(partner=self.peer.id)));self.assertEqual(self.w.conflict_status(self.s.id,self.peer.id),'ВОЙНА')
        self.w.execute(self.peer,dict(type='peace',args=dict(partner=self.s.id)));self.assertEqual(self.w.conflict_status(self.s.id,self.peer.id),'МИР')
    def test_no_data_is_not_valid_deferral_when_real_recruitment_options_are_present(self):
        self.war();d=self.decision();d['military_response']=dict(choice='defer',reason='Нет данных о текущем фронте и составе войск.',revisit_day=self.w.day+1)
        with self.assertRaises(ValueError):validate_military(d,self.w.context(self.s))
    def test_stream_batching_preserves_every_character_and_channel(self):
        events=[];brain=Brain(dict(host='http://localhost',detect_repetition=False),observer=lambda kind,text='',**kw:events.append((kind,text)))
        class Response:
            headers={'Content-Type':'text/event-stream'}
            def readline(self,size=-1):
                if not hasattr(self,'lines'):self.lines=iter(self)
                line=next(self.lines,None)
                return line+b'\n' if line is not None else b''
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def __iter__(self):
                for field,value in (('reasoning_content','р'),('content','x')):
                    for _ in range(1000):
                        yield ('data: '+json.dumps(dict(choices=[dict(delta={field:value})]))).encode();yield b''
                yield b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}';yield b''
        with patch('urllib.request.urlopen',return_value=Response()):response=brain.stream_request(dict(stream=True))
        self.assertEqual(response['choices'][0]['message']['content'],'x'*1000)
        self.assertEqual(''.join(t for k,t in events if k=='reasoning'),'р'*1000);self.assertEqual(''.join(t for k,t in events if k=='content'),'x'*1000)
        self.assertLess(len(events),100)
    def test_construction_schema_forbids_build_without_selected_project(self):
        from planet.decision_format import construction_review_schema
        ctx=self.w.context(self.s);schema=construction_review_schema(ctx)
        build=[branch['properties'] for branch in schema['anyOf'] if 'build' in branch['properties']['choice']['enum']]
        self.assertEqual(len(build),1);self.assertNotIn(None,build[0]['project_id']['enum'])
        self.assertIn(ctx['construction']['projects'][0]['project_id'],build[0]['project_id']['enum'])
        self.assertTrue(any(b['properties']['project_id'].get('type')=='null' for b in schema['anyOf']))
    def test_schema_fallback_supplies_contract_in_plain_prompt(self):
        brain=Brain(dict(model='test',stream=False,context_window=12000,max_tokens=2000));brain.schema_support['test']=False;captured=[]
        schema=dict(type='json_schema',json_schema=dict(schema=dict(type='object',properties=dict(actions=dict(type='array')),required=['actions'])))
        def request(path,payload):
            captured.append(payload);return dict(choices=[dict(message=dict(content='{"actions":[]}'),finish_reason='stop')])
        with patch.object(brain,'request',side_effect=request):brain.complete('Верни JSON по схеме.',dict(_response_schema=schema),'test')
        fitted=json.loads(captured[0]['messages'][1]['content']);self.assertEqual(fitted['output_contract']['required'],['actions'])

if __name__=='__main__':unittest.main()
