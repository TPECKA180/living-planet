import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from planet.configuration import DEFAULTS,load_config
from planet.engine import World,Store
from planet.dialogs import Dialog,edit_settings
from main import App

class PublicReleaseTests(unittest.TestCase):
    def test_first_launch_creates_only_clean_local_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            config=load_config(folder)
            self.assertEqual(config['model'],'');self.assertEqual(config['api_key'],'')
            self.assertEqual(config['saves_directory'],'saves')
            self.assertEqual(list(Path(folder).iterdir()),[Path(folder)/'config.json'])
            config['state_models']['state_1']='changed'
            self.assertEqual(DEFAULTS['state_models'],{})
    def test_existing_settings_are_retained_and_invalid_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json';path.write_text('{"model":"fixture-model","max_tokens":32768}',encoding='utf-8')
            self.assertEqual(load_config(folder)['max_tokens'],32768)
            path.write_text('broken',encoding='utf-8');before=path.read_bytes()
            with self.assertRaises(ValueError):load_config(folder)
            self.assertEqual(path.read_bytes(),before)
    def test_settings_save_preserves_limits_and_supports_api_key(self):
        import pygame as pg
        with tempfile.TemporaryDirectory() as folder:
            config=copy.deepcopy(DEFAULTS);config.update(model='fixture-model',api_key='fixture-token',context_memories=73)
            with patch.object(Dialog,'events',return_value=['save']):self.assertTrue(edit_settings(folder,config))
            saved=json.loads((Path(folder)/'config.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['api_key'],'fixture-token');self.assertEqual(saved['context_memories'],73)
            self.assertEqual(saved['input_tokens'],56000)
            pg.quit()
    def test_secret_field_never_renders_the_token(self):
        dialog=Dialog('Test',(800,300));dialog.field('api_key','API','fixture-private-token',(20,70,400,35),secret=True)
        with patch.object(dialog,'label') as render:dialog.draw_fields()
        self.assertFalse(any('fixture-private-token' in str(call.args) for call in render.call_args_list))
        dialog.pg.quit()
    def test_unconfigured_start_stays_paused_with_useful_status(self):
        with tempfile.TemporaryDirectory() as folder:
            view=App(World(size=24,count=2),Store(Path(folder)/'world.sqlite3'),copy.deepcopy(DEFAULTS))
            with patch.object(view.runner,'tick') as tick:
                view.action('run');self.assertFalse(view.running);tick.assert_not_called()
                self.assertIn('F2',view.status)
            view.close()
    def test_six_countries_all_tabs_and_resource_hovers_render_on_small_window(self):
        import pygame as pg
        with tempfile.TemporaryDirectory() as folder:
            view=App(World(size=32,count=6),Store(Path(folder)/'world.sqlite3'),dict(external_console=False))
            view.screen=pg.display.set_mode((1120,760))
            for selected in range(6):
                view.selected=selected
                for tab in range(10):
                    view.tab=tab;view.chronicle_tab=tab%2;view.draw()
                    rect,key=view.resource_rects[tab%6]
                    with patch('pygame.mouse.get_pos',return_value=rect.center):view.draw()
            view.close()

