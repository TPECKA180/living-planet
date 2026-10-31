"""Scripted synthetic campaigns, not a claim about live LLM intelligence."""
import argparse,copy,json,math,sys,tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from main import Runner
from planet.engine import World,Store
from planet.modern_catalog import RESOURCE_NAMES,TECHNOLOGIES as MODERN_TECHS
from planet.technology import TECHNOLOGIES as BASE_TECHS

def campaign(mode='normal',days=20,modern=False):
    world=World(size=32,count=2,seed=2026,map_mode=mode)
    for state in world.states:
        state.operations.update(explore=True,recruit=False)
        state.stocks.update(money=200000,metal=20000,resource=20000,food=100000,science=20000,matter=20000)
        if modern:
            state.tech=list(BASE_TECHS)+list(MODERN_TECHS);state.era=2
            state.modern=dict(entered_day=0,unrest=0,debt=0)
            state.stocks.update(dict.fromkeys(RESOURCE_NAMES,1000000))
            for p in world.positions(state.id)[:4]:
                cell=world.cell(p);cell.building='skyscraper';cell.building_level=1;cell.population=300
    accepted=Counter();rejected=Counter()
    with tempfile.TemporaryDirectory() as folder:
        store=Store(Path(folder)/'world.sqlite3');store.save(world)
        runner=Runner(world,store,dict(external_console=False,local_execution=True,local_chronicle=True,manager_every=10))
        def decide(state,context):
            w=runner.world;peer=next(s for s in w.states if s.id!=state.id);actions=[]
            if w.day==3 and state.id==w.states[0].id:actions.append(dict(type='declare_war',args=dict(partner=peer.id,reason='Синтетическая проверка войны и набора')))
            options=context['military']['recruitment_options']
            if options and (w.day%4==1 or context['military']['enemies'] and not context['military']['combat_count']):
                option=next((o for o in options if modern and o['action']['type']=='recruit_modern'),options[0])
                actions.append(copy.deepcopy(option['action']))
            combat_ids={u['id'] for u in context['military']['combat_units']}
            for unit in [u for u in context['mobility'] if u['unit_id'] in combat_ids and u['safe_targets']][:2]:
                actions.append(dict(type='move',args=dict(unit_id=unit['unit_id'],target_cell=unit['safe_targets'][0]['target'])))
            if w.day==2:actions.append(dict(type='trade',args=dict(partner=peer.id,resource='metal',amount=5,price=2)))
            for offer in context.get('trade_offers',[]):
                if offer['partner']==state.id and offer['status']=='open':actions.append(dict(type='accept_trade',args=dict(offer_id=offer['id'])))
            if w.day%5==0:actions.append(dict(type='transfer',args=dict(partner=peer.id,resource='money',amount=10)))
            research=context.get('decision_support',{}).get('research_orders_now',[])
            if research and w.day%2==0:actions.append(copy.deepcopy(research[0]))
            project=next((p for p in context['construction']['projects'] if all(state.stocks.get(k,0)>=v for k,v in p['cost'].items())),None)
            review=dict(choice='build' if project else 'defer',project_id=project['project_id'] if project else None,reason='Синтетическая проверка реальной платной стройки.',revisit_day=w.day+1)
            return dict(thinking='Тест механик, а не ответ живой модели.',notes=state.notes,plan=state.plan,
                diplomacy=[dict(to=peer.id,text=f'Тестовое сообщение дня {w.day}; предложение не равно платежу.')],actions=actions[:10],construction_review=review)
        with patch.object(runner.brain,'think',side_effect=decide),patch.object(runner.brain,'complete',side_effect=AssertionError('No real LLM calls in a synthetic test')):
            for day in range(days):
                for tick in range(30):
                    runner.work()
                    messages=[]
                    while not runner.messages.empty():messages.append(runner.messages.get())
                    failures=[v for k,v in messages if k in ('retry','error')]
                    if failures:raise AssertionError(failures)
                    if runner.world.day==day+1 and not runner.world.in_day:break
                else:raise AssertionError('Day failed to reach idle')
                w=runner.world;loaded=store.load()
                assert loaded.data()==w.data()
                for unit in w.units:
                    assert math.isfinite(unit['strength']) and unit['strength']>0
                    assert unit.get('embarked_on') or (w.cell(unit['cell']).terrain=='water')==(unit['type']=='ship')
                for state in w.states:
                    assert all(math.isfinite(v) for v in state.stocks.values())
                    assert w.at_war(state.id,w.states[1 if state.id==w.states[0].id else 0].id)==(w.conflict_status(state.id,w.states[1 if state.id==w.states[0].id else 0].id)=='ВОЙНА')
                    for row in state.decision_outcome.get('action_results',[]):
                        (accepted if row['success'] else rejected)[row['type']]+=1
        built=sum(c.building is not None for c in runner.world.cells)
        report=dict(mode=mode,epoch=2 if modern else 1,days=runner.world.day,phase=runner.world.phase,
            decisions=len(runner.world.decisions),messages=len(runner.world.messages),units=len(runner.world.units),buildings=built,
            movement_records=len(runner.world.movement_log),chapters=runner.world.chapter,live_llm_calls=0,sqlite_roundtrip=True,invariants=True,
            accepted=dict(accepted),rejected=dict(rejected))
        assert report['decisions']==days*2 and report['messages']>=days*2
        return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--days',type=int,default=20);args=parser.parse_args()
    print(json.dumps([campaign('normal',args.days),campaign('archipelago',args.days),campaign('normal',args.days,True)],ensure_ascii=False))
