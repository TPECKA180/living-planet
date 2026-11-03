from __future__ import annotations

import copy
import json
import math
import random
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from .rules import RuleError
from .commerce import Commerce,FINANCIAL_ACTIONS
from .modern import Modern
from .modern_catalog import NEW_ACTIONS,MODERN_RESOURCES,UNITS as MODERN_UNITS
from .mobility import Mobility, SPEED, STEP_COST, ATTACK_COST, UNIT_COST, METAL_PER_STRENGTH
from .economy import Economy
from .technology import Technology, TECHS, TECHNOLOGIES
from .strategy import Strategy
from .politics import Politics
from .planning import Planning
from .infrastructure import Infrastructure
from .performance import AnalysisCache,read_analysis,mutation
from .diplomacy import Diplomacy
from .learning import Learning

RESOURCES = ('food', 'resource', 'metal', 'science', 'matter', 'money')
PRICES = dict(build=200, unit=UNIT_COST, army=0, move=0, explore=0, hold=0, policy=0, research=100, upgrade=300,
              relationship=0,declare_war=0,peace=0,embargo=0,
              embark=0,disembark=0,reinforce=0,convert=0,fortify=0,improve_building=0,demand_surrender=0,surrender=0,offer_vassalage=0,accept_vassalage=0,rebel=0,release_vassal=0,pledge=0,repair_wall=0,
              trade=0, transfer=0, accept_trade=0, settle=50, alliance=200, migrate=50, do_nothing=0)
PRICES.update(dict.fromkeys(NEW_ACTIONS+FINANCIAL_ACTIONS,0))
BUILDINGS = ('lab', 'castle', 'mine', 'tavern', 'arsenal','tower','wall')
COLORS = [(92, 207, 178), (239, 174, 91), (159, 143, 240), (103, 177, 241), (239, 127, 153), (197, 213, 113)]


@dataclass
class Cell:
    terrain: str
    level: int
    owner: str | None = None
    building: str | None = None
    building_level: int = 0
    population: int = 0
    fortification: int = 0
    wall_hp: float | None = None
    radiation: int = 0
    integrity: float = 100
    factory_enabled: bool = True
    factory_priority: int | None = None
    last_fired_day: int = -1


@dataclass
class State:
    id: str
    name: str
    color: list
    stocks: dict = field(default_factory=lambda: dict(food=250, resource=250, metal=150, science=50, matter=0, money=1200))
    notes: str = 'Мы — молодое государство. Наш характер и цели ещё предстоит сформировать.'
    plan: str = 'Развивать государство: увеличивать население, ресурсы и территорию. Вести переговоры.'
    thinking: str = 'Ожидание первого решения модели.'
    history: list = field(default_factory=list)
    tech: list = field(default_factory=list)
    allies: list = field(default_factory=list)
    memory: list = field(default_factory=list)
    operations: dict = field(default_factory=lambda:dict(explore=True,recruit=True,reserve_money=30,unit_limit=8))
    relations: dict = field(default_factory=dict)
    strategic_assessment: dict = field(default_factory=dict)
    decision_outcome: dict = field(default_factory=dict)
    construction_review: dict = field(default_factory=dict)
    economic_review: dict = field(default_factory=dict)
    era: int = 1
    modern: dict = field(default_factory=dict)
    vassal_of: str | None = None
    eliminated: bool = False
    defeated_by: str | None = None


