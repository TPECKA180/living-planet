import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import Runner
from planet.brain import Brain, RULES
from planet.engine import RuleError, Store, World
from planet.saves import WorldLibrary, WorldLock


def action(kind,**args): return dict(type=kind,args=args)


def decision(**kwargs):
    return dict(thinking='Развитие',notes='Сохраняю характер',plan='Больше граждан и ресурсов',
                diplomacy=[dict(to='all',text='Обсудим сотрудничество')],actions=[action('do_nothing')],**kwargs)


class RoundTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.world=World(size=24,count=2)
        self.store=Store(Path(self.temp.name)/'world.sqlite3')
        self.runner=Runner(self.world,self.store,dict(manager_every=10))

    def test_common_day_collects_all_before_any_effect(self):
        contexts=[]
        def think(state,context):
            contexts.append(context)
            result=decision(); result['actions']=[action('transfer',cell=self.world.positions(state.id)[0],partner='state_2' if state.id=='state_1' else 'state_1',amount=5,resource='food')]
            return result
        with patch.object(Brain,'think',side_effect=think):
            self.runner.work(); start_food=self.world.states[0].stocks['food']
            self.assertEqual(self.world.day,1); self.assertEqual(len(self.world.pending_decisions),1)
            self.assertEqual(self.world.messages,[]); self.assertEqual(self.world.states[0].memory,[])
            self.runner.work()
            self.assertEqual(self.world.states[0].stocks['food'],start_food)
            self.assertEqual([c['day'] for c in contexts],[1,1]); self.assertEqual(self.world.phase,'resolution')
            self.runner.work(); resolved=self.runner.world
            self.assertEqual(len(resolved.messages),2); self.assertEqual(len(resolved.decisions),2)
            self.assertEqual(resolved.states[0].stocks['food'],start_food)
            self.runner.work(); self.assertEqual(self.runner.world.day,1); self.assertFalse(self.runner.world.in_day)

    def test_pending_decision_survives_restart_without_requery(self):
        with patch.object(Brain,'think',return_value=decision()): self.runner.work()
        restored=self.store.load(); self.assertEqual(restored.cursor,1)
        runner=Runner(restored,self.store,dict(manager_every=10))
        with patch.object(Brain,'think',return_value=decision()) as think:
            runner.work(); runner.work(); runner.work()
            self.assertEqual(think.call_count,1)
        self.assertEqual(runner.world.day,1); self.assertEqual(len(runner.world.decisions),2)

    def test_resolved_round_is_not_applied_twice_after_restart(self):
        with patch.object(Brain,'think',return_value=decision()):
            self.runner.work(); self.runner.work(); self.runner.work()
        runner=Runner(self.store.load(),self.store,dict(manager_every=10)); runner.work()
        self.assertEqual(len(runner.world.messages),2); self.assertEqual(len(runner.world.decisions),2)

    def test_manager_failure_does_not_repeat_resolved_actions(self):
        self.runner.config['manager_every']=1
        with patch.object(Brain,'think',return_value=decision()):
            self.runner.work(); self.runner.work(); self.runner.work()
        with patch.object(Brain,'manager',side_effect=ValueError('bad manager')): self.runner.work()
        self.assertEqual(self.runner.world.phase,'manager'); self.assertEqual(len(self.runner.world.messages),2)
        event=dict(event='peace',target=None,title='Глава',description='Событие',expand=False)
        with patch.object(Brain,'manager',return_value=event): self.runner.work()
        self.assertEqual(len(self.runner.world.messages),2); self.assertEqual(self.runner.world.chapter,1)

    def test_old_partial_day_migrates_without_replaying_finished_states(self):
        self.world.start_day(); self.world.cursor=1
        data=self.world.data()
        for key in ('phase','pending_decisions','decisions','messages','trade_offers','next_offer'): data.pop(key)
        data['version']=1
        restored=World.restore(data); runner=Runner(restored,self.store,dict(manager_every=10))
        with patch.object(Brain,'think',return_value=decision()) as think:
            runner.work(); runner.work(); runner.work(); self.assertEqual(think.call_count,1)
        self.assertEqual([d['state'] for d in runner.world.decisions],['state_2'])


class EconomyTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=24,count=2); self.s,self.other=self.w.states
        self.p=self.w.positions(self.s.id)[0]; self.q=self.w.positions(self.other.id)[0]

    def test_transfer_remote_and_conservation(self):
        total=sum(s.stocks['metal'] for s in self.w.states)
        self.w.execute(self.s,action('transfer',cell=self.p,partner=self.other.id,resource='metal',amount=40))
        self.assertEqual(self.s.stocks['metal'],110); self.assertEqual(self.other.stocks['metal'],190)
        self.assertEqual(sum(s.stocks['metal'] for s in self.w.states),total)

    def test_transfer_money(self):
        self.w.execute(self.s,action('transfer',cell=self.p,partner=self.other.id,resource='money',amount=100))
        self.assertEqual(self.s.stocks['money'],1100); self.assertEqual(self.other.stocks['money'],1300)

    def test_no_negative_or_overdraft_transfer(self):
        for amount in (-1,0,999,True,1.5):
            before=self.w.data()
            with self.assertRaises(RuleError): self.w.execute(self.s,action('transfer',cell=self.p,partner=self.other.id,resource='metal',amount=amount))
            self.assertEqual(before,self.w.data())

    def test_trade_requires_consent_and_only_buyer_can_accept(self):
        before=[copy.deepcopy(s.stocks) for s in self.w.states]
        self.w.execute(self.s,action('trade',cell=self.p,partner=self.other.id,resource='metal',amount=10,price=3))
        self.assertEqual(before,[s.stocks for s in self.w.states])
        with self.assertRaises(RuleError): self.w.execute(self.s,action('accept_trade',cell=self.p,offer_id=1))
        self.w.execute(self.other,action('accept_trade',cell=self.q,offer_id=1))
        self.assertEqual(self.s.stocks['money'],1230); self.assertEqual(self.other.stocks['money'],1170)
        self.assertEqual(self.s.stocks['metal'],140); self.assertEqual(self.other.stocks['metal'],160)
        with self.assertRaises(RuleError): self.w.execute(self.other,action('accept_trade',cell=self.q,offer_id=1))

    def test_unfunded_accept_does_not_partially_spend(self):
        self.w.execute(self.s,action('trade',cell=self.p,partner=self.other.id,resource='metal',amount=10,price=1000))
        before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.other,action('accept_trade',cell=self.q,offer_id=1))
        self.assertEqual(self.w.data(),before)

    def test_expired_trade(self):
        self.w.execute(self.s,action('trade',cell=self.p,partner=self.other.id,resource='metal',amount=10))
        self.w.day=6; self.w.start_day()
        self.assertEqual(self.w.trade_offers[0]['status'],'expired')
        with self.assertRaises(RuleError): self.w.execute(self.other,action('accept_trade',cell=self.q,offer_id=1))

    def test_settle_grows_population_at_real_cost(self):
        self.w.execute(self.s,action('settle',cell=self.p,amount=2))
        self.assertEqual(sum(self.w.cell(p).population for p in self.w.positions(self.s.id)),5)
        self.assertEqual(self.s.stocks['money'],1100); self.assertEqual(self.s.stocks['food'],190)
        self.assertEqual(self.s.stocks['resource'],230)

    def test_settle_cannot_create_free_people(self):
        self.s.stocks['food']=0; before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.s,action('settle',cell=self.p,amount=2))
        self.assertEqual(before,self.w.data())

    def test_private_messages_only_in_participant_context(self):
        w=World(size=32,count=3)
        w.send_message(w.states[0],'state_2','Закрытые переговоры')
        self.assertEqual(len(w.context(w.states[1])['messages']),1)
        context=w.context(w.states[2])
        self.assertEqual(context['messages'],[])
        self.assertNotIn('Закрытые переговоры',json.dumps(context,ensure_ascii=False))


