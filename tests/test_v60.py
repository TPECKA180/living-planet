import copy,json,tempfile,unittest,math
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store,RuleError
from planet.modern_catalog import RESOURCE_NAMES,MODERN_RESOURCES,BUILDINGS,TECHNOLOGIES,UNITS,MISSILES
from planet.brain import Brain
from planet.isolation import checked_context


def act(kind,**args): return dict(type=kind,args=args)


class EraFixture(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2); self.s,self.other=self.w.states; self.w.day=10
        for state in self.w.states: state.operations.update(explore=False,recruit=False)
        for c in self.w.cells: c.terrain='grass'
        self.own=self.w.positions(self.s.id); self.lab=self.own[0]; c=self.w.cell(self.lab); c.terrain='science'; c.building='lab'; c.building_level=1
        self.s.stocks.update(money=1000000,science=1000000,matter=1000000,food=1000000,resource=1000000,metal=1000000)
    def grant(self,state=None,all_tech=True):
        state=state or self.s; state.tech.extend(k for k in TECHNOLOGIES if k not in state.tech and (all_tech or k=='industrialization'))
        state.era=2; state.modern=dict(entered_day=0,unrest=0,debt=0); state.stocks.update(dict.fromkeys(RESOURCE_NAMES,1000000))
    def free(self):
        return next(p for p in self.own if not self.w.cell(p).building and not self.w.unit_at(p))
    def build(self,key,level=1,p=None):
        p=p or self.free(); self.w.execute(self.s,act('build',cell=p,building=key,level=level)); return p
    def populate(self,n=1000):
        for p in self.own: self.w.cell(p).population=0
        left=n
        while left:
            p=self.free(); self.build('skyscraper',p=p); take=min(500,left); self.w.cell(p).population=take; left-=take
    def population(self,state=None): return sum(self.w.cell(p).population for p in self.w.positions((state or self.s).id))


class EpochTests(EraFixture):
    def test_transition_is_personal_expensive_and_initializes_only_own_new_stocks(self):
        self.s.tech=list(TECHNOLOGIES['industrialization']['requires']); before=copy.deepcopy(self.s.stocks)
        self.w.execute(self.s,act('research',cell=self.lab,tech='industrialization'))
        self.assertEqual(self.w.era_for(self.s),2); self.assertEqual(self.w.era_for(self.other),1)
        for k,v in TECHNOLOGIES['industrialization']['cost'].items(): self.assertEqual(self.s.stocks[k],before[k]-v)
        self.assertTrue(all(self.s.stocks[k]==0 for k in MODERN_RESOURCES)); self.assertNotIn('steel',self.other.stocks)
    def test_insufficient_transition_does_not_charge_or_grant_era(self):
        self.s.tech=list(TECHNOLOGIES['industrialization']['requires']); self.s.stocks['matter']=3999; before=copy.deepcopy(self.s.stocks)
        self.assertRaises(RuleError,self.w.execute,self.s,act('research',cell=self.lab,tech='industrialization'))
        self.assertEqual(before,self.s.stocks); self.assertEqual(self.w.era_for(self.s),1)
    def test_cannot_skip_transition_or_copy_opponents_epoch(self):
        self.grant(self.other)
        for action in (act('build',cell=self.free(),building='coal_mine'),act('research',cell=self.lab,tech='urban_planning'),act('edict',edict='population_campaign',amount=100),act('recruit_modern',cell=self.free(),unit='motorized')):
            before=copy.deepcopy(self.s.stocks); self.assertRaises(RuleError,self.w.execute,self.s,action); self.assertEqual(self.s.stocks,before)
        self.assertEqual(self.w.era_for(self.s),1)
    def test_era_catalog_is_gated_and_additional_science_is_actually_paid(self):
        self.assertNotIn('highrise',[t['id'] for t in self.w.research_catalog(self.s)])
        self.grant(); self.s.tech.remove('highrise'); self.s.stocks['engineering_science']=799
        self.assertRaises(RuleError,self.w.execute,self.s,act('research',cell=self.lab,tech='highrise'))
        self.s.stocks['engineering_science']=800; self.w.execute(self.s,act('research',cell=self.lab,tech='highrise')); self.assertEqual(self.s.stocks['engineering_science'],0)
    def test_capture_does_not_unlock_epoch_or_operate_factory(self):
        self.grant(); p=self.build('weapons_factory_1'); self.w.cell(p).owner=self.other.id
        self.assertEqual(self.w.era_for(self.other),1); self.assertEqual(self.w.production_for_cell(self.other,self.w.cell(p))['matter'],0)
        self.assertRaises(RuleError,self.w.execute,self.other,act('factory_policy',cell=p,enabled=True))


