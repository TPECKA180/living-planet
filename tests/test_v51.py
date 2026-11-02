import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

from planet.engine import World,Store,RuleError
from planet.brain import Brain,AutomaticRetry
from planet.technology import TECHNOLOGIES,BASE_TECHS,ROWS
from main import Runner


def action(kind,**args): return dict(type=kind,args=args)
def decision():
    return dict(thinking='Расширяем государство',notes='Сохраняем характер',plan='Рост и превосходство',diplomacy=[dict(to='all',text='Обсудим поставки')],actions=[])


class Fixture(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2); self.s,self.enemy=self.w.states
        self.s.stocks.update(money=100000,science=100000,resource=10000,metal=10000,matter=10000,food=10000)
        for state in self.w.states: state.operations.update(explore=False,recruit=False)
        for cell in self.w.cells: cell.terrain='grass'
        self.w.day=1
        self.u=self.w.units[0]
    def own(self): return list(self.u['cell'])
    def research_site(self):
        p=self.own(); cell=self.w.cell(p); cell.terrain='science'; cell.building='lab'; cell.building_level=1
        return p


class WaterTests(Fixture):
    def test_all_land_types_reject_water_with_every_technology_and_no_money_loss(self):
        self.s.tech=list(TECHNOLOGIES)
        for kind in ('scout','builder','army'):
            self.u['type']=kind; p=self.w.adjacent(self.u['cell'])[0]; self.w.cell(p).terrain='water'
            before=self.s.stocks.copy(); original=list(self.u['cell'])
            self.assertIsNone(self.w.find_route(self.u,p))
            with self.assertRaises(RuleError): self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=p))
            self.assertIsNotNone(self.w.step_unit(self.u,p))
            self.assertEqual(self.s.stocks,before); self.assertEqual(self.u['cell'],original)
    def test_land_route_cannot_cut_across_water(self):
        start=self.own(); target=[start[0]+2,start[1]]
        for q in self.w.adjacent(start): self.w.cell(q).terrain='water'
        self.s.tech=['navigation']; self.assertIsNone(self.w.find_route(self.u,target))
    def test_legacy_navigation_walker_relocated_without_changing_funds_or_character(self):
        self.s.tech=['navigation']; old=self.own(); self.w.cell(old).terrain='water'
        self.u['order']=dict(kind='move',target=list(old))
        restored=World.restore(self.w.data()); unit=restored.units[0]
        self.assertNotEqual(restored.cell(unit['cell']).terrain,'water'); self.assertEqual(unit['migration_position']['original'],old)
        self.assertEqual(restored.states[0].stocks,self.s.stocks); self.assertEqual(restored.states[0].notes,self.s.notes)
        self.assertEqual(unit['order']['kind'],'hold')
    def build_ship(self):
        p=[self.u['cell'][0]+1,self.u['cell'][1]]; c=self.w.cell(p); c.terrain='water'; c.owner=None
        self.s.tech=['navigation']; self.w.execute(self.s,action('unit',cell=p,unit='ship',strength=5))
        return self.w.units[-1]
    def test_ship_transports_passenger_and_lands_next_day(self):
        ship=self.build_ship(); source=self.own()
        self.w.execute(self.s,action('embark',unit_id=self.u['id'],ship_id=ship['id']))
        self.assertEqual(self.w.unit_at(ship['cell']),ship)
        target=[ship['cell'][0]+1,ship['cell'][1]]; self.w.cell(target).terrain='water'
        self.w.execute(self.s,action('move',unit_id=ship['id'],target_cell=target))
        self.assertEqual(self.u['cell'],target)
        shore=[target[0],target[1]+1]; self.w.cell(shore).owner=None
        with self.assertRaises(RuleError): self.w.execute(self.s,action('disembark',unit_id=self.u['id'],target_cell=shore))
        self.w.day+=1; self.w.execute(self.s,action('disembark',unit_id=self.u['id'],target_cell=shore))
        self.assertEqual(self.u['cell'],shore); self.assertIsNone(self.u['embarked_on']); self.assertEqual(self.w.cell(shore).owner,self.s.id)
        self.assertEqual(self.w.remaining_moves(self.u),0); self.assertNotEqual(source,shore)
    def test_ship_cannot_walk_land_or_build_without_navigation(self):
        ship=self.build_ship(); funds=self.s.stocks['money']
        with self.assertRaises(RuleError): self.w.execute(self.s,action('move',unit_id=ship['id'],target_cell=self.own()))
        self.assertEqual(self.s.stocks['money'],funds)
        self.s.tech=[]; p=[ship['cell'][0],ship['cell'][1]+1]; self.w.cell(p).terrain='water'
        with self.assertRaises(RuleError): self.w.execute(self.s,action('unit',cell=p,unit='ship',strength=3))
    def test_sinking_carrier_kills_passenger(self):
        ship=self.build_ship(); self.w.execute(self.s,action('embark',unit_id=self.u['id'],ship_id=ship['id']))
        self.w.remove_unit(ship); self.assertNotIn(self.u,self.w.units); self.assertNotIn(ship,self.w.units)
    def test_invalid_standing_water_order_never_charges(self):
        target=self.w.adjacent(self.u['cell'])[0]; self.w.cell(target).terrain='water'
        self.u['order']=dict(kind='move',target=target); self.s.tech=['navigation']; funds=self.s.stocks['money']
        self.w.run_operations(); self.assertEqual(self.s.stocks['money'],funds)


