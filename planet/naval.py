"""Paid batch recruitment, ship capacity and executable coastal operations."""
import copy
from .rules import RuleError

class Naval:
    def ship_capacity(self,ship):return min(3,1+int(ship.get('max_strength',ship['strength']))//4)

    def shipyards(self,state):
        return sorted({tuple(q) for p in self.positions(state.id) if self.cell(p).terrain!='water' for q in self.adjacent(p)
            if self.cell(q).terrain=='water' and self.cell(q).owner in (None,state.id) and not self.unit_at(q)})

    def recruit_group(self,state,kind,args):
        count=args.get('count')
        if type(count) is not int or count<1:raise RuleError('count должен быть положительным целым числом')
        first=args.get('cell');self.cell(first)
        ship=kind=='unit' and args.get('unit',args.get('type'))=='ship'
        sites=[list(p) for p in (self.shipyards(state) if ship else self.recruitment_sites(state))]
        if first not in sites:raise RuleError('Начальная клетка найма должна быть своей свободной сушей или доступной верфью')
        sites.remove(first);sites.sort(key=lambda p:abs(p[0]-first[0])+abs(p[1]-first[1]));sites.insert(0,first)
        if count>len(sites):raise RuleError('Для всего найма не хватает свободных подходящих клеток')
        orders=[]
        for p in sites[:count]:
            one=copy.deepcopy(args);one.pop('count',None);one['cell']=p;orders.append(dict(type=kind,args=one))
        from .engine import World
        sandbox=World.restore(self.data());actor=sandbox.state(state.id)
        for order in orders:sandbox.execute(actor,order)
        for order in orders:self.execute(state,order)
        return f'Нанято {count} формирований ({args.get("unit",args.get("type"))}); все клетки, ресурсы и экипажи оплачены'

    def naval_context(self,state):
        ships=[u for u in self.units if u['owner']==state.id and u['type']=='ship']
        landing=[];boarding=[]
        for ship in ships:
            passengers=[u for u in self.units if u.get('embarked_on')==ship['id']]
            if len(passengers)<self.ship_capacity(ship):
                for u in self.units:
                    if u['owner']==state.id and u['type']!='ship' and not u.get('embarked_on') and u['cell'] in self.adjacent(ship['cell']):
                        boarding.append(dict(unit_id=u['id'],ship_id=ship['id']))
            for passenger in passengers:
                for p in self.adjacent(ship['cell']):
                    cell=self.cell(p);other=self.unit_at(p)
                    if cell.terrain=='water' or cell.radiation:continue
                    hostile=cell.owner not in (None,state.id) or other and other['owner']!=state.id
                    peer=other['owner'] if other and other['owner']!=state.id else cell.owner
                    if hostile and (not self.combat_unit(passenger) or not self.at_war(state.id,peer)):continue
                    if other and other['owner']==state.id:continue
                    landing.append(dict(unit_id=passenger['id'],target_cell=list(p),assault=bool(hostile),wall_hp=self.wall_hitpoints(cell),minimum_money=22 if hostile else 0))
        return dict(navigation='navigation' in state.tech,shipyards=[list(p) for p in self.shipyards(state)][:24],
                    ships=[dict(id=u['id'],cell=list(u['cell']),capacity=self.ship_capacity(u),order=copy.deepcopy(u.get('order')),passengers=[p['id'] for p in self.units if p.get('embarked_on')==u['id']]) for u in ships],
                    embark_options=boarding[:24],landing_options=landing[:24],
                    rule='unit(unit=ship) строит корабль на прибрежной воде после navigation; embark → морской move → disembark. Высадка армии на вражеский берег требует войны и оплаченного боя/осады. Только корабли ходят по воде. count нанимает группу без лимита двух, но нужны ресурсы и отдельные клетки.')
