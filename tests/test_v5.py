import copy
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
import sqlite3
from unittest.mock import patch,MagicMock

from planet.engine import World,Store,RuleError
from planet.saves import WorldLibrary
from planet.brain import Brain
from planet.brain import AutomaticRetry
from main import Runner


def action(kind,**args): return dict(type=kind,args=args)


class PassabilityTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2); self.w.start_day(); self.s=self.w.states[0]; self.u=self.w.units[0]
        self.s.operations['recruit']=False

    def test_failed_water_order_cannot_continue_old_order_and_charge_money(self):
        self.u['order']=dict(kind='explore',issued_day=self.w.day-1)
        x,y=self.u['cell']; target=[x+1,y]; self.w.cell(target).terrain='water'
        gold=self.s.stocks['money']; source=list(self.u['cell'])
        with self.assertRaises(RuleError): self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=target))
        self.w.run_operations()
        self.assertEqual(self.s.stocks['money'],gold); self.assertEqual(self.u['cell'],source)
        self.assertEqual(self.u['skip_day'],self.w.day)
        feedback=self.w.mobility_context(self.s)[0]['last_rejected_order']
        self.assertEqual(feedback['target'],target); self.assertEqual(feedback['charged'],0)

    def test_ai_receives_explicit_water_restriction_and_safe_targets(self):
        target=self.w.adjacent(self.u['cell'])[0]; self.w.cell(target).terrain='water'
        item=next(row for row in self.w.mobility_context(self.s) if row['unit_id']==self.u['id'])
        water=next(row for row in item['adjacent_cells'] if row['cell']==target)
        self.assertFalse(water['passable']); self.assertEqual(water['blocked_by'],'wrong_medium')
        for row in item['safe_targets']: self.assertNotEqual(self.w.cell(row['target']).terrain,'water')

    def test_closed_island_does_not_pay_for_another_trapped_scout(self):
        for cell in self.w.cells:
            if cell.owner is None: cell.terrain='water'
        self.s.operations['recruit']=True
        before=self.s.stocks['money']; count=sum(u['owner']==self.s.id for u in self.w.units)
        self.assertEqual(self.w.exploration_recruitment_sites(self.s),[])
        self.w.run_operations()
        self.assertEqual(sum(u['owner']==self.s.id for u in self.w.units),count)
        self.assertEqual(self.s.stocks['money'],before)

    def test_navigation_does_not_make_land_unit_walk_on_water(self):
        target=self.w.adjacent(self.u['cell'])[0]; self.w.cell(target).terrain='water'
        other=self.w.unit_at(target)
        if other: self.w.units.remove(other)
        self.s.tech.append('navigation'); money=self.s.stocks['money']
        with self.assertRaises(RuleError): self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=target))
        self.assertNotEqual(self.u['cell'],target); self.assertEqual(self.s.stocks['money'],money)


class ForecastTests(unittest.TestCase):
    def test_forecast_base_matches_actual_full_income_and_upkeep(self):
        w=World(size=32,count=2); s=w.states[0]; before=copy.deepcopy(s.stocks)
        forecast=w.economic_forecast(s); w.income()
        for key,item in forecast['resources'].items(): self.assertAlmostEqual(s.stocks[key]-before[key],item['base_net'])

    def test_forecast_does_not_change_world_or_spend_funds(self):
        w=World(size=32,count=2); before=w.data(); forecast=w.economic_forecast(w.states[0])
        self.assertEqual(w.data(),before); self.assertTrue(forecast['uncertain'])

    def test_no_production_and_negative_balance_are_distinct(self):
        w=World(size=32,count=2); s=w.states[0]; s.operations['recruit']=False
        forecast=w.economic_forecast(s)
        self.assertEqual(forecast['resources']['metal']['production'],0)
        self.assertEqual(forecast['resources']['metal']['net'],0)
        for pos in w.positions(s.id): w.cell(pos).terrain='mountain'
        s.stocks['food']=8; food=w.economic_forecast(s)['resources']['food']
        self.assertEqual(food['net'],-6); self.assertEqual(food['status'],'critical'); self.assertLess(food['runway_days'],2)

    def test_all_production_arrives_before_any_citizens_are_fed(self):
        w=World(size=32,count=2); s=w.states[0]
        for pos in w.positions(s.id): w.cell(pos).terrain='grass'; w.cell(pos).level=0
        for pos in w.positions(s.id)[-5:]: w.cell(pos).level=10
        s.stocks['food']=0; s.stocks['resource']=100
        population=sum(w.cell(p).population for p in w.positions(s.id))
        w.income()
        self.assertEqual(sum(w.cell(p).population for p in w.positions(s.id)),population)
        self.assertEqual(s.stocks['food'],50-2*population)

    def test_agents_receive_crisis_and_trade_evaluation_data(self):
        w=World(size=32,count=2); s,t=w.states
        p=w.positions(s.id)[0]
        w.execute(s,action('trade',cell=p,partner=t.id,resource='metal',amount=10,price=5))
        context=w.context(t)
        self.assertIn('economy',context); self.assertIn('relations',context)
        self.assertEqual(context['trade_analysis'][0]['offer_id'],1)
        self.assertEqual(context['trade_analysis'][0]['total'],50)

    def test_forecast_and_safety_reserve_respect_the_states_own_policy(self):
        w=World(size=32,count=2); state=w.states[0]; state.operations['reserve_money']=4000
        forecast=w.economic_forecast(state)
        self.assertEqual(forecast['resources']['metal']['planned_cost'],0)
        self.assertEqual(forecast['resources']['money']['reserve'],4000)


class EconomicChoiceTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2); self.a,self.b=self.w.states
        self.p=self.w.positions(self.a.id)[0]; self.q=self.w.positions(self.b.id)[0]

    def test_expensive_unneeded_resource_requires_conscious_risk(self):
        self.w.execute(self.a,action('trade',cell=self.p,partner=self.b.id,resource='food',amount=10,price=30))
        assessment=self.w.assess_trade(self.b,self.w.trade_offers[0]); self.assertEqual(assessment['need'],'low')
        self.assertEqual(assessment['recommendation'],'avoid'); before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.b,action('accept_trade',cell=self.q,offer_id=1))
        self.assertEqual(self.w.data(),before)
        self.w.execute(self.b,action('accept_trade',cell=self.q,offer_id=1,allow_risk=True,reason='Осознанно создаём резерв для будущей войны'))
        self.assertEqual(self.w.trade_offers[0]['status'],'accepted')

    def test_import_for_a_real_deficit_is_recommended(self):
        for pos in self.w.positions(self.b.id): self.w.cell(pos).terrain='mountain'
        self.b.stocks['food']=3
        self.w.execute(self.a,action('trade',cell=self.p,partner=self.b.id,resource='food',amount=20,price=1))
        info=self.w.assess_trade(self.b,self.w.trade_offers[0]); self.assertEqual(info['need'],'high'); self.assertEqual(info['recommendation'],'useful')
        self.w.execute(self.b,action('accept_trade',cell=self.q,offer_id=1))
        self.assertEqual(self.b.stocks['food'],23)

    def test_critical_food_cannot_be_exported_accidentally(self):
        for pos in self.w.positions(self.a.id): self.w.cell(pos).terrain='mountain'
        self.a.stocks['food']=8; before=copy.deepcopy(self.a.stocks)
        with self.assertRaises(RuleError): self.w.execute(self.a,action('trade',cell=self.p,partner=self.b.id,resource='food',amount=5,price=1))
        self.assertEqual(self.a.stocks,before); self.assertEqual(self.w.trade_offers,[])

    def test_deliberate_risky_exports_are_possible_without_resource_magic(self):
        for pos in self.w.positions(self.a.id): self.w.cell(pos).terrain='mountain'
        self.a.stocks['food']=8
        self.w.execute(self.a,action('trade',cell=self.p,partner=self.b.id,resource='food',amount=5,price=1,allow_risk=True,reason='Принимаем риск ради политического соглашения'))
        total=self.a.stocks['food']+self.b.stocks['food']
        self.w.execute(self.b,action('accept_trade',cell=self.q,offer_id=1))
        self.assertEqual(self.a.stocks['food'],3)
        self.assertEqual(self.a.stocks['food']+self.b.stocks['food'],total)


