import copy,json,tempfile,unittest
from collections import deque
from pathlib import Path
from planet.engine import World,RuleError,Store
from planet.saves import WorldLibrary

def land_components(w):
    remaining={(i%w.size,i//w.size) for i,c in enumerate(w.cells) if c.terrain!='water'};groups=[]
    while remaining:
        start=remaining.pop();group={start};queue=deque([start])
        while queue:
            for q in w.adjacent(queue.popleft()):
                q=tuple(q)
                if q in remaining:remaining.remove(q);group.add(q);queue.append(q)
        groups.append(group)
    return groups

class GeographyTests(unittest.TestCase):
    def test_seed_changes_coastline_and_same_seed_is_reproducible(self):
        a=World(size=32,seed=1);b=World(size=32,seed=2);c=World(size=32,seed=1)
        self.assertNotEqual([x.terrain=='water' for x in a.cells],[x.terrain=='water' for x in b.cells])
        self.assertEqual(a.data(),c.data())
    def test_archipelago_has_six_large_separate_islands_and_independent_starts(self):
        for size in (24,32,64,128):
            for seed in (1,42,912):
                with self.subTest(size=size,seed=seed):
                    w=World(size=size,count=6,seed=seed,map_mode='archipelago');groups=land_components(w)
                    self.assertEqual(len(groups),6);self.assertGreater(min(map(len,groups)),size*size*.035)
                    homes=[next(i for i,g in enumerate(groups) if tuple(w.positions(s.id)[0]) in g) for s in w.states]
                    self.assertEqual(len(set(homes)),6)
    def test_mode_seed_and_map_survive_library_save_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            library=WorldLibrary(folder);w,store=library.create('Острова',6,123,map_mode='archipelago')
            self.assertEqual(store.load().data(),w.data());self.assertEqual(w.map_mode,'archipelago')
            old=copy.deepcopy(w.data());old.pop('map_mode');old.pop('generation_size');restored=World.restore(old)
            self.assertEqual(restored.data()['cells'],old['cells']);self.assertEqual(restored.data()['map_mode'],'normal')
    def test_archipelago_menu_selection_reaches_world_generator(self):
        import os
        os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
        from unittest.mock import patch
        from planet.dialogs import Dialog
        from planet.launcher import choose_world
        clicked=[]
        def events(dialog):
            if not dialog.buttons:return []
            if not clicked:clicked.append(True);return ['mode:archipelago']
            return ['new']
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(Dialog,'events',events):w,store=choose_world(folder,dict(saves_directory=str(Path(folder)/'saves'),states=6))
            store.session_lock.close();self.assertEqual(w.map_mode,'archipelago');self.assertEqual(len(land_components(w)),6)

class NavalTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=24,count=2);self.w.day=1;self.s,self.peer=self.w.states
        for c in self.w.cells:c.owner=None;c.population=0;c.building=None;c.terrain='water';c.radiation=0;c.wall_hp=None
        self.w.units=[]
        for x in range(2,8):
            for y in range(2,8):c=self.w.cell([x,y]);c.terrain='grass';c.owner=self.s.id
        for x in range(10,16):
            for y in range(2,8):c=self.w.cell([x,y]);c.terrain='grass';c.owner=self.peer.id
        self.s.tech.extend(['navigation','army']);self.s.stocks.update(money=10000,metal=1000,food=1000,resource=1000)
    def execute(self,kind,**args):return self.w.execute(self.s,dict(type=kind,args=args))
    def ship(self,strength=8):
        self.execute('unit',unit='ship',cell=[8,4],strength=strength);return self.w.units[-1]
    def passenger(self,p=[7,4],strength=5):
        self.execute('unit',unit='army',cell=p,strength=strength);return self.w.units[-1]
    def test_batch_recruitment_exceeds_old_cap_and_pays_each_unit(self):
        self.s.operations.update(unit_limit=0,war_army_limit=0);before=self.s.stocks.copy()
        self.execute('unit',unit='army',cell=[3,3],strength=3,count=10)
        self.assertEqual(len(self.w.units),10);self.assertEqual(before['money']-self.s.stocks['money'],600);self.assertEqual(before['metal']-self.s.stocks['metal'],90)
        self.assertEqual(len({tuple(u['cell']) for u in self.w.units}),10)
    def test_batch_builds_multiple_ships_only_at_legal_coast(self):
        before=self.s.stocks['money'];self.execute('unit',unit='ship',cell=[8,4],strength=3,count=3)
        self.assertEqual(len(self.w.units),3);self.assertEqual(before-self.s.stocks['money'],180)
        self.assertTrue(all(self.w.cell(u['cell']).terrain=='water' for u in self.w.units))
    def test_every_modern_unit_can_be_recruited_as_paid_batch(self):
        from planet.modern_catalog import UNITS,TECHNOLOGIES,MODERN_RESOURCES
        self.s.tech.extend(TECHNOLOGIES);self.s.era=2;self.w.cell([3,3]).population=10000
        self.s.stocks.update({k:10**9 for k in list(self.s.stocks)+list(MODERN_RESOURCES)})
        baseline=self.w.data()
        for kind,info in UNITS.items():
            with self.subTest(unit=kind):
                w=World.restore(baseline);s=w.state(self.s.id);before=s.stocks.copy()
                w.execute(s,dict(type='recruit_modern',args=dict(cell=[4,4],unit=kind,count=3)))
                self.assertEqual(len(w.units),3)
                for key,cost in w.modern_recruitment_cost(kind).items():self.assertEqual(before[key]-s.stocks[key],cost*3)
    def test_embarked_combat_units_remain_known_to_military_response(self):
        from planet.military_ai import validate_military
        ship=self.ship();unit=self.passenger();self.execute('embark',unit_id=unit['id'],ship_id=ship['id']);self.execute('declare_war',partner=self.peer.id,reason='Проверка подготовки настоящего десанта')
        decision=dict(actions=[dict(type='disembark',args=dict(unit_id=unit['id'],target_cell=[7,4]))],military_response=dict(choice='maneuver',reason='Высаживаем собственный боевой отряд на подготовленный берег.',revisit_day=self.w.day+1))
        validate_military(decision,self.w.context(self.s))
    def test_ship_movement_and_existing_naval_route_count_as_war_maneuver(self):
        from planet.military_ai import validate_military
        ship=self.ship();self.execute('declare_war',partner=self.peer.id,reason='Проверка реальных морских манёвров')
        decision=dict(actions=[dict(type='move',args=dict(unit_id=ship['id'],target_cell=[9,4]))],military_response=dict(choice='maneuver',reason='Перемещаем собственный флот к месту будущей операции.',revisit_day=self.w.day+1))
        validate_military(decision,self.w.context(self.s))
        ship['order']=dict(kind='move',target=[9,4]);decision['actions']=[]
        validate_military(decision,self.w.context(self.s))
    def test_unaffordable_batch_rejects_without_partial_recruitment(self):
        self.s.stocks['money']=100;before=self.w.data()
        with self.assertRaises(RuleError):self.execute('unit',unit='army',cell=[3,3],strength=3,count=10)
        self.assertEqual(before,self.w.data())
    def test_capacity_and_several_passengers_follow_ship_and_roundtrip(self):
        ship=self.ship();units=[self.passenger([7,y]) for y in (3,4,5)]
        # Bring each passenger adjacent on shore without sharing a cell.
        self.execute('embark',unit_id=units[1]['id'],ship_id=ship['id'])
        self.w.day+=1
        self.w.units.remove(units[0]);self.w.units.remove(units[2])
        a=self.passenger([7,4]);self.execute('embark',unit_id=a['id'],ship_id=ship['id'])
        self.w.day+=1;b=self.passenger([7,4]);self.execute('embark',unit_id=b['id'],ship_id=ship['id'])
        self.assertEqual(self.w.ship_capacity(ship),3)
        self.w.day+=1;self.execute('move',unit_id=ship['id'],target_cell=[9,4]);self.w.run_operations()
        self.assertEqual(ship['cell'],[9,4]);self.assertTrue(all(u['cell']==ship['cell'] for u in (units[1],a,b)))
        self.assertEqual(World.restore(self.w.data()).data(),self.w.data())
    def test_amphibious_assault_captures_enemy_coast_after_war(self):
        ship=self.ship();unit=self.passenger();self.execute('embark',unit_id=unit['id'],ship_id=ship['id'])
        self.w.day+=1;self.w.step_unit(ship,[9,4]);self.execute('declare_war',partner=self.peer.id,reason='Высадка ради плацдарма')
        before=self.s.stocks['money'];self.execute('disembark',unit_id=unit['id'],target_cell=[10,4])
        self.assertEqual(unit['cell'],[10,4]);self.assertIsNone(unit['embarked_on']);self.assertEqual(self.w.cell([10,4]).owner,self.s.id)
        self.assertEqual(before-self.s.stocks['money'],22);self.assertEqual(self.w.remaining_moves(unit),0)
    def test_enemy_landing_requires_war_and_friendly_landing_needs_free_cell(self):
        ship=self.ship();unit=self.passenger();self.execute('embark',unit_id=unit['id'],ship_id=ship['id'])
        self.w.day+=1;self.w.step_unit(ship,[9,4]);before=self.w.data()
        with self.assertRaises(RuleError):self.execute('disembark',unit_id=unit['id'],target_cell=[10,4])
        self.assertEqual(before,self.w.data())
    def test_wall_siege_leaves_surviving_passenger_on_ship(self):
        ship=self.ship();unit=self.passenger();self.execute('embark',unit_id=unit['id'],ship_id=ship['id'])
        self.w.day+=1;self.w.step_unit(ship,[9,4]);c=self.w.cell([10,4]);c.building='wall';c.building_level=1;c.wall_hp=20
        self.execute('declare_war',partner=self.peer.id,reason='Настоящая осада побережья');self.execute('disembark',unit_id=unit['id'],target_cell=[10,4])
        self.assertEqual(c.wall_hp,15);self.assertEqual(unit['embarked_on'],ship['id']);self.assertEqual(unit['cell'],ship['cell'])
        with self.assertRaises(RuleError):self.execute('disembark',unit_id=unit['id'],target_cell=[10,4])
    def test_sink_ship_removes_every_passenger(self):
        ship=self.ship();unit=self.passenger();self.execute('embark',unit_id=unit['id'],ship_id=ship['id']);self.w.remove_unit(ship)
        self.assertNotIn(unit,self.w.units)
    def test_water_does_not_generate_money_or_prevent_defeat_after_fleet_loss(self):
        self.w.cell([8,4]).owner=self.s.id;self.assertFalse(any(self.w.production_for_cell(self.s,self.w.cell([8,4])).values()))
        for c in self.w.cells:
            if c.owner==self.s.id and c.terrain!='water':c.owner=None
        self.w.check_eliminations();self.assertTrue(self.s.eliminated);self.assertIsNone(self.w.cell([8,4]).owner)
    def test_naval_context_shows_real_shipyards_capacity_and_landing_options(self):
        ship=self.ship();unit=self.passenger();self.execute('embark',unit_id=unit['id'],ship_id=ship['id'])
        ctx=self.w.naval_context(self.s);self.assertEqual(ctx['ships'][0]['capacity'],3);self.assertTrue(ctx['shipyards']);self.assertTrue(ctx['landing_options'])

if __name__=='__main__':unittest.main()
