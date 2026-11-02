import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing

from planet.engine import World,Store,RuleError
from planet.mobility import SPEED,STEP_COST,UNIT_COST,METAL_PER_STRENGTH
from planet.saves import WorldLibrary


def action(kind,**args): return dict(type=kind,args=args)


def idle_decision(state):
    return dict(thinking=state.thinking,notes=state.notes,plan=state.plan,
                diplomacy=[dict(to='all',text='Продолжаем переговоры')],actions=[action('do_nothing')])


class MovementTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2)
        for cell in self.w.cells: cell.terrain='grass'
        self.w.start_day(); self.s=self.w.states[0]; self.u=self.w.units[0]
        for state in self.w.states: state.operations.update(explore=False,recruit=False)

    def test_distant_order_walks_adjacent_steps_and_persists_after_save(self):
        before=list(self.u['cell']); money=self.s.stocks['money']
        self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=[0,0]))
        self.assertEqual(len(self.w.movement_log),4)
        self.assertEqual(self.s.stocks['money'],money-STEP_COST*4)
        self.assertNotEqual(self.u['cell'],[0,0]); self.assertEqual(self.u['order']['target'],[0,0])
        for record in self.w.movement_log:
            self.assertEqual(sum(abs(a-b) for a,b in zip(record['source'],record['target'])),1)
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.db'); store.save(self.w); loaded=store.load()
            self.assertEqual(loaded.units[0]['order'],self.u['order'])
            previous=list(loaded.units[0]['cell']); loaded.in_day=False; loaded.start_day(); loaded.run_operations()
            self.assertNotEqual(loaded.units[0]['cell'],previous)
            self.assertEqual(loaded.units[0]['moves_used'],4)

    def test_multiple_orders_cannot_exceed_daily_speed(self):
        self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=[0,0]))
        cell=list(self.u['cell']); money=self.s.stocks['money']
        self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=[0,1]))
        self.w.run_operations()
        self.assertEqual(self.u['cell'],cell); self.assertEqual(self.s.stocks['money'],money)
        self.assertEqual(self.u['moves_used'],4)

    def test_old_distant_army_order_is_interpreted_as_route(self):
        source=list(self.u['cell']); target=[source[0]-3,source[1]-2]
        self.w.execute(self.s,action('army',cell=[0,0],unit_id=self.u['id'],target_cell=target))
        self.assertGreater(len(self.w.movement_log),0)
        self.assertLessEqual(len(self.w.movement_log),4)
        self.assertNotEqual(self.u['cell'],target)

    def test_exploration_captures_without_repeated_model_orders(self):
        count=len(self.w.positions(self.s.id))
        self.w.execute(self.s,action('explore',unit_id=self.u['id']))
        self.assertGreater(len(self.w.positions(self.s.id)),count)
        self.w.in_day=False; self.w.start_day(); self.w.run_operations()
        self.assertGreater(len(self.w.positions(self.s.id)),count+1)
        self.assertEqual(self.u['order']['kind'],'explore')

    def test_hold_overrides_default_exploration(self):
        self.s.operations['explore']=True
        before=list(self.u['cell'])
        self.w.execute(self.s,action('hold',unit_id=self.u['id'])); self.w.run_operations()
        self.assertEqual(self.u['cell'],before)

    def test_unreachable_water_target_does_not_spend_or_change_order(self):
        target=[0,0]; self.w.cell(target).terrain='water'; before=copy.deepcopy(self.u); money=self.s.stocks['money']
        with self.assertRaises(RuleError): self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=target))
        for key in ('cell','order','strength','moves_used'): self.assertEqual(self.u[key],before[key])
        self.assertEqual(self.s.stocks['money'],money)

    def test_pathfinder_routes_around_water_and_friendly_units(self):
        x,y=self.u['cell']; water=[x-1,y]; self.w.cell(water).terrain='water'
        self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=[x-2,y]))
        self.assertNotIn(water,[m['target'] for m in self.w.movement_log])
        self.assertEqual(self.u['cell'],[x-2,y])

    def test_bankrupt_units_cannot_move_for_free(self):
        self.s.stocks['money']=0; before=list(self.u['cell'])
        self.w.execute(self.s,action('explore',unit_id=self.u['id']))
        self.assertEqual(self.u['cell'],before); self.assertEqual(self.w.movement_log,[])
        self.assertGreater(len(self.u['blocked_reason']),0)

    def test_builder_has_own_movement_budget(self):
        unit=self.w.units[1]
        self.w.execute(self.s,action('move',unit_id=unit['id'],target_cell=[0,0]))
        self.assertEqual(unit['moves_used'],SPEED['builder'])

    def test_context_has_real_movement_and_recruitment_options(self):
        context=self.w.context(self.s)
        self.assertEqual(context['rules']['step_cost'],2)
        self.assertEqual(context['rules']['action_prices']['unit'],60)
        self.assertTrue(context['recruitment_sites'])
        for option in context['mobility']:
            route=option['path_to_neutral']; current=option['cell']
            self.assertTrue(route)
            for point in route:
                self.assertIn(point,self.w.adjacent(current)); current=point
            self.assertIsNone(self.w.cell(route[-1]).owner)