class ScaleTests(EraFixture):
    def setUp(self): super().setUp(); self.grant()
    def test_skyscraper_holds_500_and_cannot_stack_population_past_capacity(self):
        p=self.build('skyscraper'); self.assertEqual(self.w.population_capacity(self.s,self.w.cell(p)),500)
        self.w.execute(self.s,act('edict',edict='population_campaign',amount=500)); self.assertEqual(self.w.cell(p).population,500)
        self.assertEqual(self.population(),503); self.assertRaises(RuleError,self.w.execute,self.s,act('edict',edict='population_campaign',amount=100))
    def test_population_edict_is_paid_and_failed_capacity_leaves_everything_unchanged(self):
        for p in self.own: self.w.cell(p).population=20
        before=self.w.data(); self.assertRaises(RuleError,self.w.execute,self.s,act('edict',edict='population_campaign',amount=100)); self.assertEqual(self.w.data(),before)
        p=self.free(); self.w.cell(p).population=0; self.build('skyscraper',p=p)
        money,food,raw=(self.s.stocks[k] for k in ('money','food','resource')); self.w.execute(self.s,act('edict',edict='population_campaign',amount=100))
        self.assertEqual(self.s.stocks['money'],money-2500); self.assertEqual(self.s.stocks['food'],food-4000); self.assertEqual(self.s.stocks['resource'],raw-500)
    def test_industrial_farm_requires_more_than_100_workers_and_produces_thousands(self):
        farm=self.build('industrial_farm')
        for p in self.own: self.w.cell(p).population=0
        self.w.cell(farm).population=200 # 110 working adults: not enough for 120 jobs.
        row=next(r for r in self.w.industrial_plan(self.s)['buildings'] if r['cell']==farm); self.assertEqual(row['utilization'],0); self.assertIn('labor',row['bottlenecks'])
        self.populate(500); row=next(r for r in self.w.industrial_plan(self.s)['buildings'] if r['cell']==farm)
        self.assertEqual(row['outputs']['food'],3750) # automation +25%, with real inputs.
        self.assertEqual(row['assigned'],120)
    def test_workers_are_never_counted_twice_and_priority_controls_allocation(self):
        self.populate(500); a=self.build('industrial_farm'); b=self.build('industrial_farm'); c=self.build('industrial_farm')
        self.w.execute(self.s,act('factory_policy',cell=c,priority=100)); self.w.execute(self.s,act('factory_policy',cell=a,priority=1))
        plan=self.w.industrial_plan(self.s); self.assertLessEqual(plan['assigned_workers'],plan['workforce']); self.assertEqual(plan['workforce'],275)
        self.assertIn('labor',next(r for r in plan['buildings'] if r['cell']==a)['bottlenecks'])
    def test_missing_inputs_reduce_output_and_mothballing_stops_expenses(self):
        self.populate(500); farm=self.build('industrial_farm'); self.s.stocks['fertilizer']=0
        row=next(r for r in self.w.industrial_plan(self.s)['buildings'] if r['cell']==farm); self.assertEqual(row['utilization'],0); self.assertIn('fertilizer',row['bottlenecks'])
        self.w.execute(self.s,act('factory_policy',cell=farm,enabled=False)); row=next(r for r in self.w.industrial_plan(self.s)['buildings'] if r['cell']==farm)
        self.assertEqual(sum(row['inputs'].values()),0); self.assertEqual(row['assigned'],0)
    def test_forecast_shares_the_real_ledger_and_never_mutates_world(self):
        self.populate(500); self.build('industrial_farm'); before=self.w.data(); plan=self.w.industrial_plan(self.s); forecast=self.w.economic_forecast(self.s)
        self.assertEqual(before,self.w.data()); self.assertEqual(forecast['industry'],plan)
        self.w.income()
        for key,value in plan['end_stocks'].items():
            if key not in ('medicine','consumer_goods'): self.assertAlmostEqual(self.s.stocks[key],value,places=3)
    def test_electricity_is_not_infinite_storage(self):
        plan=self.w.industrial_plan(self.s); self.assertGreater(plan['electricity_spilled'],0); self.assertLessEqual(plan['end_stocks']['electricity'],1000)
    def test_mass_famine_kills_a_fraction_and_debt_crisis_is_real(self):
        self.populate(500); self.build('engineering_institute',level=3)
        self.s.stocks.update(food=0,resource=0,water=0,money=0,electricity=0); before=self.population(); self.w.income()
        self.assertGreater(self.population(),0); self.assertLess(self.population(),before); self.assertGreater(self.s.modern['unrest'],0)
        self.assertGreater(self.s.modern['debt'],0); self.assertTrue(any(e['kind']=='crisis' for e in self.w.events))
    def test_destroyed_housing_causes_overcrowding_and_can_be_evacuated(self):
        self.populate(500); city=next(p for p in self.own if self.w.cell(p).population==500); refuge=self.build('skyscraper')
        self.w.cell(city).building=None; before=self.population(); self.w.execute(self.s,act('edict',edict='evacuation'))
        self.assertEqual(self.population(),before); self.assertEqual(self.w.cell(city).population,20); self.assertEqual(self.w.cell(refuge).population,480)
    def test_modern_upgrade_uses_full_cost_and_obeys_industrial_limit(self):
        p=self.build('coal_mine'); money=self.s.stocks['money']; self.w.execute(self.s,act('improve_building',cell=p)); self.assertEqual(money-self.s.stocks['money'],BUILDINGS['coal_mine']['cost']['money']*2)
        self.w.execute(self.s,act('improve_building',cell=p)); self.assertRaises(RuleError,self.w.execute,self.s,act('improve_building',cell=p))
    def test_mass_migration_preserves_total_people_and_leaves_city_residents(self):
        self.populate(1000); self.grant(self.other); border=self.w.adjacent(self.own[0])[0]; self.w.cell(border).owner=self.other.id
        before=self.population()+self.population(self.other); mine=self.population(); theirs=self.population(self.other)
        self.w.execute(self.s,act('migrate',cell=self.lab,partner=self.other.id,amount=150))
        self.assertEqual(self.population(),mine-150); self.assertEqual(self.population(self.other),theirs+150); self.assertEqual(before,self.population()+self.population(self.other))
    def test_all_building_costs_are_valid_and_station_replaces_only_test_range(self):
        p=self.free()
        for key,info in BUILDINGS.items():
            with self.subTest(key=key):
                c=self.w.cell(p); c.population=0; c.building='radiation_test_range' if key=='radiation_station' else None; c.radiation=100 if key=='radiation_station' else 0; c.terrain=info.get('terrain',['grass'])[0]
                before=copy.deepcopy(self.s.stocks); self.w.execute(self.s,act('build',cell=p,building=key))
                for k,v in info['cost'].items(): self.assertAlmostEqual(before[k]-self.s.stocks[k],v)
                self.assertEqual(c.building,key)
    def test_fractional_industrial_damage_and_modern_barrier_can_really_be_repaired(self):
        p=self.build('coal_mine'); self.w.cell(p).integrity=79.6
        self.w.execute(self.s,act('repair_building',cell=p)); self.assertEqual(self.w.cell(p).integrity,100)
        q=self.build('concrete_wall'); self.w.cell(q).wall_hp=240; money=self.s.stocks['money']
        self.w.execute(self.s,act('repair_building',cell=q,amount=25)); self.assertEqual(self.w.wall_hitpoints(self.w.cell(q)),340); self.assertEqual(money-self.s.stocks['money'],750)