class RelationsTests(unittest.TestCase):
    def setUp(self): self.w=World(size=32,count=3); self.a,self.b,self.c=self.w.states

    def test_private_judgement_is_saved_and_not_sent_to_other_agents(self):
        self.w.execute(self.a,action('relationship',partner=self.b.id,trust=-55,stance='rival',trade_policy='avoid',memo='Скрытый план давления',grievance='Нас обманули в переговорах'))
        own=self.w.context(self.a); other=self.w.context(self.c)
        self.assertIn('Скрытый план давления',json.dumps(own,ensure_ascii=False))
        self.assertNotIn('Скрытый план давления',json.dumps(other,ensure_ascii=False))
        restored=World.restore(self.w.data()); self.assertEqual(restored.relation(self.a.id,self.b.id)['trust'],-55)

    def test_war_and_peace_require_actual_actions_and_both_sides_for_peace(self):
        self.w.execute(self.a,action('declare_war',partner=self.b.id,reason='Спор о ресурсных клетках'))
        self.assertTrue(self.w.at_war(self.a.id,self.b.id)); self.assertLess(self.w.relation(self.b.id,self.a.id)['trust'],0)
        self.w.execute(self.a,action('peace',partner=self.b.id)); self.assertTrue(self.w.at_war(self.a.id,self.b.id))
        self.w.execute(self.b,action('peace',partner=self.a.id)); self.assertFalse(self.w.at_war(self.a.id,self.b.id))

    def test_old_opinion_cannot_erase_an_attack_in_the_same_common_day(self):
        w=World(size=32,count=2); w.start_day(); a,b=w.states
        w.pending_decisions[a.id]=dict(thinking='Решение',notes=a.notes,plan=a.plan,diplomacy=[],actions=[],
            relation_reviews={b.id:dict(trust=10,stance='friend',trade_policy='normal',memo='Утренняя оценка партнёра')})
        w.pending_decisions[b.id]=dict(thinking='Решение',notes=b.notes,plan=b.plan,diplomacy=[],
            actions=[action('declare_war',partner=a.id,reason='Захват ресурсных клеток')])
        w.resolve_round()
        record=w.relation(a.id,b.id)
        self.assertLess(record['trust'],0); self.assertEqual(record['stance'],'enemy')
        self.assertTrue(record['grievances'])

    def test_embargo_blocks_real_trade(self):
        self.w.execute(self.a,action('embargo',partner=self.b.id,enabled=True))
        with self.assertRaises(RuleError): self.w.execute(self.b,action('trade',cell=self.w.positions(self.b.id)[0],partner=self.a.id,resource='metal',amount=5,price=1))
        self.w.execute(self.a,action('embargo',partner=self.b.id,enabled=False))
        self.assertFalse(self.w.economic_block(self.a.id,self.b.id))

    def test_completed_trade_records_payments_and_trust(self):
        self.w.execute(self.a,action('trade',cell=self.w.positions(self.a.id)[0],partner=self.b.id,resource='metal',amount=5,price=2))
        self.w.execute(self.b,action('accept_trade',cell=self.w.positions(self.b.id)[0],offer_id=1))
        record=self.w.relation(self.b.id,self.a.id)
        self.assertEqual(record['imports']['metal'],5); self.assertEqual(record['paid'],10); self.assertEqual(record['trade_count'],1)

    def test_actual_attack_creates_factual_grievance_and_war(self):
        unit=self.w.units[0]; target=next(p for p in self.w.adjacent(unit['cell']) if not self.w.unit_at(p))
        self.w.cell(target).terrain='grass'; self.w.cell(target).owner=self.b.id
        self.w.execute(self.a,action('move',unit_id=unit['id'],target_cell=target))
        self.assertTrue(self.w.at_war(self.a.id,self.b.id))
        self.assertTrue(any(f['kind']=='territory_loss' for f in self.w.relation(self.b.id,self.a.id)['facts']))

    def test_new_prose_fields_are_translated_without_changing_political_values(self):
        value=dict(thinking='План',notes='Память',plan='Развитие',diplomacy=[],actions=[action('relationship',partner='state_2',trust=-40,stance='rival',memo='We must never trust this neighbor again.')])
        brain=Brain({})
        with patch.object(brain,'complete',return_value={'actions.0.args.memo':'Больше не доверяем этому соседу.'}): result=brain.russify(value,'test')
        self.assertEqual(result['actions'][0]['args']['trust'],-40)
        self.assertEqual(result['actions'][0]['args']['memo'],'Больше не доверяем этому соседу.')

    def test_private_review_fills_missing_dossier_without_regenerating_public_decision(self):
        w=World(size=32,count=2); state=w.states[0]; context=w.context(state)
        decision=dict(thinking='Выбираем развитие',notes='Скрываем намерения',plan='Торг и разведка',diplomacy=[],actions=[action('do_nothing')])
        response=dict(reviews={'state_2':dict(trust=-20,stance='rival',trade_policy='normal',memo='Уникальный тайный расчёт: осторожно использовать поставки соседа.')})
        brain=Brain({})
        with patch.object(brain,'complete',return_value=response) as complete:
            reviewed=brain.review_relationships(state,context,decision)
            second=brain.review_relationships(state,context,reviewed)
            self.assertEqual(complete.call_count,1)
        self.assertEqual(reviewed['actions'],decision['actions']); self.assertEqual(second,reviewed)
        w.apply_decision(state,reviewed)
        self.assertEqual(w.relation(state.id,'state_2')['trust'],-20)
        self.assertNotIn('Уникальный тайный расчёт',json.dumps(w.context(w.states[1]),ensure_ascii=False))

    def test_review_failure_retains_public_decisions_and_completed_reviews(self):
        with tempfile.TemporaryDirectory() as temp:
            w=World(size=32,count=2); w.start_day(); w.phase='resolution'; w.cursor=2
            for state in w.states:
                w.pending_decisions[state.id]=dict(thinking='Решение',notes='Характер',plan='План',diplomacy=[],actions=[])
            store=Store(Path(temp)/'world.sqlite3'); store.save(w); runner=Runner(w,store,dict(review_relations=True))
            first=copy.deepcopy(w.pending_decisions['state_1']); first['relation_reviews']={'state_2':dict(trust=0,stance='neutral',trade_policy='normal',memo='Осторожно наблюдаем')}
            with patch.object(runner.brain,'review_relationships',side_effect=[first,AutomaticRetry('Повтор контекста')]): runner.work()
            saved=store.load()
            self.assertIn('relation_reviews',saved.pending_decisions['state_1'])
            self.assertEqual(saved.phase,'preparing'); self.assertEqual(saved.cursor,2)
            self.assertEqual(saved.states[0].relations['state_2']['memo'],'')
            self.assertEqual(saved.states[0].notes,w.states[0].notes)