class TechnologyTests(Fixture):
    def test_exactly_twenty_new_technologies_all_researchable_in_dependency_order(self):
        self.assertEqual(len(ROWS),20); self.assertEqual(len(TECHNOLOGIES),25)
        site=self.research_site()
        for key,info in TECHNOLOGIES.items():
            before=self.s.stocks.copy(); self.w.execute(self.s,action('research',cell=site,tech=key))
            for resource in ('money','science','matter'): self.assertEqual(before[resource]-self.s.stocks[resource],info[resource])
            self.assertIn(key,self.s.tech)
    def test_missing_prerequisite_or_matter_is_atomic(self):
        site=self.research_site(); before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.s,action('research',cell=site,tech='universities'))
        self.assertEqual(before,self.w.data()); self.s.tech=['lab','scholarship']; self.s.stocks['matter']=0; before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.s,action('research',cell=site,tech='universities'))
        self.assertEqual(before,self.w.data())
    def test_forecast_matches_income_with_all_technology_bonuses(self):
        self.s.tech=list(TECHNOLOGIES); own=self.w.positions(self.s.id)
        for i,p in enumerate(own):
            c=self.w.cell(p); c.terrain=('grass','forest','mountain','science','resource')[i%5]
            c.building=('castle','tavern','mine','lab','arsenal')[i%5]; c.building_level=2
        forecast=self.w.economic_forecast(self.s); before=self.s.stocks.copy(); self.w.income()
        for key,value in forecast['resources'].items(): self.assertAlmostEqual(self.s.stocks[key]-before[key],value['base_net'])
    def test_each_production_technology_has_documented_effect(self):
        from planet.engine import Cell
        cases=[('irrigation',Cell('grass',4),'food',5),('crop_rotation',Cell('grass',4),'food',5),('forestry',Cell('forest',4),'resource',5),('deep_mining',Cell('mountain',4),'metal',5),('scholarship',Cell('science',4),'science',5),('universities',Cell('science',0,building='lab',building_level=1,population=1),'science',12.5),('steelworks',Cell('mountain',0,building='mine',building_level=1,population=1),'metal',12.5),('banking',Cell('grass',0,building='castle',building_level=1,population=1),'money',17),('taxation',Cell('grass',0),'money',5),('aether_forging',Cell('grass',0,building='arsenal',building_level=1,population=1),'matter',12.5)]
        for tech,cell,key,expected in cases:
            self.s.tech=[tech]; self.assertEqual(self.w.production_for_cell(self.s,cell)[key],expected,tech)
    def test_upkeep_and_speed_and_recruit_discounts(self):
        self.s.tech=['granaries','recycling','logistics','cartography','conscription']
        self.assertEqual(self.w.citizen_upkeep(self.s),dict(food=1.5,resource=.75)); self.assertEqual(self.w.remaining_moves(self.u),6)
        p=next(p for p in self.w.positions(self.s.id) if not self.w.unit_at(p)); money=self.s.stocks['money']
        self.w.execute(self.s,action('unit',cell=p,unit='army',strength=2)); self.assertEqual(money-self.s.stocks['money'],45)
    def test_construction_discounts(self):
        p=next(p for p in self.w.positions(self.s.id) if not self.w.cell(p).building); self.s.tech=['masonry','engineering','agriculture']
        before=self.s.stocks.copy(); self.w.execute(self.s,action('build',cell=p,building='tavern',level=2))
        self.assertEqual(before['money']-self.s.stocks['money'],160); self.assertEqual(before['resource']-self.s.stocks['resource'],30)
        money=self.s.stocks['money']; self.w.execute(self.s,action('upgrade',cell=p,tech='agriculture')); self.assertEqual(money-self.s.stocks['money'],240)
    def test_matter_conversion_and_reinforcement_and_building_upgrade(self):
        p=self.own(); self.s.tech=['alchemy','military_medicine','aether_forging']; self.u['strength']=2
        before=self.s.stocks.copy(); self.w.execute(self.s,action('convert',cell=p,resource='food',amount=10))
        self.assertEqual(self.s.stocks['food']-before['food'],40); self.assertEqual(before['matter']-self.s.stocks['matter'],10)
        self.w.execute(self.s,action('reinforce',unit_id=self.u['id'],amount=3)); self.assertEqual(self.u['strength'],5)
        before=self.s.stocks.copy()
        with self.assertRaises(RuleError): self.w.execute(self.s,action('reinforce',unit_id=self.u['id'],amount=1))
        self.assertEqual(before,self.s.stocks)
        self.w.execute(self.s,action('improve_building',cell=p)); self.assertEqual(self.w.cell(p).building_level,2)
    def test_fortification_reduces_incoming_damage_without_invulnerability(self):
        target=self.w.adjacent(self.u['cell'])[0]; self.w.cell(target).owner=self.enemy.id
        self.w.units=[u for u in self.w.units if u['cell']!=target]
        self.w.spawn(self.enemy.id,target,'army',3); defender=self.w.units[-1]
        self.enemy.tech=['fortification']; self.enemy.stocks.update(money=1000,matter=100,resource=100)
        for _ in range(3): self.w.execute(self.enemy,action('fortify',cell=target))
        source=list(self.u['cell']); self.w.step_unit(self.u,target)
        self.assertEqual(defender['strength'],1); self.assertEqual(self.u['cell'],source)
    def test_fortified_cell_cannot_hold_two_surviving_opponents(self):
        # A surviving defender prevents entry even if the attacker also survives.
        target=self.w.adjacent(self.u['cell'])[0]; self.w.cell(target).owner=self.enemy.id; self.w.cell(target).fortification=3
        self.w.units=[u for u in self.w.units if u['cell']!=target]; self.w.spawn(self.enemy.id,target,'army',3)
        start=list(self.u['cell']); self.w.step_unit(self.u,target)
        self.assertEqual(self.u['cell'],start); self.assertEqual(self.w.cell(target).owner,self.enemy.id)