class MilitaryTests(EraFixture):
    def setUp(self): super().setUp(); self.grant(); self.populate(1000)
    def test_new_army_is_much_stronger_and_takes_equipment_and_civilian_crew(self):
        p=self.free(); before=self.population(); stocks=copy.deepcopy(self.s.stocks)
        self.w.execute(self.s,act('recruit_modern',cell=p,unit='tank_corps')); u=self.w.unit_at(p)
        self.assertEqual(self.w.effective_strength(u),320); self.assertEqual(before-self.population(),80)
        self.assertEqual(stocks['weapons_ii']-self.s.stocks['weapons_ii'],140); self.assertEqual(stocks['steel']-self.s.stocks['steel'],220)
    def test_no_free_modern_army_when_missing_weapon_or_crew(self):
        p=self.free(); self.s.stocks['weapons_iii']=0; before=self.w.data()
        self.assertRaises(RuleError,self.w.execute,self.s,act('recruit_modern',cell=p,unit='elite_corps')); self.assertEqual(self.w.data(),before)
    def test_modern_units_still_cannot_walk_on_water(self):
        p=self.free(); self.w.execute(self.s,act('recruit_modern',cell=p,unit='motorized')); u=self.w.unit_at(p); target=self.w.adjacent(p)[0]; self.w.cell(target).terrain='water'; money=self.s.stocks['money']
        self.assertRaises(RuleError,self.w.execute,self.s,act('move',unit_id=u['id'],target_cell=target)); self.assertEqual(money,self.s.stocks['money']); self.assertEqual(u['cell'],p)
    def test_fuel_crisis_reduces_strength_and_causes_attrition(self):
        p=self.free(); self.w.execute(self.s,act('recruit_modern',cell=p,unit='tank_corps')); u=self.w.unit_at(p); self.s.stocks['fuel']=0; self.w.income()
        self.assertEqual(u['supply_ratio'],0); self.assertLess(self.w.effective_strength(u),80); self.assertLess(u['strength'],320)
    def test_modern_army_can_siege_a_wall_but_scout_cannot(self):
        p=self.free(); self.w.execute(self.s,act('recruit_modern',cell=p,unit='motorized')); u=self.w.unit_at(p); target=self.w.adjacent(p)[0]; self.w.cell(target).owner=self.other.id; self.w.cell(target).building='wall'; self.w.cell(target).building_level=1
        self.w.units=[u]; self.w.step_unit(u,target); self.assertEqual(u['cell'],target); self.assertEqual(self.w.cell(target).owner,self.s.id)
    def test_bombardment_is_paid_once_per_day_and_does_not_capture(self):
        p=self.free(); self.w.execute(self.s,act('recruit_modern',cell=p,unit='artillery')); u=self.w.unit_at(p); target=self.w.adjacent(p)[0]; self.w.cell(target).owner=self.other.id; self.w.cell(target).population=100
        ammo=self.s.stocks['weapons_i']; self.w.execute(self.s,act('bombard',unit_id=u['id'],target_cell=target))
        self.assertEqual(self.s.stocks['weapons_i'],ammo-10); self.assertEqual(self.w.cell(target).owner,self.other.id); self.assertLess(self.w.cell(target).population,100)
        self.assertRaises(RuleError,self.w.execute,self.s,act('bombard',unit_id=u['id'],target_cell=target))
    def test_test_range_station_and_ballistics_require_own_irradiated_site(self):
        p=self.free(); self.assertRaises(RuleError,self.w.execute,self.s,act('build',cell=p,building='radiation_station'))
        self.build('radiation_test_range',p=p); self.assertEqual(self.w.cell(p).radiation,100); self.assertEqual(self.w.population_capacity(self.s,self.w.cell(p)),0)
        self.build('radiation_station',p=p); self.s.tech.remove('ballistics_i'); self.w.execute(self.s,act('research',cell=self.lab,tech='ballistics_i'))
        self.w.cell(p).owner=self.other.id; self.s.tech.remove('ballistics_ii'); self.assertRaises(RuleError,self.w.execute,self.s,act('research',cell=self.lab,tech='ballistics_ii'))
    def test_missile_shaft_needs_supplies_and_uses_real_stock(self):
        p=self.build('missile_silo'); target=self.w.adjacent(p)[0]; self.w.cell(target).owner=self.other.id; self.w.cell(target).population=100; before=self.s.stocks['missiles_i']
        self.assertRaises(RuleError,self.w.execute,self.s,act('missile_strike',cell=p,target_cell=target,missile='missiles_i'))
        self.s.modern['operating']={f'{p[0]}:{p[1]}':1}; self.w.execute(self.s,act('missile_strike',cell=p,target_cell=target,missile='missiles_i'))
        self.assertEqual(self.s.stocks['missiles_i'],before-1); self.assertLess(self.w.cell(target).population,100); self.assertEqual(self.w.cell(target).owner,self.other.id)
        self.assertRaises(RuleError,self.w.execute,self.s,act('missile_strike',cell=p,target_cell=target,missile='missiles_i'))
    def test_defenses_must_be_powered_and_radar_increases_interception(self):
        p=self.free(); self.w.cell(p).owner=self.other.id; self.w.cell(p).building='missile_defense_site'; self.w.cell(p).building_level=1; self.grant(self.other)
        self.assertEqual(self.w.interception(self.other.id,p),0); self.other.modern['operating']={f'{p[0]}:{p[1]}':1}
        self.assertEqual(self.w.interception(self.other.id,p),85)
        q=self.w.adjacent(p)[0]; self.w.cell(q).owner=self.other.id; self.w.cell(q).building='radar'; self.w.cell(q).building_level=1; self.other.modern['operating'][f'{q[0]}:{q[1]}']=1
        self.assertEqual(self.w.interception(self.other.id,p),95)
    def test_radioactive_site_requires_demolition_before_expensive_cleanup(self):
        p=self.build('radiation_test_range'); self.assertRaises(RuleError,self.w.execute,self.s,act('remediate',cell=p))
        self.w.execute(self.s,act('demolish',cell=p)); self.assertEqual(self.w.cell(p).radiation,100)
        self.w.execute(self.s,act('remediate',cell=p)); self.assertEqual(self.w.cell(p).radiation,75)
    def test_strategic_area_damage_can_harm_own_nearby_city(self):
        p=self.build('missile_silo'); target=self.w.adjacent(p)[0]; self.w.cell(target).owner=self.other.id
        city=next(q for q in self.w.adjacent(target) if q!=p); self.w.cell(city).owner=self.s.id; self.w.cell(city).population=100
        self.s.modern['operating']={f'{p[0]}:{p[1]}':1}
        with patch.object(self.w,'interception',return_value=0): self.w.execute(self.s,act('missile_strike',cell=p,target_cell=target,missile='missiles_iii'))
        self.assertLess(self.w.cell(city).population,100); self.assertEqual(self.w.cell(city).radiation,25); self.assertEqual(self.w.cell(target).owner,self.other.id)