class SavesTests(unittest.TestCase):
    def test_world_lock_prevents_two_writers_and_releases(self):
        with tempfile.TemporaryDirectory() as temp:
            lock=WorldLock(temp)
            try:
                with self.assertRaises(RuntimeError): WorldLock(temp)
            finally: lock.close()
            second=WorldLock(temp); second.close()

    def test_independent_worlds_and_full_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            library=WorldLibrary(temp,dict(api_key='SECRET',context_window=131072))
            a,store=library.create('Мир / один',count=2,seed=1)
            a.start_day(); a.pending_decisions['state_1']=decision(); a.cursor=1; store.save(a)
            b,other=library.create('Мир / один',count=2,seed=2)
            self.assertNotEqual(store.path,other.path); self.assertEqual(len(library.entries()),2)
            loaded,_=library.load(store.path.parent); self.assertEqual(a.data(),loaded.data())
            folder=store.path.parent
            for name in ('world.json','manifest.json','chronicle.jsonl','messages.jsonl','decisions.jsonl','trade_offers.json','states/state_1/state.json','states/state_1/actions.jsonl','states/state_1/memory.jsonl'):
                self.assertTrue((folder/name).is_file(),name)
            self.assertNotIn('SECRET',(folder/'settings.json').read_text())
            self.assertEqual(json.loads((folder/'world.json').read_text(encoding='utf-8')),a.data())

    def test_legacy_import_keeps_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'old.sqlite3'; old=Store(path); world=World(size=24,count=2); old.save(world)
            before=path.read_bytes()
            library=WorldLibrary(Path(temp)/'saves'); restored,store=library.import_legacy(path)
            self.assertEqual(restored.data(),world.data()); self.assertEqual(path.read_bytes(),before)
            self.assertNotEqual(path,store.path)


class ContextTests(unittest.TestCase):
    def test_large_context_is_bounded_and_keeps_notes(self):
        brain=Brain(dict(context_window=16384,max_tokens=4096))
        context=dict(notes='Уникальный характер',plan='Развитие',map=[[i,'x'*200] for i in range(2000)],messages=[dict(text='Важное последнее сообщение')])
        fitted=brain.fit_context(RULES,context,16384)
        self.assertEqual(fitted['notes'],context['notes']); self.assertTrue(fitted['map_truncated'])
        self.assertLessEqual(fitted['context_info']['estimated_input_tokens'],16384-4096-1024)
        self.assertEqual(len(context['map']),2000)

    def test_diplomacy_is_required(self):
        world=World(size=24,count=2); brain=Brain({}); result=decision(); result.pop('diplomacy')
        with patch.object(brain,'complete',return_value=result):
            from planet.brain import AutomaticRetry
            with self.assertRaises(AutomaticRetry): brain.think(world.states[0],world.context(world.states[0]))

    def test_server_context_reload_uses_confirmed_window(self):
        brain=Brain(dict(manage_model_context=True,context_window=131072))
        calls=[]
        def request(path,payload=None):
            calls.append((path,payload))
            if path=='/api/v1/models': return dict(models=[dict(key='test',type='llm',max_context_length=262144,loaded_instances=[dict(id='old',config=dict(context_length=4096))])])
            if path.endswith('/load'): return dict(instance_id='new',load_config=dict(context_length=131072))
            return {}
        with patch.object(brain,'request',side_effect=request): model,window=brain.prepare_model('test')
        self.assertEqual((model,window),('new',131072))
        self.assertEqual(calls[1],('/api/v1/models/unload',dict(instance_id='old')))
        self.assertEqual(calls[2][1]['context_length'],131072)

    def test_unsupported_window_clamps_before_loading(self):
        brain=Brain(dict(manage_model_context=True,context_window=131072))
        def request(path,payload=None):
            if path=='/api/v1/models': return dict(models=[dict(key='tiny',type='llm',max_context_length=4096,loaded_instances=[])])
            self.assertEqual(payload['context_length'],4096)
            return dict(instance_id='tiny',load_config=dict(context_length=4096))
        with patch.object(brain,'request',side_effect=request):
            self.assertEqual(brain.prepare_model('tiny'),('tiny',4096))

    def test_failed_increase_falls_back_to_confirmed_smaller_context(self):
        brain=Brain(dict(manage_model_context=True,context_window=131072)); calls=[]
        def request(path,payload=None):
            calls.append((path,payload))
            if path=='/api/v1/models': return dict(models=[dict(key='test',type='llm',max_context_length=262144,loaded_instances=[dict(id='old',config=dict(context_length=65536))])])
            if path.endswith('/load'):
                if payload['context_length']==131072: raise RuntimeError('insufficient system resources')
                return dict(instance_id='restored',load_config=dict(context_length=65536))
            return {}
        with patch.object(brain,'request',side_effect=request):
            self.assertEqual(brain.prepare_model('test'),('restored',65536))
        self.assertLess(calls[-1][1]['context_length'],131072)
        self.assertEqual(brain.loaded_instance,'restored')


if __name__=='__main__': unittest.main()
