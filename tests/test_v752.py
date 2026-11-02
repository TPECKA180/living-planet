import os,copy,json,tempfile,unittest,hashlib,time
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from planet.engine import World,Store
from planet.runtime_config import upgrade_config
from planet.military_ai import MILITARY_RULES
from main import App

class SmallPatchTests(unittest.TestCase):
    def test_upgrade_from_751_changes_only_version_marker(self):
        c=dict(runtime_patch='7.5.1',input_tokens=57000,max_tokens=123456,context_window=220000,temperature=.43,local_execution=False,model='test',external_console=False)
        before=copy.deepcopy(c);self.assertTrue(upgrade_config(c));before['runtime_patch']='7.5.2';self.assertEqual(c,before);self.assertFalse(upgrade_config(c))
    def test_prompt_changes_only_one_batch_recruitment_paragraph(self):
        lines=MILITARY_RULES.splitlines(keepends=True);added=[s for s in lines if s.startswith('НЕСКОЛЬКО АРМИЙ')]
        self.assertEqual(len(added),1);self.assertIn('count:N',added[0]);self.assertIn('критически важно',added[0])
        old=''.join(s for s in lines if not s.startswith('НЕСКОЛЬКО АРМИЙ'))
        self.assertEqual(hashlib.sha256(old.encode()).hexdigest(),'2bce58878dd94a2ab07d93abd8d63c48e88df0f2466902b08ba69cdb1fb0ffcc')
    def test_wartime_group_of_three_is_paid_not_limited_to_one(self):
        w=World(size=32,count=2);w.day=1;a,b=w.states;a.stocks.update(money=5000,metal=1000);w.set_war(a.id,b.id,'Проверка найма')
        option=w.context(a)['military']['recruitment_options'][0];self.assertGreaterEqual(option['max_count'],3)
        action=copy.deepcopy(option['action']);action['args']['count']=3;before=dict(a.stocks);count=len(w.units);w.execute(a,action)
        self.assertEqual(len(w.units),count+3)
        for key,value in option['cost'].items():self.assertEqual(before[key]-a.stocks[key],value*3)

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'world.sqlite3');self.world=World(size=24,count=2);self.store.save(self.world)
        self.app=App(self.world,self.store,dict(model='test',external_console=False,local_execution=True,local_chronicle=True))
    def tearDown(self):self.app.close();self.temp.cleanup()
    def messages(self):
        while not self.app.runner.messages.empty():self.app.worker_message(*self.app.runner.messages.get())
    def test_worker_failure_keeps_observing_and_next_step_continues_same_day(self):
        self.app.action('run');self.app.runner.busy=True
        with patch.object(self.world,'context',side_effect=IndexError('temporary')),patch('planet.diagnostics.record'):self.app.runner.work()
        self.messages();self.assertTrue(self.app.running);self.assertFalse(self.app.runner.busy);self.assertIsNone(self.app.target_day);self.assertGreater(self.app.retry_after,time.monotonic())
        self.assertEqual(self.app.runner.world.day,1);self.assertEqual(self.app.runner.world.cursor,0)
        a=self.app.runner.world.states[0];d=dict(owner=a.id,thinking='Продолжение сохранённого хода',notes=a.notes,plan=a.plan,diplomacy=[dict(to='all',text='Продолжаем переговоры.')],actions=[])
        with patch.object(self.app.runner.brain,'think',return_value=d):self.app.runner.work()
        self.messages();self.assertTrue(self.app.running);self.assertEqual(self.app.world.day,1);self.assertEqual(self.app.world.cursor,1);self.assertEqual(self.app.error,'')
    def test_manual_pause_is_not_cancelled_by_error_or_world_update(self):
        self.app.action('run');self.app.action('run');reason=self.app.pause_reason
        self.app.worker_message('world',self.world.data());self.app.worker_message('retry','попробуем позже')
        self.assertFalse(self.app.running);self.assertEqual(self.app.status,reason)
        self.app.worker_message('error','ошибка');self.assertFalse(self.app.running)
    def test_single_day_still_stops_at_requested_boundary_with_reason(self):
        self.app.action('day');target=self.app.target_day;d=self.world.data();d.update(day=target,in_day=False,phase='idle')
        self.app.worker_message('world',d);self.assertFalse(self.app.running);self.assertIsNone(self.app.target_day);self.assertIn('одиночный день завершён',self.app.status)
        rows=[json.loads(s) for s in (self.store.path.parent/'observation.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[-1]['mode'],'paused');self.assertIn('одиночный',rows[-1]['reason'])
    def test_error_in_single_day_is_visible_and_does_not_start_observation(self):
        self.app.action('day');self.app.worker_message('error','нештатная ошибка');self.assertFalse(self.app.running);self.assertIn('Пауза после ошибки',self.app.status)
    def test_settings_pause_waits_for_saved_response_and_remains_explicit(self):
        self.app.action('run');self.app.runner.busy=True;self.app.action('settings')
        self.assertFalse(self.app.running);self.assertIn('настроек',self.app.status);self.assertIsNone(self.app.target_day)

if __name__=='__main__':unittest.main()
