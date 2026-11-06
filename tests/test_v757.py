import unittest
from planet.engine import World
from planet.execution_ai import preview_orders
from planet.modern_catalog import MODERN_RESOURCES

class PriorityRecovery(unittest.TestCase):
    def setUp(self):
        self.world=World(size=32,count=2)
        self.state=self.world.states[0]
        self.state.tech.extend(('industrialization','urban_planning'))
        for resource in MODERN_RESOURCES:
            self.state.stocks[resource]=0
        self.state.stocks.update(money=2500,food=4000,resource=500)
        self.positions=self.world.positions(self.state.id)
        for p in self.positions:
            self.world.cell(p).population=0

    def apply(self,actions):
        self.world.apply_decision(self.state,dict(thinking='Тест',notes=self.state.notes,plan=self.state.plan,actions=actions))
        return self.state.decision_outcome['action_results']

    def population(self):
        return sum(self.world.cell(p).population for p in self.positions)

    def test_queued_construction_cannot_spend_recovery_budget_first(self):
        p=next(p for p in self.positions if self.world.cell(p).building is None)
        action=dict(type='build',args=dict(cell=p,building='tower'))
        preview=preview_orders(self.world,self.state.id,dict(actions=[action]))
        self.assertEqual(self.population(),0)
        rows=self.apply([action])
        self.assertEqual([(r['type'],r['success']) for r in rows],[('edict',True),('build',False)])
        self.assertEqual(rows[0]['source'],'population_recovery')
        self.assertEqual(preview['stocks_after'],self.state.stocks)
        self.assertEqual(self.population(),100)
        self.assertEqual(self.state.stocks['money'],0)

    def test_invalid_order_gets_paid_fallback_even_with_small_budget(self):
        self.state.stocks.update(money=150,food=90,resource=30)
        rows=self.apply([dict(type='settle',args=dict(cell=[-1,0],amount=3))])
        self.assertEqual([r['success'] for r in rows],[False,True])
        self.assertEqual(self.population(),3)
        self.assertEqual(self.state.stocks['money'],0)

    def test_valid_player_order_moves_first_and_does_not_trigger_fallback(self):
        rows=self.apply([dict(type='do_nothing',args={}),dict(type='settle',args=dict(cell=self.positions[0],amount=2))])
        self.assertEqual([r['type'] for r in rows],['settle','do_nothing'])
        self.assertEqual(self.population(),2)
        self.assertEqual(self.state.stocks['money'],2400)

    def test_empty_decision_recovers_once_and_no_free_people_without_funds(self):
        self.state.stocks['money']=49
        self.assertEqual(self.apply([]),[])
        self.assertEqual(self.population(),0)
        self.state.stocks['money']=2500
        self.assertTrue(self.apply([])[0]['success'])
        self.assertEqual(self.apply([]),[])
        self.assertEqual(self.population(),100)

    def test_water_and_radiation_cannot_receive_recovery(self):
        for i,p in enumerate(self.positions):
            cell=self.world.cell(p)
            if i%2:cell.terrain='water'
            else:cell.radiation=100
        self.assertEqual(self.apply([]),[])
        self.assertEqual(self.state.stocks['money'],2500)
        self.assertEqual(self.population(),0)