class SaveAndArtTests(unittest.TestCase):
    def test_each_state_can_open_its_own_relations_window_without_duplicates(self):
        from main import App
        import pygame as pg
        with tempfile.TemporaryDirectory() as temp:
            w=World(size=32,count=2); store=Store(Path(temp)/'world.sqlite3'); store.save(w)
            app=App(w,store,{})
            process=MagicMock(); process.poll.return_value=None
            with patch('main.subprocess.Popen',return_value=process) as spawn:
                app.open_relations(); app.open_relations(); self.assertEqual(spawn.call_count,1)
                app.selected=1; app.open_relations(); self.assertEqual(spawn.call_count,2)
                self.assertEqual(set(app.relation_windows),{'state_1','state_2'})
        pg.quit()

    def test_v4_snapshot_migrates_with_characters_resources_and_pending_preserved(self):
        world=World(size=32,count=2); world.start_day(); world.cursor=1; world.pending_decisions['state_1']={'notes':'Готовое решение'}
        data=world.data(); data['version']=4
        for state in data['states']: state.pop('relations')
        restored=World.restore(data)
        for old,new in zip(data['states'],restored.states):
            for key in ('notes','plan','memory','history','stocks'): self.assertEqual(old[key],getattr(new,key))
        self.assertEqual(data['pending_decisions'],restored.pending_decisions)
        self.assertEqual(restored.day,world.day); self.assertEqual(restored.cursor,1)
        self.assertEqual(restored.rules_version,6)

    def test_invalid_legacy_water_order_is_suspended_but_not_lost(self):
        w=World(size=32,count=2); target=[0,0]; w.cell(target).terrain='water'; order=dict(kind='move',target=target,issued_day=1)
        w.units[0]['order']=order; data=w.data(); data['version']=4
        restored=World.restore(data)
        self.assertEqual(restored.units[0]['suspended_order'],order); self.assertEqual(restored.units[0]['order']['kind'],'hold')

    def test_biomes_and_buildings_have_distinct_pixel_art(self):
        import pygame as pg
        from planet.pixel_art import PixelAtlas
        atlas=PixelAtlas()
        images=[pg.image.tostring(atlas.tile(name,0),'RGB') for name in ('grass','forest','mountain','water','science','resource')]
        self.assertEqual(len(set(images)),6)
        buildings=[pg.image.tostring(atlas.building(name,(92,207,178)),'RGBA') for name in ('lab','castle','mine','tavern','arsenal')]
        self.assertEqual(len(set(buildings)),5)

    def test_relation_window_uses_read_only_saved_state(self):
        from planet.relations_window import read_world
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'world.sqlite3'; store=Store(path); world=World(size=32,count=2); store.save(world)
            before=path.read_bytes(); loaded=read_world(path)
            self.assertEqual(before,path.read_bytes()); self.assertEqual(loaded.day,world.day)


if __name__=='__main__': unittest.main()