class ContractTests(EraFixture):
    def setUp(self): super().setUp(); self.grant(); self.grant(self.other)
    def pact(self,**extra):
        self.w.execute(self.s,act('supply_pact',partner=self.other.id,resource='fuel',amount=100,price=10,duration=3,penalty=500,**extra)); p=self.w.supply_pacts[-1]
        self.w.execute(self.other,act('accept_supply',pact_id=p['id'],allow_risk=True,reason='Осознанный импорт для снабжения промышленности и армии.')); return p
    def test_signed_daily_pact_moves_existing_resources_and_money_once(self):
        p=self.pact(); before=self.s.stocks['fuel']+self.other.stocks['fuel']; money=self.s.stocks['money']+self.other.stocks['money']
        self.w.day+=1; self.w.process_supply(); self.w.process_supply()
        self.assertEqual(p['delivered'],100); self.assertEqual(p['paid'],1000); self.assertEqual(before,self.s.stocks['fuel']+self.other.stocks['fuel']); self.assertEqual(money,self.s.stocks['money']+self.other.stocks['money'])
    def test_seller_default_creates_real_claim_not_free_delivery_or_money(self):
        p=self.pact(); self.s.stocks.update(fuel=0,money=0); before=self.other.stocks['money']; self.w.day+=1; self.w.process_supply()
        self.assertEqual(p['delivered'],0); self.assertEqual(p['defaults'],1); self.assertEqual(self.other.stocks['money'],before); self.assertEqual(self.s.modern['claims'][0]['amount'],500)
    def test_buyer_default_and_early_exit_charge_the_responsible_party(self):
        p=self.pact(); self.other.stocks['money']=0; self.w.day+=1; self.w.process_supply(); self.assertEqual(self.other.modern['claims'][0]['creditor'],self.s.id)
        self.other.stocks['money']=1000; self.w.execute(self.other,act('cancel_supply',pact_id=p['id'])); self.assertEqual(self.other.stocks['money'],500); self.assertEqual(p['status'],'cancelled')
    def test_high_cost_contract_requires_explicit_risk_and_displays_total_commitment(self):
        self.w.execute(self.s,act('supply_pact',partner=self.other.id,resource='fuel',amount=100,price=10,duration=60,penalty=500)); p=self.w.supply_pacts[-1]
        self.assertRaises(RuleError,self.w.execute,self.other,act('accept_supply',pact_id=p['id']))
        self.assertEqual(self.w.supply_context(self.other)[0]['total_commitment'],60000)
    def test_new_resources_cannot_be_given_to_first_era(self):
        self.other.tech.remove('industrialization')
        self.assertRaises(RuleError,self.w.execute,self.s,act('transfer',cell=self.lab,partner=self.other.id,resource='weapons_i',amount=100))
        self.assertRaises(RuleError,self.w.execute,self.s,act('supply_pact',partner=self.other.id,resource='fuel',amount=100,price=10))
    def test_pact_private_reasons_never_reach_the_other_country(self):
        self.pact(reason='SELLER_PRIVATE_CANARY'); context=checked_context(self.other,self.w.context(self.other))
        self.assertNotIn('SELLER_PRIVATE_CANARY',json.dumps(context)); self.assertIn('SELLER_PRIVATE_CANARY',json.dumps(self.w.context(self.s)))
    def test_contract_expiry_stops_obligation(self):
        p=self.pact()
        for _ in range(4): self.w.day+=1; self.w.process_supply()
        self.assertEqual(p['delivered'],300); self.assertEqual(p['status'],'completed')
    def test_forecast_includes_signed_daily_payment_and_arriving_fuel_without_mutation(self):
        self.pact(); before=self.w.data(); forecast=self.w.economic_forecast(self.other)
        self.assertEqual(forecast['resources']['fuel']['signed_pact_net'],100); self.assertEqual(forecast['resources']['money']['signed_pact_net'],-1000)
        self.assertEqual(self.w.data(),before)
        expected=forecast['industry']['end_stocks']; opening=dict(self.other.stocks); self.w.start_day()
        self.assertAlmostEqual(self.other.stocks['fuel'],expected['fuel']); self.assertAlmostEqual(self.other.stocks['money'],expected['money'])
        self.assertAlmostEqual(self.w.daily_income[self.other.id]['money'],self.other.stocks['money']-opening['money'])
    def test_unsigned_offer_is_never_counted_as_guaranteed_income(self):
        self.w.execute(self.s,act('supply_pact',partner=self.other.id,resource='fuel',amount=100,price=10)); forecast=self.w.economic_forecast(self.s)
        self.assertEqual(forecast['resources']['money']['signed_pact_net'],0)
    def test_crisis_private_budget_is_not_broadcast_to_third_party(self):
        third=self.other; self.s.modern['debt']=123456789; self.s.stocks['water']=0; self.w.income()
        private=[e for e in self.w.events if e['kind']=='crisis' and self.s.name in e['text']]
        self.assertTrue(private); self.assertTrue(all(e['visible_to']==[self.s.id] for e in private))
        self.assertNotIn('123456789',json.dumps(self.w.context(third)))


