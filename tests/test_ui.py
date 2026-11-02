import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from planet.dialogs import Dialog,edit_settings
from planet.launcher import choose_world


def drive(action):
    return lambda dialog: [action] if dialog.buttons else []


class MenuTests(unittest.TestCase):
    def test_create_load_and_edit_settings_without_tk(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            config=dict(saves_directory=str(root/'saves'),states=2,host='http://localhost:1234/v1',model='test',context_window=262144)
            with patch.object(Dialog,'events',drive('new')): first=choose_world(root,config)
            first[1].session_lock.close()
            with patch.object(Dialog,'events',drive('load')): second=choose_world(root,config)
            self.assertEqual(first[1].path,second[1].path)
            second[1].session_lock.close()
            with patch.object(Dialog,'events',drive('save')): self.assertTrue(edit_settings(root,config))
            saved=json.loads((root/'config.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['context_window'],262144)
        self.assertEqual(saved['max_tokens'],196608)
        __import__('pygame').quit()

    def test_cyrillic_field_input_and_selection(self):
        dialog=Dialog('Input test'); pg=dialog.pg
        dialog.field('name','Name','old',(10,30,300,35)); dialog.focus('name')
        pg.event.clear()
        pg.event.post(pg.event.Event(pg.KEYDOWN,key=pg.K_a,mod=pg.KMOD_CTRL))
        pg.event.post(pg.event.Event(pg.TEXTINPUT,text='Новая планета'))
        dialog.events(); self.assertEqual(dialog.fields['name']['value'],'Новая планета')
        pg.quit()

    def test_cancel_does_not_create_world(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(Dialog,'events',drive('cancel')):
                self.assertIsNone(choose_world(Path(temp),dict(saves_directory=str(Path(temp)/'saves'))))
            self.assertEqual(list((Path(temp)/'saves').glob('*/manifest.json')),[])


if __name__=='__main__': unittest.main()
