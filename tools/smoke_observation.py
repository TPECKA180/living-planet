"""Exercise the actual observation controller, including a transient worker failure."""
from pathlib import Path
import os,sys,json,tempfile,copy,time,argparse
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from planet.engine import World,Store
from main import App

def run(days=40):
    import pygame as pg
    w=World(size=32,count=2,seed=752)
    for state in w.states:
        state.stocks.update(money=200000,metal=20000,food=100000,resource=20000,science=20000,matter=20000)
        state.operations['recruit']=False
    injected=False;frames=0;started=time.monotonic();snapshots=0
    with tempfile.TemporaryDirectory() as folder:
        store=Store(Path(folder)/'world.sqlite3');store.save(w)
        app=App(w,store,dict(model='synthetic',external_console=False,local_execution=True,local_chronicle=True,manager_every=10))
        def decide(state,context):
            nonlocal injected
            if not injected:
                injected=True;raise IndexError('Synthetic transient worker failure')
            options=context['military']['recruitment_options'];actions=[]
            if options and context['day']%5==0:
                option=options[0];order=copy.deepcopy(option['action']);order['args']['count']=min(3,option['max_count']);actions.append(order)
            return dict(owner=state.id,thinking='Программная проверка непрерывного наблюдения.',notes=state.notes,plan=state.plan,actions=actions,diplomacy=[dict(to='all',text='Проверяем общий ход.')])
        def draw():
            nonlocal frames,snapshots
            frames+=1
            if time.monotonic()-started>900:raise AssertionError('Observation test timed out')
            if not app.running and app.world.day<days:raise AssertionError('Observation unexpectedly paused')

        original_message=app.worker_message
        def message(kind,value):
            nonlocal snapshots
            original_message(kind,value)
            if kind=='world' and not app.world.in_day:
                if app.world.day%10==0:print(json.dumps(dict(progress_day=app.world.day)),flush=True)
                if app.world.day>=days:
                    assert app.world.day==days
                    assert store.load().data()==app.runner.world.data();snapshots+=1
                    app.action('run');pg.event.post(pg.event.Event(pg.QUIT))
        app.action('run')
        with patch.object(app,'worker_message',side_effect=message),patch.object(app,'draw',side_effect=draw),patch.object(app.runner.brain,'think',side_effect=decide),patch.object(app.runner.brain,'complete',side_effect=AssertionError('No real LLM calls')),patch('planet.diagnostics.record'):
            app._loop()
        assert injected and snapshots
        armies=sum(u['type']=='army' for u in app.world.units)
        assert armies>1
        rows=[json.loads(s) for s in (store.path.parent/'observation.jsonl').read_text(encoding='utf-8').splitlines()]
        errors=[r for r in rows if r['reason'].startswith('Ошибка шага:')]
        assert len(errors)==1 and errors[0]['mode']=='observe'
        return dict(days=app.world.day,phase=app.world.phase,injected_worker_errors=len(errors),unexpected_pauses=0,armies=armies,sqlite_roundtrip=True,live_llm_calls=0,frames=frames)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--days',type=int,default=40);args=parser.parse_args();print(json.dumps(run(args.days)))
