"""Render a brand-new synthetic world; never reads a user world or config."""
import copy,os,sys,tempfile
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from planet.configuration import DEFAULTS
from planet.engine import World,Store
from main import App

def render(destination=None):
    import pygame as pg
    destination=Path(destination or ROOT/'docs/assets/interface.png');destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        config=copy.deepcopy(DEFAULTS);config['external_console']=False
        view=App(World(size=64,count=4,seed=2026),Store(Path(folder)/'preview.sqlite3'),config)
        view.tab=9;view.zoom=1.2;view.status='Новый демонстрационный мир · подключите модель в F2 и начните свою историю'
        view.draw();pg.image.save(view.screen,str(destination));view.close()
    return destination

if __name__=='__main__':print(render())
