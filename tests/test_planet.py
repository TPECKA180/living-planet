import copy
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from planet.brain import Brain, parse_json
from planet.engine import RuleError, Store, World
from main import Runner


def action(kind,**args): return dict(type=kind,args=args)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=24,count=2); self.s=self.w.states[0]
        self.p=self.w.positions(self.s.id)[0]

    def test_initial_map_and_reproducibility(self):
        self.assertEqual(self.w.data(),World(size=24,count=2).data())
        self.assertEqual(len(self.w.cells),24**2)
        self.assertEqual(len({tuple(u['cell']) for u in self.w.units}),len(self.w.units))

    def test_invalid_build_does_not_spend(self):
        before=copy.deepcopy(self.s.stocks)
        with self.assertRaises(RuleError): self.w.execute(self.s,action('build',cell=self.p,type='lab',level=1))
        self.assertEqual(self.s.stocks,before)

    def test_income_is_once_on_retry(self):
        self.w.start_day(); stocks=copy.deepcopy(self.s.stocks)
        self.w.start_day()
        self.assertEqual(self.s.stocks,stocks); self.assertEqual(self.w.day,1)

    def test_unstaffed_building_multiplier(self):
        c=self.w.cell(self.p); c.building='arsenal'; c.building_level=2
        self.w.income(); self.assertEqual(self.s.stocks['matter'],2)
        c.population=1; self.w.income(); self.assertEqual(self.s.stocks['matter'],22)

    def test_no_teleport(self):
        for c in self.w.cells: c.terrain='grass'
        u=self.w.units[0]; before=list(u['cell'])
        self.w.execute(self.s,action('army',cell=u['cell'],unit_id=u['id'],target_cell=[0,0]))
        self.assertNotEqual(u['cell'],[0,0]); self.assertLessEqual(abs(before[0]-u['cell'][0])+abs(before[1]-u['cell'][1]),4)
        for step in self.w.movement_log:
            self.assertEqual(abs(step['source'][0]-step['target'][0])+abs(step['source'][1]-step['target'][1]),1)

    def test_battle_and_no_regeneration(self):
        u=self.w.units[0]; u['strength']=7
        target=next(p for p in self.w.adjacent(u['cell']) if not self.w.unit_at(p))
        self.w.cell(target).terrain='grass'
        self.w.spawn(self.w.states[1].id,target,'army',3)
        self.w.execute(self.s,action('army',cell=list(u['cell']),unit_id=u['id'],target_cell=target))
        self.assertEqual(u['strength'],4); self.assertEqual(self.w.cell(target).owner,self.s.id)
        self.w.income(); self.assertEqual(u['strength'],4)

    def test_research_requires_lab_and_costs_science(self):
        p=next(p for p in self.w.positions(self.s.id) if self.w.cell(p).terrain=='science')
        self.w.execute(self.s,action('build',cell=p,type='lab',level=1))
        self.w.execute(self.s,action('research',cell=p,tech='navigation'))
        self.assertEqual(self.s.stocks['science'],20)
        self.assertIn('navigation',self.s.tech)

    def test_upgrade_never_grows_building(self):
        p=next(p for p in self.w.positions(self.s.id) if self.w.cell(p).building)
        self.s.tech.append('agriculture'); c=self.w.cell(p); level=c.building_level
        self.w.execute(self.s,action('upgrade',cell=p,tech='agriculture'))
        self.assertEqual(c.building_level,level)

    def test_self_trade_rejected(self):
        before=copy.deepcopy(self.s.stocks)
        with self.assertRaises(RuleError): self.w.execute(self.s,action('trade',cell=self.p,partner=self.s.id,amount=3,resource='food'))
        self.assertEqual(self.s.stocks,before)

    def test_expansion_preserves_coordinates_and_memory(self):
        self.s.notes='Характер'; before=copy.deepcopy(self.w.cell(self.p))
        self.w.expand(); self.assertEqual(self.w.size,48)
        self.assertEqual(self.w.cell(self.p),before); self.assertEqual(self.s.notes,'Характер')

    def test_save_resume_mid_day(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'world.db'); self.w.start_day(); self.w.cursor=1
            self.s.memory.append(dict(day=1,notes='Память',plan='План'))
            store.save(self.w); restored=store.load()
            self.assertEqual(restored.data(),self.w.data())
            before=copy.deepcopy(restored.states[0].stocks); restored.start_day()
            self.assertEqual(before,restored.states[0].stocks)

    def test_manager_cannot_reset_memory(self):
        notes=self.s.notes
        self.w.manager(dict(event='drought',target=self.s.id,title='Засуха',description='Мало дождя',expand=False))
        self.assertEqual(self.s.stocks['food'],210); self.assertEqual(self.s.notes,notes)

    def test_failed_brain_does_not_skip_state(self):
        with tempfile.TemporaryDirectory() as folder:
            runner=Runner(self.w,Store(Path(folder)/'world.db'),{})
            with patch.object(Brain,'think',side_effect=ValueError('bad JSON')): runner.work()
            self.assertEqual(self.w.cursor,0); self.assertTrue(self.w.in_day)
            self.assertEqual(self.s.history,[])

    def test_successful_full_day_and_manager(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'world.db'); runner=Runner(self.w,store,dict(manager_every=1))
            decision=dict(thinking='Объяснение',notes='Память',plan='План',actions=[action('do_nothing')])
            event=dict(event='peace',target=None,title='Мир',description='Начало мира',expand=False)
            with patch.object(Brain,'think',return_value=decision) as think, patch.object(Brain,'manager',return_value=event) as manager:
                runner.work(); runner.work(); runner.work(); runner.work()
                self.assertEqual(think.call_count,2); self.assertEqual(manager.call_count,1)
            self.w=runner.world
            self.assertEqual(self.w.day,1); self.assertFalse(self.w.in_day)
            self.assertEqual(self.w.chapter,1); self.assertEqual(store.load().data(),self.w.data())

    def test_diplomacy_and_population_conservation(self):
        other=self.w.states[1]
        q=next(q for q in self.w.adjacent(self.p) if self.w.cell(q).owner==self.s.id)
        self.w.cell(q).owner=other.id; self.w.cell(q).population=0
        self.w.execute(self.s,action('alliance',cell=self.p,partner=other.id))
        self.assertIn(self.s.id,other.allies)
        old_food=other.stocks['food']
        self.w.execute(self.s,action('trade',cell=self.p,partner=other.id,amount=2,resource='food'))
        self.assertEqual(other.stocks['food'],old_food)
        self.w.execute(other,action('accept_trade',cell=q,offer_id=1))
        self.assertEqual(other.stocks['food'],old_food+2)
        population=sum(c.population for c in self.w.cells)
        self.w.execute(self.s,action('migrate',cell=self.p,partner=other.id,amount=1))
        self.assertEqual(sum(c.population for c in self.w.cells),population)

    def test_equal_combat_destroys_both_without_capture(self):
        u=self.w.units[0]
        target=next(p for p in self.w.adjacent(u['cell']) if not self.w.unit_at(p))
        self.w.cell(target).terrain='grass'; self.w.cell(target).owner='state_2'
        self.w.spawn('state_2',target,'army',u['strength'])
        self.w.execute(self.s,action('army',cell=list(u['cell']),unit_id=u['id'],target_cell=target))
        self.assertNotIn(u,self.w.units); self.assertIsNone(self.w.unit_at(target))
        self.assertEqual(self.w.cell(target).owner,'state_2')

    def test_negative_trade_does_not_create_resources(self):
        with self.assertRaises(RuleError): self.w.execute(self.s,action('trade',cell=self.p,partner='state_2',amount=-10,resource='food'))
        self.assertEqual(self.s.stocks['food'],250)


