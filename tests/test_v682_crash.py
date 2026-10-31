import copy
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import tempfile
import unittest
from pathlib import Path

from planet.diagnostics import record
from planet.engine import Store,World
from planet.pixel_art import PixelAtlas

class CrashRegressionTests(unittest.TestCase):
    def test_zoom_cache_limits_bytes_instead_of_number_of_images(self):
        import pygame as pg
        atlas=PixelAtlas(scaled_budget=1024*1024)
        surfaces=[pg.Surface((32,32),pg.SRCALPHA) for _ in range(20)]
        for size in (64,128,256,384,512,128,256):
            for surface in surfaces:
                result=atlas.sized(surface,size)
                self.assertEqual(result.get_size(),(size,size))
                actual=sum(s.get_pitch()*s.get_height() for s in atlas.scaled.values())
                self.assertLessEqual(actual,atlas.scaled_budget)
                self.assertEqual(atlas.scaled_bytes,actual)

    def test_large_sprite_is_drawn_without_exceeding_cache(self):
        import pygame as pg
        atlas=PixelAtlas(scaled_budget=1024)
        result=atlas.sized(pg.Surface((32,32)),256)
        self.assertEqual(result.get_size(),(256,256))
        self.assertEqual(atlas.scaled_bytes,0)

    def test_cache_keeps_recent_sprites_and_exact_pixels(self):
        import pygame as pg
        atlas=PixelAtlas(scaled_budget=3*64*64*4)
        surfaces=[pg.Surface((32,32),pg.SRCALPHA) for _ in range(4)]
        for i,s in enumerate(surfaces): s.fill((i*50,20,30,255))
        first=atlas.sized(surfaces[0],64)
        atlas.sized(surfaces[1],64);atlas.sized(surfaces[2],64)
        self.assertIs(atlas.sized(surfaces[0],64),first)
        atlas.sized(surfaces[3],64)
        self.assertIn((id(surfaces[0]),64),atlas.scaled)
        self.assertNotIn((id(surfaces[1]),64),atlas.scaled)
        self.assertEqual(first.get_at((33,33)),(0,20,30,255))

    def test_incomplete_pending_and_legacy_prose_do_not_crash_strategy_tab(self):
        import pygame as pg
        from main import App
        with tempfile.TemporaryDirectory() as folder:
            app=App(World(size=32,count=2),Store(Path(folder)/'test.sqlite3'),dict(external_console=False))
            app.tab=8;sid=app.world.states[0].id
            for assessment in ({'objective':'План'},['повреждено'],{'objective':None}):
                pending=dict(strategic_assessment=assessment,military_response={'choice':[],'reason':None})
                app.world.pending_decisions[sid]=pending
                before=copy.deepcopy(app.world.data())
                app.draw()
                self.assertEqual(app.world.data(),before)
                app.world.states[0].strategic_assessment=assessment
                app.world.pending_decisions[sid]={}
                app.draw()
            pg.quit()

    def test_traceback_persists_and_redacts_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            try: raise ValueError('Bearer secret123 sk-testing-secret123')
            except ValueError as exc: path=record(folder,exc,'test-stage')
            text=path.read_text(encoding='utf-8')
            self.assertIn('ValueError',text);self.assertIn('test-stage',text)
            self.assertNotIn('secret123',text);self.assertNotIn('sk-testing-secret123',text)