class World(Commerce,Modern,Mobility,Economy,Diplomacy,Technology,Strategy,Politics,Planning,Infrastructure,AnalysisCache,Learning):
    def __init__(self, size=128, count=4, seed=42,map_mode='normal'):
        from .geography import MODES
        if map_mode not in MODES:raise ValueError('Режим мира: normal или archipelago')
        if map_mode=='archipelago' and size<24:raise ValueError('Для шести островов нужна карта не меньше 24')
        self.map_mode=map_mode;self.generation_size=size
        self.size, self.seed, self.day, self.cursor = size, seed, 0, 0
        self.in_day = False
        self.phase='idle'
        self.pending_decisions={}
        self.decisions=[]
        self.messages=[]
        self.trade_offers=[]
        self.next_offer=1
        self.patch='7.5.5'
        self.supply_pacts=[]; self.next_supply=1
        self.exchanges=[]; self.next_exchange=1; self.settlements=[]; self.next_receipt=1
        self.rules_version=6
        self.vassal_offers=[]; self.vassal_treaties=[]; self.pledges=[]; self.next_vassal_offer=1; self.next_pledge=1
        self.surrender_demands=[]
        self.wars=[]
        self.daily_income={}
        self.movement_log=[]
        self.day_stats={}
        self.last_day_stats={}
        self.operations_day=0
        self.cells = [self.generate(x, y) for y in range(size) for x in range(size)]
        if map_mode=='archipelago':
            from .geography import clean_islands
            clean_islands(self.cells,size,seed)
        names = ['Аврора', 'Гелиос', 'Орион', 'Таласса', 'Эос', 'Вега']
        self.states = [State(f'state_{i+1}', names[i], list(COLORS[i])) for i in range(count)]
        self.learning={}
        for state in self.states:self.learning_record(state.id)
        self.units, self.events, self.chapter = [], [], 0
        self.history_book=[]
        self.next_unit = 1
        for i, state in enumerate(self.states):
            angle = 2 * math.pi * i / count
            cx, cy = int(size/2 + size*.27*math.cos(angle)), int(size/2 + size*.27*math.sin(angle))
            if map_mode=='archipelago':
                from .geography import island_centres
                cx,cy=island_centres(size,seed)[i]
            for y in range(cy-2, cy+3):
                for x in range(cx-2, cx+3):
                    c = self.cell([x, y]); c.owner = state.id
                    c.terrain, c.level = 'grass', 3
            for pos, terrain in [([cx+1,cy], 'science'), ([cx-1,cy], 'resource'), ([cx,cy+1], 'forest')]:
                self.cell(pos).terrain = terrain
            for pos in ([cx,cy], [cx+1,cy], [cx-1,cy]):
                self.cell(pos).population = 1
            c = self.cell([cx,cy]); c.building, c.building_level = 'castle', 1
            self.spawn(state.id, [cx,cy], 'scout', 5)
            self.spawn(state.id, [cx,cy-1], 'builder', 5)
        self.initialise_relations()
        self.log('world', 'Начало истории. Государства пробуждаются.')

    def generate(self, x, y):
        from .geography import is_water,biome
        terrain,level=biome(x,y,self.seed)
        if is_water(x,y,getattr(self,'generation_size',self.size),self.seed,getattr(self,'map_mode','normal')):terrain='water'
        return Cell(terrain,level)

    def cell(self, pos):
        if not isinstance(pos, (list,tuple)) or len(pos) != 2 or any(type(v) is not int for v in pos):
            raise RuleError('cell должен быть [x, y] с целыми координатами')
        x,y = pos
        if not (0 <= x < self.size and 0 <= y < self.size):
            raise RuleError('Клетка за пределами мира')
        return self.cells[y*self.size+x]

    def positions(self, sid):
        index=getattr(self,'_analysis_index',None)
        if index is not None: return [p[:] for p in index['positions'].get(sid,[])]
        return [[i % self.size, i // self.size] for i,c in enumerate(self.cells) if c.owner == sid]

    def state(self, sid):
        found = next((s for s in self.states if s.id == sid), None)
        if found is None: raise RuleError('Неизвестное государство')
        return found

    def adjacent(self, pos):
        x,y=pos
        return [[a,b] for a,b in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)) if 0<=a<self.size and 0<=b<self.size]

    def neighbors(self, sid):
        return sorted({self.cell(q).owner for p in self.positions(sid) for q in self.adjacent(p)
                       if self.cell(q).owner not in (None,sid)})

    def unit_at(self, p):
        index=getattr(self,'_analysis_index',None)
        if index is not None: return index['occupied'].get(tuple(p))
        return next((u for u in self.units if u['cell'] == p and not u.get('embarked_on')), None)

    @mutation
    def spawn(self, sid, pos, kind, strength):
        if kind not in SPEED or not self.terrain_allowed(dict(type=kind),pos): raise RuleError('Нельзя создать юнит в неверной среде: корабль в воде, остальные на суше')
        if self.unit_at(pos): raise RuleError('На клетке уже есть юнит')
        self.units.append(dict(id=self.next_unit, owner=sid, cell=list(pos), type=kind, strength=strength,
                               max_strength=strength,embarked_on=None,born_day=self.day,order=None,moves_day=-1,moves_used=0,command_day=-1,skip_day=-1,blocked_reason=''))
        self.next_unit += 1

    def log(self, kind, text,visible_to=None):
        self.events.append(dict(day=self.day, kind=kind, text=text,**(dict(visible_to=list(visible_to)) if visible_to is not None else {})))

    @mutation
    def income(self):
        before={s.id:copy.deepcopy(s.stocks) for s in self.states}; gross_money={}
        for s in self.states:
            if self.era_for(s)==2:
                gross_money[s.id]=self.modern_income(s); continue
            owned=self.positions(s.id); gross_money[s.id]=0
            for p in owned:
                for key,value in self.production_for_cell(s,self.cell(p)).items():
                    s.stocks[key]+=value
                    if key=='money': gross_money[s.id]+=value
            upkeep=self.citizen_upkeep(s)
            for p in owned:
                c=self.cell(p)
                if c.population:
                    if all(s.stocks[key]>=value for key,value in upkeep.items()):
                        for key,value in upkeep.items(): s.stocks[key]=round(s.stocks[key]-value,2)
                    else:
                        c.population=0
                        self.log('famine', f'{s.name}: житель в {p} погиб от нехватки запасов.')
        self.pay_tribute(gross_money)
        for unit in list(self.units):
            if self.cell(unit['cell']).radiation>0:
                unit['strength']=round(unit['strength']*.85,4)
                if unit['strength']<1: self.remove_unit(unit)
        for s in self.states:
            self.daily_income[s.id]={key:round(s.stocks.get(key,0)-before[s.id].get(key,0),4) for key in self.resource_keys(s)}

    def start_day(self):
        if self.in_day: return
        self.day += 1; self.cursor=0; self.in_day=True
        self.last_day_stats=copy.deepcopy(self.day_stats); self.day_stats={}
        self.phase='planning'; self.pending_decisions={}
        opening_stocks={s.id:dict(s.stocks) for s in self.states}
        self.process_contracts()
        self.process_supply()
        self.process_exchanges()
        self.prepare_tower_day()
        self.income()
        for s in self.states:
            self.daily_income[s.id]={k:round(s.stocks.get(k,0)-opening_stocks[s.id].get(k,0),4) for k in self.resource_keys(s)}
        for offer in self.trade_offers:
            if offer['status']=='open' and offer['expires']<self.day: offer['status']='expired'

    def resolve_round(self):
        """All agents planned against the same world; apply once, on a clone."""
        reward_before=self.reward_baseline()
        order=self.day % len(self.states)
        before={s.id:len(self.positions(s.id)) for s in self.states}
        self._opinion_baselines={(s.id,peer):record['trust'] for s in self.states for peer,record in s.relations.items()}
        for s in self.states[order:]+self.states[:order]:
            if s.id in self.pending_decisions and not s.eliminated: self.apply_decision(s,self.pending_decisions[s.id])
        self.run_operations()
        self.finish_tower_day()
        self.check_eliminations()
        self.settle_rewards(reward_before)
        for s in self.states:
            stats=self.day_stats.setdefault(s.id,{})
            stats['territory_delta']=len(self.positions(s.id))-before[s.id]
            if s.decision_outcome.get('day')==self.day:
                s.decision_outcome['after_round']=dict(stocks=copy.deepcopy(s.stocks),territory=len(self.positions(s.id)),population=sum(self.cell(p).population for p in self.positions(s.id)),stats=copy.deepcopy(stats))
            self.log('summary',f'{s.name}: шагов {stats.get("steps",0)}, территория {stats["territory_delta"]:+d}, новых юнитов {stats.get("recruited",0)}.')
        self.pending_decisions={}
        self.phase='manager'
        del self._opinion_baselines
        self.log('round', f'Общий ход {self.day}: решения всех государств применены.')

    def send_message(self,s,recipient,text):
        if recipient!='all':
            partner=self.state(recipient)
            if partner.eliminated: raise RuleError('Партнёр выбыл')
            if partner.id==s.id: raise RuleError('Нельзя отправить сообщение самому себе')
        if not isinstance(text,str) or not 1<=len(text.strip())<=4000: raise RuleError('Длина сообщения: 1–4000 символов')
        message=dict(id=len(self.messages)+1,day=self.day,sender=s.id,recipient=recipient,text=text.strip())
        self.messages.append(message)
        self.log('diplomacy', f'{s.name} → {recipient}: {text.strip()}')

    @mutation
    def execute(self, s, a):
        """Validate every prerequisite before any mutation or deduction."""
        if not isinstance(a,dict): raise RuleError('Действие должно быть объектом')
        if s.eliminated: raise RuleError('Государство выбыло; его история сохранена')
        kind=a.get('type', a.get('action'))
        if kind not in PRICES: raise RuleError('Неизвестное действие')
        args=a.get('args', a)
        if not isinstance(args,dict): raise RuleError('args должен быть объектом')
        if kind in ('unit','recruit_modern'):
            if type(args.get('count',1)) is not int or args.get('count',1)<1:raise RuleError('count должен быть положительным целым числом')
            if args.get('count',1)!=1:return self.recruit_group(s,kind,args)
        if kind in FINANCIAL_ACTIONS: return self.financial_action(s,kind,args)
        modern_result=self.modern_action(s,kind,args)
        if modern_result is not None: return modern_result
        if kind=='repair_wall': return self.repair_wall(s,args)
        if kind in ('offer_vassalage','accept_vassalage','rebel','release_vassal','pledge'): return self.politics_action(s,kind,args)
        if kind in ('embark','disembark'): return self.transport_action(s,kind,args)
        if kind in ('reinforce','convert','fortify','improve_building'): return self.matter_action(s,kind,args)
        if kind in ('demand_surrender','surrender'): return self.surrender_action(s,kind,args)
        if kind=='do_nothing': return 'Ожидание'
        if kind in ('army','move','explore','hold'): return self.movement_action(s,kind,args)
        if kind in ('relationship','declare_war','peace','embargo'): return self.diplomatic_action(s,kind,args)
        if kind=='unit' and args.get('unit',args.get('type'))=='ship': return self.recruit_ship(s,args)
        p=args.get('cell')
        # National policy and diplomacy do not need an arbitrary map coordinate.
        if p is None and kind in ('policy','alliance','migrate'):
            positions=self.positions(s.id)
            if not positions: raise RuleError('Нет собственной территории')
            p=positions[0]
        c=self.cell(p)
        if c.owner != s.id: raise RuleError('Нужна своя клетка')
        price=self.unit_price(s) if kind=='unit' else 160 if kind=='build' and 'engineering' in s.tech else 240 if kind=='upgrade' and 'engineering' in s.tech else PRICES[kind]
        if s.stocks['money']<price: raise RuleError('Недостаточно денег')
        if kind=='policy':
            changed={key:args[key] for key in ('explore','recruit','war_recruit','war_army_limit','reserve_money','unit_limit') if key in args}
            if not changed: raise RuleError('Нет параметров дежурных приказов')
            if any(type(changed[key]) is not bool for key in ('explore','recruit','war_recruit') if key in changed): raise RuleError('explore/recruit/war_recruit должны быть true/false')
            for key,low,high in (('reserve_money',0,100000),('unit_limit',0,50),('war_army_limit',0,20)):
                if key in changed and (type(changed[key]) is not int or not low<=changed[key]<=high): raise RuleError(f'Некорректный параметр {key}')
            s.operations.update(changed)
            if changed.get('explore') is False:
                for unit in self.units:
                    if unit['owner']==s.id and (unit.get('order') or {}).get('source')=='standing_policy': unit['order']=None
        elif kind=='settle':
            amount=args.get('amount',1)
            if type(amount) is not int or not 1<=amount<=10: raise RuleError('Количество жителей: 1–10')
            if c.population or c.terrain=='water' or c.radiation: raise RuleError('Начальная клетка должна быть свободна от жителей, воды и радиации')
            own=self.positions(s.id)
            if sum(self.cell(q).population for q in own)<2: raise RuleError('Для роста нужны минимум два существующих жителя')
            free=sorted([q for q in own if not self.cell(q).population and self.cell(q).terrain!='water' and not self.cell(q).radiation],key=lambda q:abs(q[0]-p[0])+abs(q[1]-p[1]))
            price=50*amount
            if len(free)<amount or s.stocks['money']<price or s.stocks['food']<30*amount or s.stocks['resource']<10*amount:
                raise RuleError('На жителя нужны свободная клетка, 50 денег, 30 еды и 10 сырья')
            s.stocks['food']-=30*amount; s.stocks['resource']-=10*amount
            for q in free[:amount]: self.cell(q).population=1
        elif kind=='build':
            b=args.get('building',args.get('type')); level=args.get('level',1)
            if b not in BUILDINGS or type(level) is not int or not 1<=level<=10: raise RuleError('Неверный тип или уровень здания')
            if c.building or c.terrain=='water' or c.radiation: raise RuleError('Клетка занята, находится в воде или заражена радиацией')
            if b=='lab' and c.terrain!='science': raise RuleError('Лаборатория требует клетку науки')
            if b=='mine' and c.terrain not in ('resource','mountain'): raise RuleError('Шахта требует ресурс или гору')
            raw_cost=15*level if 'masonry' in s.tech else 20*level
            if s.stocks['resource']<raw_cost: raise RuleError(f'Недостаточно сырья: нужно {raw_cost}')
            c.building=b; c.building_level=level; c.wall_hp=20*level if b=='wall' else None; s.stocks['resource']-=raw_cost
        elif kind=='unit':
            t=args.get('unit',args.get('type')); strength=args.get('strength',1)
            if t not in ('scout','builder','army') or type(strength) is not int or not 1<=strength<=10: raise RuleError('Неверный юнит / сила')
            if strength>5 and 'army' not in s.tech: raise RuleError('Сила выше 5 требует технологии army')
            if self.unit_at(p) or c.terrain=='water' or c.radiation: raise RuleError('Клетка занята, находится в воде или заражена радиацией')
            if s.stocks['metal']<METAL_PER_STRENGTH*strength: raise RuleError('Недостаточно металла (3 × сила)')
            self.spawn(s.id,p,t,strength); s.stocks['metal']-=METAL_PER_STRENGTH*strength
            stats=self.day_stats.setdefault(s.id,{})
            stats['recruited']=stats.get('recruited',0)+1
        elif kind=='research':
            tech=args.get('tech')
            if c.integrity<=0: raise RuleError('Научное здание разрушено')
            if (c.terrain!='science' or c.building!='lab') and not (self.era_for(s)==2 and c.building in ('university','engineering_institute','physics_lab','computing_center','radiation_station')): raise RuleError('Нужна лаборатория на клетке науки')
            if tech not in TECHS or tech in s.tech: raise RuleError('Неизвестная или уже открытая технология')
            info=TECHNOLOGIES[tech]
            if any(t not in s.tech for t in info['requires']): raise RuleError('Сначала исследуйте: '+', '.join(info['requires']))
            if any(s.stocks[key]<info[key] for key in ('money','science','matter')): raise RuleError(f"Исследование требует {info['money']} денег, {info['science']} науки, {info['matter']} материи")
            s.stocks['science']-=info['science']; s.stocks['matter']-=info['matter']; price=info['money']; s.tech.append(tech)
        elif kind=='upgrade':
            tech=args.get('tech')
            if tech not in s.tech: raise RuleError('Технология не исследована')
            # Upgrades affect tile yield, never building levels or unit strength.
            if c.level>=10: raise RuleError('Клетка уже уровня 10')
            if tech not in ('agriculture','mine','lab'): raise RuleError('Улучшение требует agriculture / mine / lab')
            expected={'agriculture':('grass','forest'),'mine':('mountain','resource'),'lab':('science',)}
            if c.terrain not in expected[tech]: raise RuleError('Технология не подходит типу клетки')
            c.level+=1
        else:
            partner=self.state(args.get('partner'))
            if partner.eliminated or partner.id==s.id: raise RuleError('Нужен другой действующий партнёр')
            if partner.id not in self.neighbors(s.id): raise RuleError('Партнёр должен иметь общую границу')
            if kind=='alliance':
                if partner.id in s.allies: raise RuleError('Союз уже заключён')
                if self.at_war(s.id,partner.id): raise RuleError('Сначала обе стороны должны согласиться на мир')
                s.allies.append(partner.id); partner.allies.append(s.id)
                for own,other in ((s.id,partner.id),(partner.id,s.id)): self.relation_fact(own,other,'alliance','Заключён союз',15)
            elif kind=='migrate':
                amount=args.get('amount')
                if type(amount) is not int or not 1<=amount<=10: raise RuleError('Количество:1–10')
                source=[self.cell(q) for q in self.positions(s.id) if self.cell(q).population]
                dests=[self.cell(q) for q in self.positions(partner.id) if not self.cell(q).population and self.cell(q).terrain!='water' and not self.cell(q).radiation]
                if len(source)<amount or len(dests)<amount: raise RuleError('Не хватает жителей или свободных клеток')
                for source_cell,dest_cell in zip(source[:amount],dests[:amount]): source_cell.population-=1; dest_cell.population+=1
            else: raise RuleError('Не обработан тип действия')
        s.stocks['money']-=price
        return f'{kind} {json.dumps(args,ensure_ascii=False)}'

    def apply_decision(self, s, decision):
        try:self.start_experiment(s,decision.get('learning_review'))
        except (ValueError,TypeError,KeyError) as exc:self.learning_record(s.id)['review_error']=str(exc)
        text=decision.get('learning_notes')
        if isinstance(text,str) and text.strip() and len(text)<=8000:
            record=self.learning_record(s.id)
            if record['notes']!=text:
                record['notes']=text;record['notes_history'].append(dict(day=self.day,text=text))
        if isinstance(decision.get('economic_review'),dict): s.economic_review=copy.deepcopy(decision['economic_review'])
        if isinstance(decision.get('construction_review'),dict): s.construction_review=copy.deepcopy(decision['construction_review'])
        outcome=dict(day=self.day,chosen=(decision.get('strategic_assessment') or {}).get('chosen'),before=dict(stocks=copy.deepcopy(s.stocks),territory=len(self.positions(s.id))),accepted=0,rejected=[],action_results=[])
        if decision.get('strategic_assessment'): s.strategic_assessment=copy.deepcopy(decision['strategic_assessment'])
        s.thinking=decision['thinking']; s.notes=decision['notes']; s.plan=decision['plan']
        s.memory.append(dict(day=self.day,notes=s.notes,plan=s.plan,**(dict(strategic_assessment=copy.deepcopy(s.strategic_assessment)) if s.strategic_assessment else {})))
        self.decisions.append(dict(day=self.day,state=s.id,decision=copy.deepcopy(decision)))
        outcome['message_results']=[]; outcome['relation_results']=[]
        outcome['preparation_results']=copy.deepcopy(decision.get('local_preparation',{}))
        for peer,review in decision.get('relation_reviews',{}).items():
            try:
                result=self.diplomatic_action(s,'relationship',dict(partner=peer,**review))
                s.history.append(dict(day=self.day,text=result))
                outcome['relation_results'].append(dict(partner=peer,success=True,message=result))
            except (RuleError,TypeError) as exc:
                outcome['relation_results'].append(dict(partner=peer,success=False,message=str(exc)))
        for message in decision.get('diplomacy',[]):
            try:
                self.send_message(s,message.get('to'),message.get('text'))
                outcome['message_results'].append(dict(to=message.get('to'),success=True))
            except (RuleError,AttributeError,TypeError) as exc:
                outcome['message_results'].append(dict(to=message.get('to') if isinstance(message,dict) else None,success=False,message=str(exc)))
                self.log('rejected',f'{s.name}: сообщение отклонено: {exc}',visible_to=[s.id])
        for action in decision['actions']:
            try:
                receipt_before=self.next_receipt; result=self.execute(s,action); outcome['accepted']+=1
            except (RuleError, TypeError, KeyError) as exc:
                result=f'Отклонено: {exc}'; outcome['rejected'].append(result)
            outcome['action_results'].append(dict(type=action.get('type',action.get('action')) if isinstance(action,dict) else None,args=copy.deepcopy(action.get('args',{})) if isinstance(action,dict) else {},success=not result.startswith('Отклонено:'),message=result,receipt_ids=list(range(receipt_before,self.next_receipt)) if 'receipt_before' in locals() else []))
            s.history.append(dict(day=self.day,text=result))
            args=action.get('args',{}) if isinstance(action,dict) else {}
            if not isinstance(args,dict): args={}
            private=[s.id,args.get('partner')] if isinstance(action,dict) and action.get('type')=='pledge' and not args.get('public',False) else None
            self.log('action', f'{s.name}: {result}',visible_to=private or [s.id])
        outcome['after_actions']=dict(stocks=copy.deepcopy(s.stocks),territory=len(self.positions(s.id)))
        if s.construction_review:
            rows=[r for r in outcome['action_results'] if r['type']=='build']
            s.construction_review['execution_result']=dict(day=self.day,built=sum(r['success'] for r in rows),
                rejected=[r['message'] for r in rows if not r['success']],status='built' if any(r['success'] for r in rows) else 'rejected' if rows else 'deferred')
        s.decision_outcome=outcome

    def visible_trade_offer(self,state,offer):
        value=copy.deepcopy(offer)
        value['my_role']='seller' if offer['seller']==state.id else 'buyer'
        value['can_accept']=offer['partner']==state.id and offer['status']=='open' and offer.get('expires',self.day)>=self.day
        if offer['seller']!=state.id: value.pop('seller_reason',None)
        if offer['partner']!=state.id: value.pop('buyer_reason',None)
        if 'withheld' in value:
            value['own_withholding_until']=value.pop('withheld').get(state.id)
        return value

    @read_analysis
    def context(self, s, config=None):
        config=config or {}
        own=self.positions(s.id)
        visible={tuple(p) for p in own}
        for _ in range(2 if 'cartography' in s.tech else 1):
            visible.update(tuple(q) for p in list(visible) for q in self.adjacent(p))
        unit_positions={tuple(u['cell']) for u in self.units}
        limit=int(config.get('context_map_cells',4096))
        chosen=sorted(visible, key=lambda p: (self.cell(p).building is None, p not in unit_positions, p))[:limit]
        forecast=self.economic_forecast(s)
        context=dict(day=self.day,identity=dict(id=s.id,name=s.name),round_rule='Общий день: все решения собираются до исполнения. Сообщения и изменения видны со следующего дня.',
                    objective='Стать сильнейшим государством: превосходство в территории, населении, экономике и армии. Дипломатия, экономическое давление и выгодные войны — инструменты развития.',
                    technology_catalog=self.research_catalog(s),strategy=self.strategic_context(s),strategic_brief=self.decision_brief(s,forecast),construction=self.construction_context(s,forecast),politics=self.political_context(s),previous_assessment=copy.deepcopy(s.strategic_assessment),previous_outcome=copy.deepcopy(s.decision_outcome),previous_construction_review=copy.deepcopy(s.construction_review),previous_economic_review=copy.deepcopy(s.economic_review),matter_uses='Продвинутые исследования; reinforce после military_medicine; convert после alchemy; fortify после fortification; improve_building после aether_forging.',
                    size=self.size,state=s.id,private_owner=s.id,stocks={k:s.stocks.get(k,0) for k in self.resource_keys(s)},notes=s.notes,plan=s.plan,learning=self.learning_context(s.id),
                    rules=dict(version=6,patch='7.5.5',action_prices=copy.deepcopy(PRICES),effective_unit_price=self.unit_price(s),step_cost=STEP_COST,attack_extra=ATTACK_COST,
                               speed={kind:self.speed_for(s,kind) for kind in SPEED},land_water_rule='Суша: сухопутные юниты, включая современные. Вода: только ship. navigation не разрешает пехоте воду. Для перевозки embark/disembark.',unit_metal_per_strength=METAL_PER_STRENGTH,money_per_tile=4,money_per_citizen=1),
                    standing_policy=copy.deepcopy(s.operations),mobility=self.mobility_context(s),military=self.military_context(s),naval=self.naval_context(s),map_mode=getattr(self,'map_mode','normal'),
                    economy=forecast,relations=self.relations_context(s),
                    trade_analysis=[self.assess_trade(s,o,forecast) for o in self.trade_offers if o['partner']==s.id and o['status']=='open'],
                    recruitment_sites=self.recruitment_sites(s)[:16],last_day_stats=copy.deepcopy(self.last_day_stats.get(s.id,{})),
                    population=sum(self.cell(p).population for p in own),food_per_day=sum(self.cell(p).population*self.citizen_upkeep(s)['food'] for p in own),
                    territory_count=len(own), map_truncated=len(visible)>limit,
                    map_columns=['x','y','terrain','level','owner','building','building_level','population'],
                    map=[[p[0],p[1],self.cell(p).terrain,self.cell(p).level,self.cell(p).owner,self.cell(p).building,self.cell(p).building_level,self.cell(p).population] for p in chosen],
                    units=[dict(copy.deepcopy(u),effective_strength=self.effective_strength(u),tower_bonus_percent=self.tower_bonus(u),era_locked=u['type'] in MODERN_UNITS and self.era_for(self.state(u['owner']))<2) for u in self.units if u['owner']==s.id or tuple(u['cell']) in visible],
                    buildings=[dict(cell=p,type=self.cell(p).building,level=self.cell(p).building_level,population=self.cell(p).population) for p in own if self.cell(p).building],
                    action_sites=self.legal_action_sites(s),commerce=self.commerce_context(s),era=self.era_for(s),modern=self.modern_context(s),states=[dict(id=other.id,name=other.name,era=self.era_for(other),eliminated=other.eliminated) for other in self.states],
                    tech=list(s.tech),neighbors=self.neighbors(s.id),allies=list(s.allies),
                    memory=[dict(copy.deepcopy(m),owner=s.id) for m in s.memory[-int(config.get('context_memories',40)):]],
                    messages=copy.deepcopy([m for m in self.messages if m['sender']==s.id or m['recipient'] in (s.id,'all')][-int(config.get('context_messages',200)):]),
                    trade_offers=[self.visible_trade_offer(s,o) for o in self.trade_offers if s.id in (o['seller'],o['partner']) and o['status']=='open'],
                    history=[dict(copy.deepcopy(h),owner=s.id) for h in s.history[-int(config.get('context_history',200)):]],events=copy.deepcopy([e for e in self.events if e['kind'] not in ('diplomacy','action') and ('visible_to' not in e or s.id in e['visible_to'])][-int(config.get('context_events',150)):]))
        from .intelligence import briefing,CONTRACTS
        from .operation_support import treasury_options
        context['commerce']['order_templates']=treasury_options(context)
        return dict(decision_support=briefing(context),action_contracts={kind:dict(required=required) for kind,(_,required) in CONTRACTS.items()},**context)

    def manager(self, event):
        kind=event['event']; target=event.get('target')
        if target is not None and target not in [s.id for s in self.states]: raise RuleError('Неизвестная цель события')
        for s in self.states:
            if s.eliminated: continue
            if target is not None and s.id!=target: continue
            if kind=='harvest': s.stocks['food']+=50
            elif kind=='drought': s.stocks['food']=max(0,s.stocks['food']-40)
            elif kind=='fair': s.stocks['money']+=80
            elif kind=='epidemic':
                inhabited=[self.cell(p) for p in self.positions(s.id) if self.cell(p).population]
                if inhabited: inhabited[0].population=max(0,inhabited[0].population-max(1,int(inhabited[0].population*.1)))
            elif kind=='earthquake':
                buildings=[self.cell(p) for p in self.positions(s.id) if self.cell(p).building]
                if buildings: buildings[0].building=None; buildings[0].building_level=0; buildings[0].wall_hp=None
        self.chapter+=1
        self.log('chapter', f"Глава {self.chapter}. {event['title']} — {event['description']}")
        if event.get('expand') and self.size<512: self.expand()

    def expand(self):
        old=self.size; new=old*2
        self.cells=[self.cells[y*old+x] if x<old and y<old else self.generate(x,y) for y in range(new) for x in range(new)]
        self.size=new
        self.log('world',f'Открыты новые земли: {old} → {new}. Координаты старого мира сохранены.')

    def data(self):
        return dict(version=6,patch='7.5.5',map_mode=getattr(self,'map_mode','normal'),generation_size=getattr(self,'generation_size',self.size),exchanges=copy.deepcopy(self.exchanges),next_exchange=self.next_exchange,settlements=copy.deepcopy(self.settlements),next_receipt=self.next_receipt,supply_pacts=copy.deepcopy(self.supply_pacts),next_supply=self.next_supply,vassal_offers=copy.deepcopy(self.vassal_offers),vassal_treaties=copy.deepcopy(self.vassal_treaties),pledges=copy.deepcopy(self.pledges),next_vassal_offer=self.next_vassal_offer,next_pledge=self.next_pledge,surrender_demands=copy.deepcopy(self.surrender_demands),rules_version=6,wars=copy.deepcopy(self.wars),daily_income=copy.deepcopy(self.daily_income),size=self.size,seed=self.seed,day=self.day,cursor=self.cursor,in_day=self.in_day,
                    history_book=copy.deepcopy(self.history_book),movement_log=copy.deepcopy(self.movement_log),learning=copy.deepcopy(getattr(self,'learning',{})),day_stats=copy.deepcopy(self.day_stats),last_day_stats=copy.deepcopy(self.last_day_stats),operations_day=self.operations_day,
                    phase=self.phase,pending_decisions=copy.deepcopy(self.pending_decisions),decisions=copy.deepcopy(self.decisions),
                    messages=copy.deepcopy(self.messages),trade_offers=copy.deepcopy(self.trade_offers),next_offer=self.next_offer,
                    cells=[vars(c).copy() for c in self.cells],states=[asdict(s) for s in self.states],
                    units=copy.deepcopy(self.units),events=copy.deepcopy(self.events),chapter=self.chapter,next_unit=self.next_unit)

    @classmethod
    def restore(cls, data):
        obj=cls.__new__(cls)
        obj.phase='planning' if data.get('in_day') else 'idle'
        obj.history_book=[]
        obj.pending_decisions={}; obj.decisions=[]; obj.messages=[]; obj.trade_offers=[]; obj.next_offer=1
        obj.patch='7.5.5'; obj.surrender_demands=[]; obj.supply_pacts=[]; obj.next_supply=1
        obj.exchanges=[]; obj.next_exchange=1; obj.settlements=[]; obj.next_receipt=1
        obj.vassal_offers=[]; obj.vassal_treaties=[]; obj.pledges=[]; obj.next_vassal_offer=1; obj.next_pledge=1
        obj.rules_version=6; obj.wars=[]; obj.daily_income={}; obj.movement_log=[]; obj.day_stats={}; obj.last_day_stats={}
        obj.operations_day=data.get('day',0) if data.get('phase') in ('idle','manager') else -1
        for k,v in data.items():
            if k not in ('version','cells','states'): setattr(obj,k,copy.deepcopy(v))
        obj.cells=[Cell(**c) for c in data['cells']]; obj.states=[State(**copy.deepcopy(s)) for s in data['states']]
        for state in obj.states:obj.learning_record(state.id)
        obj.rules_version=6; obj.patch='7.5.5'
        for u in obj.units:
            for key,value in dict(born_day=None,order=None,moves_day=-1,moves_used=0,command_day=-1,skip_day=-1,blocked_reason='').items(): u.setdefault(key,value)
            order=u.get('order') or {}
            target=order.get('target')
            if data.get('version',1)<5 and target and obj.cell(target).terrain=='water' and 'navigation' not in obj.state(u['owner']).tech:
                u['suspended_order']=copy.deepcopy(order); u['order']=dict(kind='hold',issued_day=obj.day)
                u['blocked_reason']='Импорт: недоступная водная цель приостановлена без оплаты'
        obj.sanitise_mobility()
        obj.initialise_relations(historical=data.get('version',1)<5)
        for state in obj.states:
            state.era=obj.era_for(state)
            if state.era==2:
                for key in MODERN_RESOURCES: state.stocks.setdefault(key,0)
        return obj