class PersistenceTests(EraFixture):
    def test_modern_surrender_to_first_era_keeps_loot_but_does_not_unlock_it(self):
        self.grant(); self.populate(500); p=self.free(); self.w.execute(self.s,act('recruit_modern',cell=p,unit='motorized')); unit=self.w.unit_at(p)
        self.w.set_war(self.s.id,self.other.id,'Проверка капитуляции'); loot=self.s.stocks['weapons_i']; self.w.execute(self.s,act('surrender',partner=self.other.id))
        self.assertEqual(self.w.era_for(self.other),1); self.assertEqual(self.other.stocks['weapons_i'],loot); self.assertNotIn('weapons_i',self.w.context(self.other)['stocks'])
        self.assertEqual(unit['owner'],self.other.id); self.assertEqual(self.w.remaining_moves(unit),0); self.assertLess(self.w.effective_strength(unit),5)
        self.assertRaises(RuleError,self.w.execute,self.other,act('move',unit_id=unit['id'],target_cell=self.w.adjacent(unit['cell'])[0]))
    def test_defeat_closes_new_supply_obligations(self):
        self.grant(); self.grant(self.other); self.w.execute(self.s,act('supply_pact',partner=self.other.id,resource='fuel',amount=10,price=1))
        self.w.eliminate_state(self.s); self.assertEqual(self.w.supply_pacts[0]['status'],'closed_defeat')
    def test_all_modern_fields_roundtrip_and_forecast_cannot_modify_saved_state(self):
        self.grant(); self.populate(500); p=self.build('radiation_test_range'); self.s.modern.update(debt=1000,unrest=20)
        before=self.w.data()
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3',export=True); store.save(self.w); loaded=store.load()
            self.assertEqual(loaded.data(),before); loaded.context(loaded.states[0]); self.assertEqual(loaded.data(),before)
            self.assertEqual(json.loads((Path(temp)/'world.json').read_text(encoding='utf-8')),before)
    def test_old_snapshot_gains_only_defaults_and_keeps_pending_characters(self):
        data=self.w.data(); data['version']=5; data['patch']='5.3'; data.pop('supply_pacts'); data.pop('next_supply')
        for state in data['states']: state.pop('era'); state.pop('modern')
        for cell in data['cells']:
            for key in ('radiation','integrity','factory_enabled','factory_priority','last_fired_day'): cell.pop(key)
        data['pending_decisions']={self.s.id:dict(notes='Личная память',thinking='Уже готовый ход',actions=[])}
        loaded=World.restore(data); self.assertEqual(loaded.pending_decisions,data['pending_decisions']); self.assertEqual(loaded.states[0].stocks,data['states'][0]['stocks']); self.assertEqual(loaded.data()['version'],6)
    def test_catalog_is_large_reachable_and_all_references_are_valid(self):
        self.assertEqual(len(MODERN_RESOURCES),25); self.assertEqual(len(BUILDINGS),45); self.assertEqual(len(UNITS),8)
        for key,info in BUILDINGS.items():
            self.assertIn(info['tech'],TECHNOLOGIES)
            self.assertTrue(set(info['cost'])|set(info['inputs'])|set(info['outputs'])<=set(RESOURCE_NAMES))
        known={'universities','engineering','steelworks','banking','aether_forging'}
        for _ in range(len(TECHNOLOGIES)):
            known.update(k for k,v in TECHNOLOGIES.items() if set(v['requires'])<=known)
        self.assertTrue(set(TECHNOLOGIES)<=known)
        # Material and research bootstrap: no new resource requires only itself in a closed cycle.
        resources=set(self.s.stocks); technologies=set(TECHNOLOGIES['industrialization']['requires'])
        for _ in range(100):
            technologies.update(k for k,t in TECHNOLOGIES.items() if set(t['requires'])<=technologies and set(t['cost'])<=resources)
            for b in BUILDINGS.values():
                if b['tech'] in technologies and set(b['cost'])|set(b['inputs'])<=resources: resources.update(b['outputs'])
        self.assertTrue(set(MODERN_RESOURCES)<=resources)
    def test_increasing_context_after_a_previous_limit_really_attempts_larger_load(self):
        try: from .test_v53 import MockServer
        except ImportError: from test_v53 import MockServer
        brain=Brain(dict(model='model',strict_state_isolation=True,context_window=98304)); server=MockServer(); brain.request=server.request; brain.bind_actor(self.s.id)
        brain.prepare_model('model'); brain.load_limits['model']=65536; brain.config['context_window']=196608; _,actual=brain.prepare_model('model')
        self.assertEqual(actual,131072); self.assertEqual(server.counter,2) # Mock model supports at most 131072.


class ExpandedWindowTests(EraFixture):
    def test_every_expanded_tab_and_construction_panel_render_without_changing_world(self):
        import os
        os.environ.setdefault('SDL_VIDEODRIVER','dummy'); os.environ.setdefault('SDL_AUDIODRIVER','dummy')
        from planet.industry_window import IndustryView
        from main import App
        import pygame as pg
        self.grant(); self.populate(500); self.build('industrial_farm'); before=self.w.data()
        view=IndustryView(self.w,self.s.id)
        for tab in range(5): view.tab=tab; view.draw()
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'view.sqlite3'); store.save(self.w); app=App(self.w,store,dict(external_console=False)); app.tab=9; app.draw()
            with patch('main.subprocess.Popen') as spawn:
                app.action('industry'); self.assertEqual(spawn.call_count,1); self.assertIn('planet.industry_window',spawn.call_args.args[0])
        self.assertEqual(self.w.data(),before); pg.quit()


if __name__=='__main__': unittest.main()