class DevelopmentTests(unittest.TestCase):
    def test_two_days_really_grow_territory_and_create_paid_units(self):
        world=World(); initial_units=len(world.units)
        for _ in range(2):
            world.start_day()
            money={s.id:s.stocks['money'] for s in world.states}
            for state in world.states: world.pending_decisions[state.id]=idle_decision(state)
            world.resolve_round()
            for state in world.states:
                stats=world.day_stats[state.id]
                self.assertGreater(stats['steps'],0)
                self.assertGreater(stats['territory_delta'],0)
                self.assertTrue(any('Юнит #' in h['text'] for h in state.history))
                expected=money[state.id]-stats.get('movement_cost',0)-stats.get('recruited',0)*UNIT_COST
                self.assertEqual(state.stocks['money'],expected)
                self.assertTrue(all(value>=0 for value in state.stocks.values()))
            world.phase='idle'; world.in_day=False
        self.assertGreater(len(world.units),initial_units)
        self.assertTrue(all(len(world.positions(s.id))>25 for s in world.states))

    def test_operations_are_not_run_twice_in_same_day(self):
        world=World(); world.start_day(); world.run_operations(); snapshot=world.data()
        world.run_operations(); self.assertEqual(world.data(),snapshot)

    def test_model_can_disable_routines(self):
        world=World(); world.start_day(); state=world.states[0]
        p=world.positions(state.id)[0]
        world.execute(state,action('policy',cell=p,explore=False,recruit=False))
        before=[copy.deepcopy(u) for u in world.units if u['owner']==state.id]
        world.run_operations()
        self.assertEqual(before,[u for u in world.units if u['owner']==state.id])
        self.assertEqual(len(world.positions(state.id)),25)

    def test_manual_recruitment_consumes_new_prices(self):
        world=World(); state=world.states[0]; p=world.recruitment_sites(state)[0]
        gold,metal=state.stocks['money'],state.stocks['metal']
        world.execute(state,action('unit',cell=p,type='army',strength=3))
        self.assertEqual(state.stocks['money'],gold-UNIT_COST)
        self.assertEqual(state.stocks['metal'],metal-3*METAL_PER_STRENGTH)

    def test_more_population_and_land_give_money_income(self):
        world=World(); state=world.states[0]; before=state.stocks['money']
        world.income()
        self.assertEqual(state.stocks['money']-before,25*4+3+10)


class CompatibilityTests(unittest.TestCase):
    def legacy(self):
        world=World(); world.start_day(); world.day=3; world.cursor=1
        world.pending_decisions['state_1']=idle_decision(world.states[0])
        world.states[0].notes='Особый характер — ни одного слова не терять.'
        data=world.data(); data['version']=2
        for key in ('rules_version','movement_log','day_stats','last_day_stats','operations_day'): data.pop(key)
        for state in data['states']: state.pop('operations')
        for unit in data['units']:
            for key in ('born_day','order','moves_day','moves_used','command_day','blocked_reason'): unit.pop(key)
        return data

    def write(self,path,data):
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE snapshot(id INTEGER PRIMARY KEY,data TEXT)')
            db.execute('INSERT INTO snapshot VALUES(1,?)',(json.dumps(data,ensure_ascii=False),))

    def test_old_day_three_keeps_two_completed_days_character_and_pending_reply(self):
        data=self.legacy(); before=copy.deepcopy(data); world=World.restore(data)
        self.assertEqual(data,before)
        self.assertEqual(world.day,3); self.assertEqual(world.cursor,1); self.assertTrue(world.in_day)
        self.assertEqual(world.pending_decisions,data['pending_decisions'])
        self.assertEqual(world.data()['cells'],data['cells'])
        for old,state in zip(data['states'],world.states):
            for key in ('notes','plan','thinking','memory','history','stocks'): self.assertEqual(getattr(state,key),old[key])
        self.assertEqual(world.rules_version,6)

    def test_first_write_of_old_save_creates_loadable_pre_upgrade_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'world.sqlite3'; original=self.legacy(); self.write(path,original)
            store=Store(path); world=store.load(); store.save(world)
            backups=list((path.parent/'backups').glob('*.sqlite3')); self.assertEqual(len(backups),1)
            with closing(sqlite3.connect(backups[0])) as db: saved=json.loads(db.execute('select data from snapshot').fetchone()[0])
            self.assertEqual(saved,original)
            with closing(sqlite3.connect(path)) as db: self.assertEqual(json.loads(db.execute('select data from snapshot').fetchone()[0])['version'],6)
            store.save(world); self.assertEqual(len(list((path.parent/'backups').glob('*.sqlite3'))),1)

    def test_import_preserves_original_and_creates_complete_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'old.sqlite3'; data=self.legacy(); self.write(path,data); raw=path.read_bytes()
            world,store=WorldLibrary(Path(temp)/'worlds').import_legacy(path,'Продолжение')
            self.assertEqual(raw,path.read_bytes()); self.assertEqual(world.pending_decisions,data['pending_decisions'])
            self.assertTrue((store.path.parent/'migration.json').exists())
            self.assertEqual(len(list((store.path.parent/'backups').glob('*.sqlite3'))),1)
            for name in ('movement.jsonl','day_stats.json','states/state_1/state.json'): self.assertTrue((store.path.parent/name).exists())


if __name__=='__main__': unittest.main()