class Store:
    def __init__(self,path,export=False,settings=None):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.export=export; self.settings=settings or {}; self._export_cache={}; self._format_verified=False; self.last_snapshot=None
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS chronicle (seq INTEGER PRIMARY KEY, day INTEGER, kind TEXT, text TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS memories (state TEXT, day INTEGER, notes TEXT, plan TEXT, PRIMARY KEY(state,day))')

    def save(self,world):
        snapshot=world.data()
        with closing(sqlite3.connect(self.path)) as db, db:
            old=None if self._format_verified else db.execute('SELECT data FROM snapshot WHERE id=1').fetchone()
            if old and (json.loads(old[0]).get('version',1)<5 or json.loads(old[0]).get('patch')!='7.5.5'):
                from .saves import backup_connection
                self.backup_path=backup_connection(db,self.path.parent,old[0])
            db.execute('INSERT OR REPLACE INTO snapshot VALUES (1,?)',(json.dumps(snapshot,ensure_ascii=False,separators=(',',':')) ,))
            last_seq=db.execute('SELECT COALESCE(MAX(seq),-1) FROM chronicle').fetchone()[0]
            db.executemany('INSERT OR IGNORE INTO chronicle VALUES (?,?,?,?)',[(i,e['day'],e['kind'],e['text']) for i,e in enumerate(world.events) if i>last_seq])
            last_mem=dict(db.execute('SELECT state,MAX(day) FROM memories GROUP BY state'))
            db.executemany('INSERT OR REPLACE INTO memories VALUES (?,?,?,?)',[(s.id,m['day'],m['notes'],m['plan']) for s in world.states for m in s.memory if m['day']>=last_mem.get(s.id,-1)])
        if self.export:
            from .saves import export_world
            export_world(self.path.parent,world,snapshot,self.settings,cache=self._export_cache)

        self._format_verified=True; self.last_snapshot=snapshot
        return snapshot

    def load(self):
        with closing(sqlite3.connect(self.path)) as db: row=db.execute('SELECT data FROM snapshot WHERE id=1').fetchone()
        return World.restore(json.loads(row[0])) if row else None
