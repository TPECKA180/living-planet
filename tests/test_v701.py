import copy,unittest
from planet.engine import World,RuleError

class BorderTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=24,count=2);self.a,self.b=self.w.states;self.w.day=1
        self.w.units=[]
        for c in self.w.cells:c.terrain='water';c.owner=None;c.building=None;c.wall_hp=None;c.population=0
        for x in range(1,7):
            c=self.w.cell([x,2]);c.terrain='grass';c.owner=self.a.id if x==1 else self.b.id if x<6 else None
        self.a.stocks.update(money=1000,metal=1000);self.w.spawn(self.a.id,[1,2],'scout',5);self.u=self.w.units[-1]
    def move(self,target):self.w.execute(self.a,dict(type='move',args=dict(unit_id=self.u['id'],target_cell=target)))
    def test_crosses_multiple_foreign_cells_and_charges_real_steps(self):
        self.assertEqual(self.w.find_route(self.u,[6,2]),[[x,2] for x in range(2,7)])
        self.move([6,2]);self.assertEqual(self.u['cell'],[5,2]);self.assertEqual(self.a.stocks['money'],912)
        self.assertTrue(self.w.at_war(self.a.id,self.b.id))
        facts=self.w.relation(self.b.id,self.a.id)['facts']
        self.assertEqual(sum(f['kind']=='border_violation' for f in facts),1)
        self.w.day+=1;self.w.advance_order(self.u);self.assertEqual(self.u['cell'],[6,2])
    def test_auto_exploration_does_not_invade(self):self.assertIsNone(self.w.find_route(self.u,explore=True))
    def test_allied_and_vassal_borders_still_blocked_without_charge(self):
        self.a.allies.append(self.b.id);before=self.a.stocks.copy()
        with self.assertRaises(RuleError):self.move([6,2])
        self.assertEqual(self.a.stocks,before)
        self.a.allies=[];self.a.vassal_of=self.b.id
        self.assertIsNone(self.w.find_route(self.u,[6,2]))
    def test_water_rejection_keeps_money_and_relationships(self):
        self.w.cell([3,2]).terrain='water';before=copy.deepcopy(self.w.data())
        with self.assertRaises(RuleError):self.move([6,2])
        self.assertEqual(self.a.stocks,before['states'][0]['stocks']);self.assertFalse(self.w.wars)
    def test_wall_and_enemy_defender_cannot_be_skipped(self):
        c=self.w.cell([3,2]);c.building='wall';c.building_level=1;c.wall_hp=20
        self.assertIsNone(self.w.find_route(self.u,[6,2]))
        self.u['type']='army';self.w.spawn(self.b.id,[3,2],'army',10)
        self.assertIsNotNone(self.w.find_route(self.u,[6,2]));self.move([6,2])
        self.assertNotEqual(self.u['cell'],[6,2]);self.assertEqual(c.owner,self.b.id)
    def test_border_penalty_survives_save_restore(self):
        self.move([6,2]);restored=World.restore(self.w.data())
        self.assertEqual(restored.relation(self.b.id,self.a.id)['last_border_violation_day'],1)