class RecoveryAndStrategyTests(Fixture):
    def test_bad_schema_is_repaired_with_precise_feedback(self):
        brain=Brain(dict(model='test')); bad=decision(); bad.pop('diplomacy')
        with patch.object(brain,'complete',side_effect=[bad,decision()]) as call:
            result=brain.think(self.s,self.w.context(self.s))
        self.assertIn('decision_correction',call.call_args_list[1].args[1]); self.assertEqual(result,decision())
    def test_non_json_text_receives_format_correction(self):
        brain=Brain(dict(model='test',context_window=98304,manage_model_context=False)); payloads=[]
        def response(payload):
            payloads.append(payload); content='Я пока размышляю.' if len(payloads)==1 else json.dumps(decision(),ensure_ascii=False)
            return dict(choices=[dict(message=dict(content=content),finish_reason='stop')])
        with patch.object(brain,'stream_request',side_effect=response): result=brain.think(self.s,self.w.context(self.s))
        self.assertEqual(result,decision()); self.assertIn('format_correction',payloads[1]['messages'][1]['content'])
    def test_permanent_bad_json_becomes_retry_without_applying_turn(self):
        brain=Brain(dict(model='test',context_window=16384,context_retry_attempts=2))
        response=dict(choices=[dict(message=dict(content='не JSON'),finish_reason='stop')]); before=self.w.data()
        with patch.object(brain,'stream_request',return_value=response):
            with self.assertRaises(AutomaticRetry): brain.think(self.s,self.w.context(self.s))
        self.assertEqual(self.w.data(),before)
    def test_runner_network_error_queues_retry_and_does_not_advance_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner=Runner(self.w,Store(Path(tmp)/'world.sqlite3'),dict(external_console=False))
            with patch.object(runner.brain,'think',side_effect=RuntimeError('Сервер временно выключен')): runner.work()
            queued=list(runner.messages.queue)
            self.assertTrue(any(kind=='retry' for kind,_ in queued)); self.assertEqual(self.w.cursor,0)
    def test_three_days_recover_schema_errors_without_duplicate_income_or_decisions(self):
        self.w.day=0; before=self.s.stocks.copy(); base=self.w.economic_forecast(self.s)
        with tempfile.TemporaryDirectory() as tmp:
            runner=Runner(self.w,Store(Path(tmp)/'world.sqlite3'),dict(external_console=False,model='test'))
            calls=0
            def complete(*args,**kwargs):
                nonlocal calls
                calls+=1
                if calls%2: return dict(thinking='Неполный ответ')
                return decision()
            with patch.object(runner.brain,'complete',side_effect=complete):
                for _ in range(12): runner.work()
            self.assertEqual(runner.world.day,3); self.assertFalse(runner.world.in_day)
            self.assertEqual(len(runner.world.decisions),6); self.assertEqual(calls,12)
            for key,item in base['resources'].items(): self.assertAlmostEqual(runner.world.states[0].stocks[key]-before[key],item['base_net']*3)
            self.assertFalse(any(kind=='error' for kind,_ in list(runner.messages.queue)))
    def test_demand_never_transfers_assets_until_loser_surrenders(self):
        self.w.set_war(self.s.id,self.enemy.id,'Проверка войны'); positions=self.w.positions(self.enemy.id); notes=self.enemy.notes
        self.w.execute(self.s,action('demand_surrender',partner=self.enemy.id,reason='Наше военное превосходство'))
        self.assertEqual(self.w.positions(self.enemy.id),positions); self.assertFalse(self.enemy.eliminated)
        funds=self.s.stocks['money']+self.enemy.stocks['money']
        self.w.execute(self.enemy,action('surrender',partner=self.s.id))
        self.assertTrue(self.enemy.eliminated); self.assertEqual(self.enemy.notes,notes); self.assertEqual(self.w.positions(self.enemy.id),[])
        self.assertEqual(self.s.stocks['money'],funds); self.assertFalse(self.w.at_war(self.s.id,self.enemy.id))
        restored=World.restore(self.w.data()); self.assertTrue(restored.states[1].eliminated)
        with self.assertRaises(RuleError): self.w.execute(self.enemy,action('do_nothing'))
    def test_extinction_requires_loss_of_territory_and_units(self):
        for cell in self.w.cells:
            if cell.owner==self.enemy.id: cell.owner=self.s.id
        self.w.check_eliminations(); self.assertFalse(self.enemy.eliminated)
        self.w.units=[u for u in self.w.units if u['owner']!=self.enemy.id]; self.w.check_eliminations(); self.assertTrue(self.enemy.eliminated)
    def test_strategic_context_has_real_border_targets_and_no_enemy_stock_leak(self):
        target=self.w.adjacent(self.u['cell'])[0]; self.w.cell(target).owner=self.enemy.id
        context=self.w.strategic_context(self.s); self.assertIn(self.enemy.id,context['border_targets'])
        self.assertNotIn('stocks',context['ranking'][1])


class SpriteTests(unittest.TestCase):
    def test_all_six_biomes_have_sixteen_distinct_stable_variants(self):
        import pygame as pg
        from planet.pixel_art import PixelAtlas,PALETTE
        atlas=PixelAtlas()
        for terrain in PALETTE:
            images=[pg.image.tostring(atlas.tile(terrain,i),'RGB') for i in range(16)]
            self.assertEqual(len(set(images)),16,terrain)
            self.assertEqual(images[3],pg.image.tostring(PixelAtlas().tile(terrain,3),'RGB'))


if __name__=='__main__': unittest.main()
