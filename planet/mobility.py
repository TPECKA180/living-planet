"""Movement orders, ordinary pathfinding and paid routine exploration."""
from collections import deque

from .rules import RuleError
from .performance import read_analysis,cached_route,mutation

from .modern_catalog import UNITS
from .naval import Naval

SPEED={'scout':4,'builder':3,'army':2,'ship':4}
SPEED.update({key:info['speed'] for key,info in UNITS.items()})
STEP_COST=2
ATTACK_COST=20
UNIT_COST=60
METAL_PER_STRENGTH=3


class Mobility(Naval):
    def speed_for(self,state,kind):
        if kind in UNITS and self.era_for(state)<2: return 0
        return SPEED.get(kind,2)+int(kind!='ship' and 'logistics' in state.tech)+int(kind=='scout' and 'cartography' in state.tech)

    def terrain_allowed(self,unit,point):
        water=self.cell(point).terrain=='water'
        return water if unit['type']=='ship' else not water

    def remaining_moves(self,unit):
        used=unit.get('moves_used',0) if unit.get('moves_day')==self.day else 0
        return max(0,self.speed_for(self.state(unit['owner']),unit['type'])-used)

    @cached_route
    def find_route(self,unit,target=None,explore=False,assume_war_with=None):
        """Every returned edge is adjacent. Exploration never starts a war."""
        state=self.state(unit['owner']); start=tuple(unit['cell'])
        if unit.get('embarked_on'): return None
        goal=tuple(target) if target is not None else None
        if goal is not None:
            self.cell(goal)
            if not self.terrain_allowed(unit,goal): return None
        if goal==start: return []
        occupied={tuple(u['cell']):u for u in self.units if u['id']!=unit['id'] and not u.get('embarked_on')}
        allies=[sid for sid in state.allies if sid!=assume_war_with]
        frontier=deque([start]); previous={start:None}; found=None
        while frontier:
            position=frontier.popleft()
            if (explore and position!=start and self.cell(position).owner is None) or (not explore and position==goal):
                found=position; break
            neighbors=self.adjacent(position)
            offset=unit['id']%len(neighbors) if neighbors else 0
            neighbors=neighbors[offset:]+neighbors[:offset]
            if goal: neighbors.sort(key=lambda q:abs(q[0]-goal[0])+abs(q[1]-goal[1]))
            for point in neighbors:
                point=tuple(point)
                if point in previous: continue
                cell=self.cell(point); other=occupied.get(point)
                if not self.terrain_allowed(unit,point): continue
                if self.wall_hitpoints(cell)>0 and cell.owner not in (None,state.id) and not self.combat_unit(unit): continue
                if cell.owner in allies: continue
                if cell.owner not in (None,state.id) and self.war_permission(state.id,cell.owner): continue
                if other:
                    if other['owner']==state.id or other['owner'] in allies: continue
                    if explore: continue
                if explore and cell.owner not in (None,state.id): continue
                previous[point]=position; frontier.append(point)
        if found is None: return None
        route=[]
        while found!=start:
            route.append(list(found)); found=previous[found]
        route.reverse(); return route

    @mutation
    def step_unit(self,unit,target,automatic=False):
        state=self.state(unit['owner']); source=list(unit['cell']); dest=self.cell(target)
        if unit.get('embarked_on'): return 'Юнит находится на корабле: сначала disembark'
        if not self.terrain_allowed(unit,target): return 'Запрет среды: корабль только в воде, сухопутный юнит только на суше; оплата 0'
        if target not in self.adjacent(source): raise RuleError('Внутренняя ошибка маршрута: шаг должен быть соседним')
        other=self.unit_at(target)
        hostile=dest.owner not in (None,state.id) or (other and other['owner']!=state.id)
        if hostile:
            enemy=other['owner'] if other else dest.owner
            permission=self.war_permission(state.id,enemy)
            if permission: return permission
        sieging=hostile and self.wall_hitpoints(dest)>0
        if sieging and not self.combat_unit(unit): return 'Вражеская стена: для осады нужна армия; оплата 0'
        cost=STEP_COST+(ATTACK_COST if hostile else 0)
        if state.stocks['money']<cost: return 'Не хватает денег на следующий шаг'
        if self.remaining_moves(unit)<=0: return 'Лимит движения на этот день исчерпан'
        if other and (other['owner']==state.id or other['owner'] in state.allies): return 'Клетка занята своим или союзным юнитом'
        if dest.owner in state.allies: return 'Территория союзника'
        state.stocks['money']-=cost
        if unit.get('moves_day')!=self.day: unit['moves_day']=self.day; unit['moves_used']=0
        unit['moves_used']+=1
        old_owner=dest.owner
        wall_broken=False
        if sieging:
            wall_broken=self.hit_wall(unit,target,other)
        elif other:
            attack,defense=self.effective_strength(unit),self.effective_strength(other)
            armor=self.defense_armor(dest,other) if dest.owner==other['owner'] and dest.terrain!='water' else 0
            unit['strength']=round(unit['strength']-defense/self.strength_factor(unit),4)
            other['strength']=round(other['strength']-max(1,attack-armor)/self.strength_factor(other),4)
            if other['strength']<=0: self.remove_unit(other)
            if unit['strength']<=0: self.remove_unit(unit)
            self.log('war',f'{state.name}: бой в {target}, эффективная сила {attack:g} против {defense:g}.')
        alive=unit in self.units
        arrived=alive and (other is None or other not in self.units) and (not sieging or wall_broken)
        captured=arrived and old_owner!=state.id
        if arrived:
            self.clear_stationing(unit)
            unit['cell']=list(target); dest.owner=state.id
            for passenger in self.units:
                if passenger.get('embarked_on')==unit['id']: passenger['cell']=list(target)
        if hostile:
            enemy=other['owner'] if other else old_owner
            if enemy: self.set_war(state.id,enemy,f'Атака клетки {target}',attack=True)
            if arrived and old_owner not in (None,state.id):
                record=self.relation(old_owner,state.id)
                if record.get('last_border_violation_day')!=self.day:
                    self.relation_fact(old_owner,state.id,'border_violation',f'Вторжение через границу в {target}',-10)
                    record['last_border_violation_day']=self.day
                    record['grievances'].append(dict(day=self.day,text=f'{state.name}: вооружённое пересечение границы в {target}',source='engine'))
            if enemy and captured: self.relation_fact(enemy,state.id,'territory_loss',f'Захвачена клетка {target}',-5)
        entry=dict(day=self.day,unit_id=unit['id'],owner=state.id,source=source,target=list(target),
                   arrived=arrived,captured=captured,previous_owner=old_owner,cost=cost,automatic=automatic,**(dict(kind='siege') if sieging else {}))
        self.movement_log.append(entry)
        stats=self.day_stats.setdefault(state.id,{})
        stats['steps']=stats.get('steps',0)+1
        stats['captured']=stats.get('captured',0)+int(captured)
        stats['movement_cost']=stats.get('movement_cost',0)+cost
        description=f'Юнит #{unit["id"]} {source} → {target}, {cost} денег'+(' · осада, перехода нет' if sieging and not arrived else '')+(' · захват клетки' if captured else '')+(' · юнит погиб' if not alive else '')
        state.history.append(dict(day=self.day,text=description))
        self.log('movement',f'{state.name}: '+description)
        return None

    def advance_order(self,unit,automatic=False):
        walked=0; route=None
        if unit.get('skip_day')==self.day: return 0
        while unit in self.units and self.remaining_moves(unit)>0:
            order=unit.get('order')
            if not order or order.get('kind')=='hold': break
            explore=order['kind']=='explore'
            if route is None or not route: route=self.find_route(unit,order.get('target'),explore)
            if route is None:
                unit['blocked_reason']='Нет доступного пути: вода, границы союзника или занятые клетки'; break
            if not route:
                if not explore: unit['order']=None
                break
            destination=route[0]
            reason=self.step_unit(unit,destination,automatic)
            if reason: unit['blocked_reason']=reason; break
            unit['blocked_reason']=''; walked+=1
            if unit in self.units and unit['cell']==destination: route=route[1:]
            if not explore and unit in self.units and unit['cell']==order['target']:
                unit['order']=None; break
        return walked

    def movement_action(self,state,kind,args):
        if type(args.get('unit_id')) is not int: raise RuleError('unit_id должен быть целым номером своего юнита')
        unit=next((u for u in self.units if u['id']==args.get('unit_id') and u['owner']==state.id),None)
        if unit is None: raise RuleError('Не найден свой юнит по unit_id')
        if kind!='hold' and unit['type'] in UNITS and self.era_for(state)<2: raise RuleError('Захваченная современная техника законсервирована до собственного перехода в эпоху II')
        if kind=='hold':
            unit['order']=dict(kind='hold',issued_day=self.day); unit['blocked_reason']=''
            unit['command_day']=self.day
            return f'Юнит #{unit["id"]}: приказ удерживать позицию'
        if unit.get('embarked_on'): raise RuleError('Юнит перевозится кораблём; сначала высадка disembark')
        if kind=='explore': order=dict(kind='explore',issued_day=self.day)
        else:
            target=args.get('target_cell',args.get('target')); self.cell(target)
            if not self.terrain_allowed(unit,target):
                unit['last_rejected_order']=dict(day=self.day,target=list(target),reason='water_requires_navigation',charged=0)
                unit['skip_day']=self.day; unit['blocked_reason']=f'Цель {target}: неверная среда. Сухопутные юниты никогда не ходят по воде; нужен корабль и embark/disembark. Оплата 0.'
                raise RuleError(unit['blocked_reason'])
            route=self.find_route(unit,target)
            if route is None:
                unit['last_rejected_order']=dict(day=self.day,target=list(target),reason='unreachable',charged=0)
                unit['skip_day']=self.day; unit['blocked_reason']='К цели нет проходимого пути. За отказ деньги не списаны.'
                raise RuleError(unit['blocked_reason'])
            order=dict(kind='move',target=list(target),issued_day=self.day)
        unit['skip_day']=-1; unit['order']=order; unit['command_day']=self.day; unit['blocked_reason']=''; walked=self.advance_order(unit)
        return f'Юнит #{unit["id"]}: {kind}, выполнено шагов {walked}; клетка {unit["cell"]}'+(' · '+unit.get('blocked_reason','') if unit.get('blocked_reason') else '')

    def recruitment_sites(self,state):
        occupied={tuple(u['cell']) for u in self.units if not u.get('embarked_on')}
        sites=[p for p in self.positions(state.id) if tuple(p) not in occupied and self.cell(p).terrain!='water' and not self.cell(p).radiation]
        def rank(p):
            frontier=any(self.cell(q).owner is None and self.cell(q).terrain!='water' for q in self.adjacent(p))
            return (not frontier,p[1],p[0])
        return sorted(sites,key=rank)

    def exploration_recruitment_sites(self,state):
        result=[]
        occupied={tuple(unit['cell']) for unit in self.units}
        for point in self.recruitment_sites(state):
            if any(self.cell(q).owner is None and tuple(q) not in occupied and
                   self.cell(q).terrain!='water' for q in self.adjacent(point)):
                result.append(point)
            if len(result)>=16: break
        return result

    def run_operations(self):
        """Uniform standing service; model orders/hold/policy always take priority."""
        if self.operations_day==self.day: return
        offset=self.day%len(self.states)
        for state in self.states[offset:]+self.states[:offset]:
            if state.eliminated: continue
            policy=state.operations
            owned=len(self.positions(state.id))
            units=[u for u in self.units if u['owner']==state.id]
            wanted=min(policy.get('unit_limit',8),max(3,2+owned//20))
            sites=self.exploration_recruitment_sites(state)
            wartime=any(self.at_war(state.id,peer.id) for peer in self.states if not peer.eliminated and peer.id!=state.id)
            if (not wartime and policy.get('recruit',True) and owned and len(units)<wanted and sites and
                state.stocks['money']>=self.unit_price(state)+policy.get('reserve_money',30) and state.stocks['metal']>=METAL_PER_STRENGTH*3):
                result=self.execute(state,dict(type='unit',args=dict(cell=sites[0],type='scout',strength=3)))
                state.history.append(dict(day=self.day,text='Дежурный набор: '+result))
                self.log('operations',f'{state.name}: дежурный набор разведчика, {self.unit_price(state)} денег и {METAL_PER_STRENGTH*3} металла.')
            for unit in list(self.units):
                if unit['owner']!=state.id or unit.get('embarked_on'): continue
                if unit.get('skip_day')==self.day: continue
                if not unit.get('order') and unit.get('command_day')!=self.day and unit['type']=='scout' and policy.get('explore',True):
                    unit['order']=dict(kind='explore',issued_day=self.day,source='standing_policy')
                if unit.get('order'): self.advance_order(unit,automatic=True)
        self.operations_day=self.day

    @read_analysis
    def mobility_context(self,state):
        result=[]
        for unit in self.units:
            if unit['owner']!=state.id: continue
            route=self.find_route(unit,explore=True)
            nearby=[]
            for pos in self.adjacent(unit['cell']):
                cell=self.cell(pos); other=self.unit_at(pos)
                reason=('aboard_ship' if unit.get('embarked_on') else 'enemy_wall_requires_army' if self.wall_hitpoints(cell)>0 and cell.owner not in (None,state.id) and not self.combat_unit(unit) else 'wrong_medium' if not self.terrain_allowed(unit,pos) else
                        'occupied' if other else 'ally_border' if cell.owner in state.allies else None)
                nearby.append(dict(cell=pos,terrain=cell.terrain,owner=cell.owner,passable=reason is None,blocked_by=reason))
            alternatives=[]
            if route: alternatives.append(dict(target=route[-1],terrain=self.cell(route[-1]).terrain,path=route,cost=len(route)*STEP_COST))
            order=unit.get('order') or {}
            target=order.get('target')
            result.append(dict(unit_id=unit['id'],cell=list(unit['cell']),type=unit['type'],
                               moves_left=self.remaining_moves(unit),effective_strength=self.effective_strength(unit),tower_bonus_percent=self.tower_bonus(unit),order=unit.get('order'),
                               neutral_target=route[-1] if route else None,path_to_neutral=route,
                               adjacent_cells=nearby,safe_targets=alternatives,
                               current_target_terrain=self.cell(target).terrain if target else None,
                               last_rejected_order=unit.get('last_rejected_order'),
                               can_cross_water=unit['type']=='ship',embarked_on=unit.get('embarked_on'),
                               passengers=[u['id'] for u in self.units if u.get('embarked_on')==unit['id']],
                               blocked_reason=unit.get('blocked_reason','')))
        return result

    def remove_unit(self,unit):
        self.units[:]=[u for u in self.units if u['id']!=unit['id'] and u.get('embarked_on')!=unit['id']]

    def recruit_ship(self,state,args):
        p=args.get('cell'); cell=self.cell(p); strength=args.get('strength',3)
        if 'navigation' not in state.tech: raise RuleError('Для корабля нужна navigation')
        if cell.terrain!='water' or self.unit_at(p) or cell.owner not in (None,state.id): raise RuleError('Нужна свободная нейтральная или своя вода')
        if not any(self.cell(q).owner==state.id and self.cell(q).terrain!='water' for q in self.adjacent(p)): raise RuleError('Строительство корабля только у своего сухого берега')
        if type(strength) is not int or not 1<=strength<=10 or strength>5 and 'army' not in state.tech: raise RuleError('Недопустимая сила корабля')
        price=self.unit_price(state); metal=METAL_PER_STRENGTH*strength
        if state.stocks['money']<price or state.stocks['metal']<metal: raise RuleError('Недостаточно денег или металла на корабль')
        state.stocks['money']-=price; state.stocks['metal']-=metal; self.spawn(state.id,p,'ship',strength); cell.owner=state.id
        stats=self.day_stats.setdefault(state.id,{}); stats['recruited']=stats.get('recruited',0)+1
        return f'Корабль #{self.units[-1]["id"]} создан в {p}'

    def transport_action(self,state,kind,args):
        unit=next((u for u in self.units if u['id']==args.get('unit_id') and u['owner']==state.id),None)
        if not unit or unit['type']=='ship': raise RuleError('Нужен свой сухопутный пассажир')
        if unit.get('transport_day')==self.day: raise RuleError('Не более одной посадки или высадки юнита за день')
        if kind=='embark':
            ship=next((u for u in self.units if u['id']==args.get('ship_id') and u['owner']==state.id and u['type']=='ship'),None)
            if not ship or unit.get('embarked_on') or ship['cell'] not in self.adjacent(unit['cell']): raise RuleError('Нужен свой корабль у соседнего берега')
            if sum(u.get('embarked_on')==ship['id'] for u in self.units)>=self.ship_capacity(ship): raise RuleError('Корабль заполнен: мест больше нет')
            unit['embarked_on']=ship['id']; unit['cell']=list(ship['cell'])
        else:
            ship=next((u for u in self.units if u['id']==unit.get('embarked_on')),None)
            target=args.get('target_cell'); cell=self.cell(target)
            if not ship or target not in self.adjacent(ship['cell']) or cell.terrain=='water' or cell.radiation: raise RuleError('Высадка только на соседнюю безопасную сушу')
            other=self.unit_at(target);peer=other['owner'] if other and other['owner']!=state.id else cell.owner
            hostile=peer not in (None,state.id)
            if hostile:
                if not self.combat_unit(unit) or not self.at_war(state.id,peer):raise RuleError('Вражеский берег: нужны боевой пассажир и объявленная война')
                unit['embarked_on']=None
                error=self.step_unit(unit,target)
                if error:
                    unit['embarked_on']=ship['id'];raise RuleError(error)
                if unit in self.units and unit['cell']!=target:unit['embarked_on']=ship['id'];unit['cell']=list(ship['cell'])
            else:
                if other:raise RuleError('Берег занят своим юнитом')
                unit['embarked_on']=None; unit['cell']=list(target); cell.owner=state.id
        self.clear_stationing(unit)
        unit['transport_day']=self.day; unit['moves_day']=self.day; unit['moves_used']=self.speed_for(state,unit['type']); unit['order']=dict(kind='hold',issued_day=self.day)
        return f'Юнит #{unit["id"]}: '+('посадка на корабль' if kind=='embark' else 'штурм берега: отряд погиб' if unit not in self.units else 'штурм берега: пока остался на корабле' if unit.get('embarked_on') else 'высадка на сушу')

    def sanitise_mobility(self):
        """Migrate legacy water walkers; preserve original coordinates as evidence."""
        for unit in self.units:
            unit.setdefault('embarked_on',None); unit.setdefault('max_strength',max(5,unit['strength']))
            host=next((u for u in self.units if u['id']==unit.get('embarked_on') and u['type']=='ship' and u['owner']==unit['owner']),None)
            if host: unit['cell']=list(host['cell']); continue
            unit['embarked_on']=None
            if not self.terrain_allowed(unit,unit['cell']):
                # Read-only migration produces a deterministic nearest legal position, never a paid step.
                original=list(unit['cell'])
                sites=[p for p in self.positions(unit['owner']) if self.terrain_allowed(unit,p) and not self.unit_at(p)]
                if not sites:
                    sites=[[i%self.size,i//self.size] for i,c in enumerate(self.cells) if c.owner is None and self.terrain_allowed(unit,[i%self.size,i//self.size]) and not self.unit_at([i%self.size,i//self.size])]
                if sites:
                    unit['cell']=min(sites,key=lambda p:abs(p[0]-original[0])+abs(p[1]-original[1]))
                    unit['migration_position']=dict(original=original,reason='v5.1: исправлена неверная среда; бесплатно')
            order=unit.get('order') or {}; target=order.get('target')
            invalid=False
            if target is not None:
                try: invalid=not self.terrain_allowed(unit,target)
                except (RuleError,TypeError,IndexError): invalid=True
            if invalid:
                unit['suspended_order']=dict(order); unit['order']=dict(kind='hold',issued_day=self.day)
                unit['blocked_reason']='v5.1: недопустимая среда цели; приказ приостановлен без оплаты'