class BrainTests(unittest.TestCase):
    def test_parse_section_format(self):
        result=parse_json('THINKING: Наблюдаю\nNOTES: Помню\nPLAN: Строю\nACTIONS: [{"type":"do_nothing","args":{}}]')
        self.assertEqual(result['notes'],'Помню'); self.assertEqual(len(result['actions']),1)

    def test_real_http_protocol_and_memory_in_prompt(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"data":[{"id":"local-model"}]}')
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                answer=dict(thinking='Решение',notes='Продолжаю память',plan='План',diplomacy=[dict(to='all',text='Предлагаем сотрудничество')],actions=[action('do_nothing')])
                payload=dict(choices=[dict(message=dict(content=json.dumps(answer)),finish_reason='stop')])
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(payload).encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            brain=Brain(dict(host=f'http://127.0.0.1:{server.server_port}/v1',model='local-model'))
            self.assertEqual(brain.models(),['local-model'])
            w=World(size=24,count=2); s=w.states[0]; s.notes='Моя постоянная память'
            result=brain.think(s,w.context(s)); w.apply_decision(s,result)
            self.assertIn('Моя постоянная память',requests[0]['messages'][1]['content'])
            self.assertIsNone(brain.active); self.assertEqual(s.notes,'Продолжаю память')
            self.assertEqual(len(s.memory),1)
        finally: server.shutdown(); server.server_close()


if __name__=='__main__': unittest.main()
