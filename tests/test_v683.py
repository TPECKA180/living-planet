import copy,io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from main import App
from planet.engine import World,Store
from planet.brain import Brain
from planet.response_io import read_json,stream_lines,ResponseTooLarge
from planet.runtime_config import upgrade_config

class Response(io.BytesIO):
    headers={'Content-Type':'text/event-stream'}

class ResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'world.sqlite3')
        world=World(size=32,count=2);self.store.save(world)
        self.app=App(world,self.store,dict(external_console=False))
    def tearDown(self):
        self.app.close();self.temp.cleanup()

    def test_learning_panel_hover_all_six_resources_no_crash(self):
        self.app.chronicle_tab=1;self.app.draw()
        before=copy.deepcopy(self.app.world.data())
        for rect,key in self.app.resource_rects.copy():
            with self.subTest(resource=key),patch('pygame.mouse.get_pos',return_value=rect.center):self.app.draw()
        self.assertEqual(before,self.app.world.data())

    def test_render_failure_recovers_without_replaying_any_game_actions(self):
        before=self.store.path.read_bytes();world=copy.deepcopy(self.app.runner.world.data())
        with patch.object(self.app,'_loop',side_effect=[KeyError('science'),False]) as loop,patch.object(self.app,'recover_ui',return_value=True) as recovery,patch('planet.diagnostics.record') as log:
            self.app.running=True;self.app.tab=8
            self.assertFalse(self.app.loop())
            self.assertEqual(loop.call_count,2);recovery.assert_called_once();log.assert_called_once()
        self.assertFalse(self.app.running);self.assertEqual(self.app.tab,0)
        self.assertEqual(before,self.store.path.read_bytes());self.assertEqual(world,self.app.runner.world.data())

    def test_recovery_screen_exit_keeps_saved_world(self):
        import pygame as pg
        before=self.store.path.read_bytes()
        with patch('pygame.event.get',return_value=[pg.event.Event(pg.QUIT)]):self.assertFalse(self.app.recover_ui('ошибка'))
        self.assertEqual(before,self.store.path.read_bytes())

    def test_long_prose_renders_visible_lines_and_keeps_all_content(self):
        text='Уникальное решение и оценка риска.\n'*10000
        self.app.screen.set_clip(self.app.pg.Rect(0,0,300,150))
        with patch.object(self.app,'text',wraps=self.app.text) as draw:
            bottom=self.app.wrapped(text,0,0,290)
            self.assertLess(draw.call_count,12)
        lines=self.app.text_layout.lines(text,290,self.app.font)
        self.assertGreater(bottom,100000);self.assertIn('риска.',' '.join(lines))
        self.assertTrue(lines is self.app.text_layout.lines(text,290,self.app.font))
        self.assertLessEqual(self.app.text_layout.used,self.app.text_layout.budget)

    def test_large_unbroken_token_is_split_without_losing_characters(self):
        text='Дипломатия'*12000
        lines=self.app.text_layout.lines(text,280,self.app.font)
        self.assertEqual(''.join(lines),text)
        self.assertTrue(all(self.app.font.size(line)[0]<=280 for line in lines))

    def test_migration_preserves_explicit_limits_and_local_mode_preferences(self):
        config=dict(runtime_patch='6.8.2',max_tokens=32768,context_window=262144,local_execution=False,local_chronicle=False)
        self.assertTrue(upgrade_config(config));self.assertEqual(config['runtime_patch'],'7.5.0')
        self.assertEqual(config['max_tokens'],32768);self.assertEqual(config['context_window'],262144)
        self.assertFalse(config['local_execution']);self.assertFalse(config['local_chronicle']);self.assertFalse(upgrade_config(config))

class ResponseSizeTests(unittest.TestCase):
    def test_json_is_rejected_before_parsing_when_over_limit(self):
        with self.assertRaises(ResponseTooLarge):read_json(io.BytesIO(b'x'*10000),1024)
        self.assertEqual(read_json(io.BytesIO(b'{"ok":true}'),1024),{'ok':True})
    def test_sse_line_and_total_response_are_bounded(self):
        for data in (b'data: '+b'x'*3000,b'\n'*3000):
            with self.assertRaises(ResponseTooLarge):list(stream_lines(io.BytesIO(data),1024))
    def test_full_unicode_stream_is_preserved(self):
        content='Очень большой полный ответ. '*1000
        chunk=json.dumps({'choices':[{'delta':{'content':content}}]},ensure_ascii=False).encode()
        data=b'data: '+chunk+b'\n\ndata: [DONE]\n\n'
        brain=Brain(dict(host='http://localhost',detect_repetition=False))
        with patch('urllib.request.urlopen',return_value=Response(data)):
            result=brain.stream_request({})
        self.assertEqual(result['choices'][0]['message']['content'],content)
    def test_oversized_stream_is_retried_without_applying_partial_json(self):
        brain=Brain(dict(host='http://localhost',context_window=98304,max_tokens=28000))
        valid={'choices':[{'message':{'content':'{"ok":true}'},'finish_reason':'stop'}]}
        with patch.object(brain,'stream_request',side_effect=[ResponseTooLarge('limit'),valid]) as send:
            result=brain.complete('Правила',{},'model')
        self.assertEqual(result,{'ok':True});self.assertEqual(send.call_count,2)
        self.assertEqual(brain.response_limits,{})
