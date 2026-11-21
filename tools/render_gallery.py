"""Capture actual UI views of staged synthetic worlds, without a model or user data."""
import copy
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from planet.configuration import DEFAULTS
from planet.engine import World,Store
from planet.modern_catalog import RESOURCE_NAMES,TECHNOLOGIES as MODERN_TECHS
from planet.technology import TECHNOLOGIES
from main import App


def fixture(mode='normal',modern=False):
    world=World(size=64,count=4,seed=2026,map_mode=mode)
    for state in world.states:
        state.stocks.update(dict.fromkeys(RESOURCE_NAMES,25000))
        state.thinking='Демонстрационное состояние интерфейса. Нейросеть не вызывалась.'
        state.notes='Синтетический мир для документации. Личные сохранения не используются.'
        state.plan='Показать карту, проекты, исследования и фактические ограничения движка.'
    state=world.states[0]
    if modern:
        state.tech=list(TECHNOLOGIES)+list(MODERN_TECHS);state.era=2
        state.modern=dict(entered_day=0,unrest=0,debt=0)
        positions=[p for p in world.positions(state.id) if world.cell(p).terrain!='water']
        buildings=['skyscraper','waterworks','coal_mine','coal_power','steel_mill','concrete_plant','housing_block']
        for pos,building in zip(positions,buildings):
            cell=world.cell(pos);cell.building=building;cell.building_level=1
            cell.population=300 if building=='skyscraper' else 10
    peer=world.states[1]
    def order(kind,**args):return dict(type=kind,args=args)
    world.execute(state,order('offer_exchange',partner=peer.id,give=dict(food=100),receive=dict(money=200),mode='secure',reason='Синтетический пример взаимного обмена для документации.'))
    world.execute(peer,order('accept_exchange',exchange_id=world.exchanges[-1]['id']))
    world.execute(state,order('offer_exchange',partner=peer.id,give=dict(metal=80),receive=dict(money=240),mode='advance',reason='Демонстрационный открытый договор; вторая сторона ещё не согласилась.'))
    world.relation(state.id,peer.id)['memo']='Демонстрационное досье: первый обмен исполнен, новое предложение пока открыто. Последующие намерения модели здесь не моделируются.'
    world.send_message(peer,state.id,'Демонстрационное письмо: первый обмен принят. Следующее предложение ещё требует отдельного согласия.')
    return world


def render():
    import pygame as pg
    from planet.relations_window import RelationsView
    from planet.industry_window import IndustryView
    from planet.world_history import write_history
    assets=ROOT/'docs/assets';assets.mkdir(parents=True,exist_ok=True)
    paths=[]
    def capture(screen,name):
        path=assets/(name+'.png');pg.image.save(screen,str(path));paths.append(path)
    config=copy.deepcopy(DEFAULTS);config['external_console']=False
    with tempfile.TemporaryDirectory() as folder:
        def app(world,name):return App(world,Store(Path(folder)/(name+'.sqlite3')),config)
        view=app(fixture(),'normal');view.status='ДЕМОНСТРАЦИОННЫЙ МИР · постановочное состояние · без запросов модели'
        view.draw();capture(view.screen,'world');capture(view.screen,'interface')
        view.tab=9;view.draw();capture(view.screen,'construction')
        view.tab=6;view.draw();capture(view.screen,'technology')
        center=view.world.positions(view.world.states[0].id)[0]
        view.zoom=8;view.draw()
        view.pan=[view.map_rect.centerx-view.origin[0]-(center[0]+.5)*view.scale,
                  view.map_rect.centery-view.origin[1]-(center[1]+.5)*view.scale]
        view.draw();capture(view.screen,'closeup');view.close()
        view=app(fixture('archipelago'),'islands');view.status='АРХИПЕЛАГ · синтетический мир · seed 2026'
        view.draw();capture(view.screen,'archipelago');view.close()
        world=fixture();relations=RelationsView(world,world.states[0].id)
        relations.draw();capture(relations.screen,'relations');pg.quit()
        world=fixture(modern=True);industry=IndustryView(world,world.states[0].id)
        for tab,name in ((0,'industry'),(1,'factories'),(5,'trade')):
            industry.tab=tab;industry.scroll=0;industry.draw();capture(industry.screen,name)
        pg.quit()
        world=fixture()
        for _ in range(10):
            world.start_day()
            world.pending_decisions={s.id:dict(thinking='Синтетический день без приказов модели.',notes=s.notes,plan=s.plan,diplomacy=[],actions=[]) for s in world.states}
            world.resolve_round();write_history(world);world.in_day=False;world.phase='idle';world.cursor=0
        view=app(world,'history');view.chronicle_tab=2
        view.status='ЛЕТОПИСЬ · 10 синтетических дней без модели · демонстрационные начальные запасы'
        view.draw();capture(view.screen,'history');view.close()
    return paths


if __name__=='__main__':
    for path in render():print(path.relative_to(ROOT))
