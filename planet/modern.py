"""Second-era actions, abstract military systems and autonomous development hints."""
import copy,math,random
from .rules import RuleError
from .modern_catalog import BASE_RESOURCES,MODERN_RESOURCES,RESOURCE_NAMES,BUILDINGS,UNITS,MISSILES,TECHNOLOGIES,NEW_ACTIONS
from .modern_economy import ModernEconomy
from .modern_trade import ModernTrade,integer
from .performance import mutation,read_analysis


class Modern(ModernEconomy,ModernTrade):
    def pay_cost(self,state,cost):
        missing={k:round(v-state.stocks.get(k,0),2) for k,v in cost.items() if state.stocks.get(k,0)+1e-8<v}
        if missing: raise RuleError('Не хватает: '+', '.join(f'{RESOURCE_NAMES.get(k,k)} {v:g}' for k,v in missing.items()))
        for k,v in cost.items(): state.stocks[k]=round(state.stocks.get(k,0)-v,4)

    def modern_research(self,state,key,cell):
        info=TECHNOLOGIES[key]
        if key in state.tech: raise RuleError('Технология уже изучена')
        if key!='industrialization' and self.era_for(state)<2: raise RuleError('Сначала собственный эпохальный переход')
        if cell.owner!=state.id or cell.building not in ('lab','university','engineering_institute','physics_lab','computing_center','radiation_station'): raise RuleError('Нужно своё действующее научное здание')
        if cell.integrity<=0: raise RuleError('Научное здание разрушено')
        if any(t not in state.tech for t in info['requires']): raise RuleError('Нужны технологии: '+', '.join(t for t in info['requires'] if t not in state.tech))
        if info['site'] and not any(self.cell(p).building==info['site'] and self.cell(p).radiation>0 for p in self.positions(state.id)): raise RuleError('Нужна своя особая станция на радиоактивном полигоне')
        self.pay_cost(state,info['cost']); state.tech.append(key)
        if key=='industrialization':
            state.era=2; state.modern.update(entered_day=self.day,unrest=0,debt=0)
            for resource in MODERN_RESOURCES: state.stocks.setdefault(resource,0)
            self.log('era',f'{state.name} самостоятельно открывает ЭПОХУ II. Другие государства сохраняют свою эпоху.')
        return f'Исследовано: {info["name"]}'

    def modern_build(self,state,args):
        key=args.get('building',args.get('type')); info=BUILDINGS[key]; level=integer(args.get('level',1),1,info['max_level'],'Уровень здания'); c=self.cell(args.get('cell'))
        if info['tech'] not in state.tech: raise RuleError('Нужно исследование '+info['tech'])
        if c.owner!=state.id or c.terrain=='water': raise RuleError('Нужна своя сухопутная клетка')
        if key=='radiation_station':
            if c.building!='radiation_test_range' or c.radiation<=0: raise RuleError('Станция строится вместо своего радиационного полигона на той же клетке')
        elif c.building is not None: raise RuleError('Клетка уже занята зданием')
        if info.get('terrain') and c.terrain not in info['terrain']: raise RuleError('Подходящая местность: '+', '.join(info['terrain']))
        if key=='radiation_test_range' and c.population: raise RuleError('Полигон запрещён на населённой клетке')
        if c.radiation and not info.get('radioactive'): raise RuleError('Сначала очистите загрязнение')
        cost={k:v*level for k,v in info['cost'].items()}; self.pay_cost(state,cost)
        c.building=key; c.building_level=level; c.integrity=100; c.factory_enabled=True; c.factory_priority=None
        c.wall_hp=info.get('barrier',0)*level if info.get('barrier') else None
        if info.get('radioactive'): c.radiation=100; c.population=0
        return f'build {RESOURCE_NAMES.get(key,info["name"])} {args["cell"]} уровень {level}; оплачено {cost}'

    def place_people(self,state,amount,anchor=None):
        sites=self.positions(state.id)
        sites.sort(key=lambda p:(-self.population_capacity(state,self.cell(p)),abs(p[0]-anchor[0])+abs(p[1]-anchor[1]) if anchor else 0,p[1],p[0]))
        if sum(max(0,self.population_capacity(state,self.cell(p))-self.cell(p).population) for p in sites)<amount: raise RuleError('Не хватает жилых мест; постройте кварталы или небоскрёбы')
        left=amount
        for p in sites:
            c=self.cell(p); take=min(left,max(0,self.population_capacity(state,c)-c.population)); c.population+=take; left-=take
            if not left: break

    def edict(self,state,args):
        key=args.get('edict'); population=sum(self.cell(p).population for p in self.positions(state.id))
        if state.modern.get('edict_day')==self.day: raise RuleError('Один масштабный указ за день')
        if key=='population_campaign':
            if 'urban_planning' not in state.tech: raise RuleError('Нужно urban_planning')
            amount=integer(args.get('amount'),100,2000,'Новые жители'); anchor=args.get('cell')
            free=sum(max(0,self.population_capacity(state,self.cell(p))-self.cell(p).population) for p in self.positions(state.id))
            if free<amount: raise RuleError('Нужны свободные жилые места для демографической программы, в том числе заселения с нуля')
            if anchor is not None: self.cell(anchor)
            self.pay_cost(state,dict(money=amount*25,food=amount*40,resource=amount*5)); self.place_people(state,amount,anchor)
            result=f'Демографическая программа: +{amount} граждан; их снабжение начнётся со следующего дня'
        elif key in ('rationing','mobilization','emergency_tax'):
            self.pay_cost(state,dict(money=max(1000,population*3),food=population*5))
            state.modern[key+'_until']=self.day+5; state.modern['unrest']=min(100,state.modern.get('unrest',0)+8)
            result=f'Указ {key} действует до дня {self.day+5}; население недовольно'
        elif key=='public_relief':
            if 'public_health' not in state.tech: raise RuleError('Нужно public_health')
            self.pay_cost(state,dict(money=population*12,food=population*8,medicine=population*.05)); state.modern['unrest']=max(0,state.modern.get('unrest',0)-30)
            result='Социальная помощь: недовольство −30'
        elif key=='evacuation':
            amount=min(2000,sum(max(0,self.cell(p).population-self.population_capacity(state,self.cell(p))) for p in self.positions(state.id)))
            if not amount: raise RuleError('Нет перенаселённых клеток для эвакуации')
            free=sum(max(0,self.population_capacity(state,self.cell(p))-self.cell(p).population) for p in self.positions(state.id))
            amount=min(amount,free)
            if not amount: raise RuleError('Нет безопасных мест назначения')
            self.pay_cost(state,dict(money=1000+amount*10,food=amount*5)); left=amount
            for p in self.positions(state.id):
                c=self.cell(p); take=min(left,max(0,c.population-self.population_capacity(state,c))); c.population-=take; left-=take
            self.place_people(state,amount); result=f'Эвакуировано {amount} жителей'
        else: raise RuleError('Неизвестный указ')
        state.modern['edict_day']=self.day; return result

    def modern_recruitment_cost(self,kind):
        info=UNITS[kind]
        cost=dict(money=info['money']*15,steel=info['steel'],fuel=info['fuel']*5,food=info['crew']*10,**{info['weapon']:info['weapons']})
        if kind=='drone_swarm': cost['electronics']=100
        return cost

    def recruit_modern(self,state,args):
        key=args.get('unit',args.get('type')); info=UNITS.get(key); c=self.cell(args.get('cell'))
        if not info or info['tech'] not in state.tech: raise RuleError('Современный тип войск не открыт')
        if c.owner!=state.id or c.terrain=='water' or c.radiation or self.unit_at(args['cell']): raise RuleError('Нужна своя безопасная свободная сухопутная клетка')
        population=sum(self.cell(p).population for p in self.positions(state.id))
        if population-info['crew']<2: raise RuleError('Не хватает граждан для комплектования; экипаж покинет гражданскую экономику')
        cost=self.modern_recruitment_cost(key)
        self.pay_cost(state,cost)
        self.spawn(state.id,args['cell'],key,info['strength']); u=self.units[-1]; u.update(crew=info['crew'],supply_ratio=1,modern=True)
        left=info['crew']
        for p in sorted(self.positions(state.id),key=lambda p:self.cell(p).population,reverse=True):
            cell=self.cell(p); take=min(cell.population,left); cell.population-=take; left-=take
            if not left: break
        self.day_stats.setdefault(state.id,{})['recruited']=self.day_stats.get(state.id,{}).get('recruited',0)+1
        return f'Нанят {info["name"]}: сила {info["strength"]}, экипаж {info["crew"]}, ежедневное снабжение обязательно'

    def operating(self,state,p):
        return state.modern.get('operating',{}).get(f'{p[0]}:{p[1]}',0)
    def defense_armor(self,cell,defender=None):
        if not cell.owner: return cell.fortification
        info=BUILDINGS.get(cell.building,{})
        return cell.fortification+info.get('armor',0)*cell.building_level*self.operating(self.state(cell.owner),self.cell_position(cell))
    def cell_position(self,cell):
        index=next(i for i,c in enumerate(self.cells) if c is cell); return [index%self.size,index//self.size]
    def interception(self,owner,target,tier=1):
        state=self.state(owner); defenses=[]; radar=False
        for p in self.positions(owner):
            c=self.cell(p); info=BUILDINGS.get(c.building,{})
            distance=abs(p[0]-target[0])+abs(p[1]-target[1]); active=self.operating(state,p)
            if info.get('service')=='radar' and distance<=5 and active>=.5: radar=True
            if info.get('intercept') and distance<=info['radius'] and active>=.5: defenses.append(info['intercept']*active)
        for u in self.units:
            info=UNITS.get(u['type'],{})
            if u['owner']==owner and info.get('intercept') and abs(u['cell'][0]-target[0])+abs(u['cell'][1]-target[1])<=info['radius']: defenses.append(info['intercept']*u.get('supply_ratio',1))
        return min(95,max(defenses,default=0)+(10 if radar and defenses else 0))

    def damage_tile(self,state,p,damage,strategic=False):
        cell=self.cell(p); owner=cell.owner
        if not owner or owner==state.id and not strategic: return
        unit=self.unit_at(p)
        if unit:
            unit['strength']=round(unit['strength']-max(1,damage-self.defense_armor(cell,unit))/self.strength_factor(unit),4)
            if unit['strength']<=0: self.remove_unit(unit)
        if cell.building:
            if self.wall_hitpoints(cell):
                cell.wall_hp=max(0,self.wall_hitpoints(cell)-damage)
                if cell.wall_hp<=0: cell.building=None; cell.building_level=0; cell.wall_hp=None
            else:
                cell.integrity=max(0,cell.integrity-damage/5)
                if cell.integrity<=0: cell.building=None; cell.building_level=0
        defender=self.state(owner); sheltered=any(BUILDINGS.get(self.cell(q).building,{}).get('service')=='shelter' and self.operating(defender,q)>=.5 and abs(q[0]-p[0])+abs(q[1]-p[1])<=2 for q in self.positions(owner))
        fraction=min(.4,damage/4000)*(.5 if 'civil_defense' in defender.tech else 1)*(.5 if sheltered else 1)
        casualties=min(cell.population,math.ceil(cell.population*fraction)); cell.population-=casualties
        if strategic: cell.radiation=min(100,cell.radiation+25)
        defender.modern['unrest']=min(100,defender.modern.get('unrest',0)+5)
        self.log('strike',f'{state.name}: удар по {p}, урон {damage:g}, потери жителей {casualties}; захвата территории нет.')

    def ranged_action(self,state,kind,args):
        target=args.get('target_cell'); cell=self.cell(target)
        if cell.owner in (None,state.id): raise RuleError('Цель — клетка другого государства')
        permission=self.war_permission(state.id,cell.owner)
        if permission: raise RuleError(permission)
        if kind=='bombard':
            unit=next((u for u in self.units if u['id']==args.get('unit_id') and u['owner']==state.id),None)
            info=UNITS.get(unit['type'],{}) if unit else {}
            if not info.get('range') or unit.get('embarked_on'): raise RuleError('Нужно своё дальнобойное формирование вне транспорта')
            if unit.get('fired_day')==self.day or self.remaining_moves(unit)<1: raise RuleError('За день одна дистанционная атака, нужен оставшийся шаг')
            distance=sum(abs(a-b) for a,b in zip(unit['cell'],target))
            if not 1<=distance<=info['range']: raise RuleError('Цель вне игровой дальности')
            self.pay_cost(state,dict(money=200,**{info['weapon']:10})); unit['fired_day']=self.day
            if unit.get('moves_day')!=self.day: unit['moves_day']=self.day; unit['moves_used']=0
            unit['moves_used']+=1; damage=self.effective_strength(unit)*.6
            if unit['type']=='drone_swarm': damage*=1-self.interception(cell.owner,target)/100
            self.set_war(state.id,cell.owner,'Дистанционная атака',attack=True); self.damage_tile(state,target,damage)
            return f'Дистанционный удар #{unit["id"]}, урон {damage:g}'
        source=args.get('cell'); silo=self.cell(source); missile=args.get('missile'); info=MISSILES.get(missile)
        if not info or info['tech'] not in state.tech: raise RuleError('Ракетная технология не открыта')
        if silo.owner!=state.id or silo.building!='missile_silo' or self.operating(state,source)<.5: raise RuleError('Нужна своя снабжаемая ракетная шахта')
        if silo.last_fired_day==self.day: raise RuleError('Шахта уже выполнила пуск сегодня')
        if not 1<=sum(abs(a-b) for a,b in zip(source,target))<=info['range']: raise RuleError('Цель вне игровой дальности')
        affected=[target]+(self.adjacent(target) if info['area'] else [])
        owners={self.cell(p).owner for p in affected}-{None,state.id}
        for owner in owners:
            permission=self.war_permission(state.id,owner)
            if permission: raise RuleError('Зона поражения затронет защищённого договором участника: '+permission)
        self.pay_cost(state,{missile:1,'money':1200,'electricity':150,'fuel':50}); silo.last_fired_day=self.day
        for owner in sorted(owners): self.set_war(state.id,owner,'Ракетный удар / зона поражения',attack=True)
        nonce=state.modern.get('strike_nonce',0); state.modern['strike_nonce']=nonce+1
        chance=max(0,self.interception(cell.owner,target)-info['penetration'])
        intercepted=random.Random(f'{self.seed}:{self.day}:{state.id}:{nonce}:{target}').randrange(100)<chance
        if intercepted: self.log('strike',f'{state.name}: ракета {missile} перехвачена над {target}.'); return 'Ракета перехвачена; ресурс и стоимость пуска потрачены'
        self.damage_tile(state,target,info['damage'],info['area']>0)
        if info['area']:
            for p in self.adjacent(target): self.damage_tile(state,p,info['damage']*.4,True)
        return f'Ракетный удар {missile} по {target}; территория не захвачена'

    def large_migration(self,state,args):
        partner=self.state(args.get('partner')); positions=self.positions(state.id)
        anchor=self.cell(args.get('cell',positions[0] if positions else None))
        if anchor.owner!=state.id or partner.id==state.id or partner.eliminated or partner.id not in self.neighbors(state.id): raise RuleError('Нужны своя клетка и другой соседний получатель')
        amount=integer(args.get('amount'),1,2000,'Переселенцы')
        population=sum(self.cell(p).population for p in self.positions(state.id))
        free=sum(max(0,self.population_capacity(partner,self.cell(p))-self.cell(p).population) for p in self.positions(partner.id))
        if population<amount or free<amount: raise RuleError('Недостаточно жителей или вместимости у получателя')
        self.pay_cost(state,dict(money=50+amount*2)); left=amount
        for p in self.positions(state.id):
            c=self.cell(p); take=min(left,c.population); c.population-=take; left-=take
            if not left: break
        self.place_people(partner,amount)
        return f'Переселено {amount} граждан без потери остальных жителей городов'

    def modern_action(self,state,kind,args):
        key=args.get('building',args.get('type'))
        if kind=='migrate' and (self.era_for(state)==2 or any(self.cell(p).population>1 for p in self.positions(state.id))): return self.large_migration(state,args)
        if kind=='research' and args.get('tech') in TECHNOLOGIES: return self.modern_research(state,args['tech'],self.cell(args.get('cell')))
        if kind=='improve_building' and self.cell(args.get('cell')).building in BUILDINGS:
            cell=self.cell(args['cell']); info=BUILDINGS[cell.building]
            if self.era_for(state)<2 or cell.owner!=state.id or info['tech'] not in state.tech: raise RuleError('Нужны собственная эпоха II, здание и его технология')
            if cell.building_level>=info['max_level']: raise RuleError('Промышленный предел уровня достигнут')
            self.pay_cost(state,{k:v*(cell.building_level+1) for k,v in info['cost'].items()})
            if info.get('barrier'): cell.wall_hp=self.wall_hitpoints(cell)+info['barrier']
            cell.building_level+=1; return f'Промышленное улучшение: уровень {cell.building_level}, прежние повреждения сохранены'
        modern_build=kind=='build' and key in BUILDINGS
        if kind not in NEW_ACTIONS and not modern_build: return None
        if self.era_for(state)<2: raise RuleError('Требуется собственная эпоха II')
        if modern_build: return self.modern_build(state,args)
        if kind in ('supply_pact','accept_supply','cancel_supply'): return self.supply_action(state,kind,args)
        if kind=='edict': return self.edict(state,args)
        if kind=='recruit_modern': return self.recruit_modern(state,args)
        if kind in ('bombard','missile_strike'): return self.ranged_action(state,kind,args)
        if kind in ('borrow','repay'):
            if 'fiscal_stability' not in state.tech: raise RuleError('Нужно fiscal_stability')
            amount=integer(args.get('amount'),100,100000,'Сумма'); debt=state.modern.get('debt',0)
            if kind=='borrow':
                ceiling=max(20000,sum(self.cell(p).population for p in self.positions(state.id))*50)
                if debt+amount>ceiling: raise RuleError('Лимит государственного кредита исчерпан')
                state.modern['debt']=debt+amount; state.stocks['money']+=amount
            else:
                if amount>debt: raise RuleError('Нельзя погасить больше суммы долга')
                self.pay_cost(state,dict(money=amount)); state.modern['debt']=debt-amount
            return f'{kind}: {amount}; ставка 2%/день, обслуживание до 4% долга/день'
        cell=self.cell(args.get('cell'))
        if cell.owner!=state.id: raise RuleError('Нужна своя клетка')
        if kind=='factory_policy':
            if cell.building not in BUILDINGS: raise RuleError('Нужно современное предприятие')
            enabled=args.get('enabled',cell.factory_enabled); priority=args.get('priority',cell.factory_priority)
            if type(enabled) is not bool: raise RuleError('enabled: true/false')
            if priority is not None: integer(priority,0,100,'Приоритет')
            cell.factory_enabled=enabled; cell.factory_priority=priority
            return 'Производственная политика обновлена; остановленный завод не расходует входы'
        if kind=='repair_building':
            if cell.building not in BUILDINGS: raise RuleError('Нужно современное здание')
            maximum=BUILDINGS[cell.building].get('barrier',0)*cell.building_level
            missing=max(100-cell.integrity,100*(maximum-self.wall_hitpoints(cell))/maximum if maximum else 0)
            amount=args.get('amount',min(25,missing))
            if type(amount) not in (int,float) or not math.isfinite(amount) or not .01<=amount<=missing+1e-8: raise RuleError('Ремонт: положительный процент, не больше повреждений')
            self.pay_cost(state,dict(money=amount*30,steel=amount,concrete=amount*2)); cell.integrity=min(100,cell.integrity+amount)
            if maximum: cell.wall_hp=min(maximum,self.wall_hitpoints(cell)+maximum*amount/100)
            return 'Здание отремонтировано'
        if kind=='remediate':
            if 'environmental_recovery' not in state.tech or cell.radiation<=0 or cell.building in ('radiation_station','radiation_test_range'): raise RuleError('Нужны технология очистки, загрязнение и снос активного полигона/станции')
            self.pay_cost(state,dict(money=6000,medicine=100,chemicals=100,machinery=50)); cell.radiation=max(0,cell.radiation-25); return 'Загрязнение снижено на 25'
        if not cell.building: raise RuleError('Нет здания для сноса')
        self.pay_cost(state,dict(money=500)); cell.building=None; cell.building_level=0; cell.wall_hp=None; cell.integrity=100
        return 'Здание снесено; жители и загрязнение сохранены, проверьте вместимость и эвакуацию'

    def modern_catalog(self,state):
        rows=[]
        for key,info in TECHNOLOGIES.items():
            if self.era_for(state)<2 and key!='industrialization': continue
            row=copy.deepcopy(info); row.update(researched=key in state.tech,available=key not in state.tech and all(t in state.tech for t in info['requires']),affordable=all(state.stocks.get(k,0)>=v for k,v in info['cost'].items()))
            if info['site'] and not any(self.cell(p).building==info['site'] and self.cell(p).radiation>0 for p in self.positions(state.id)): row['available']=False
            rows.append(row)
        return rows

    @read_analysis
    def modern_construction(self,state):
        if self.era_for(state)<2: return []
        projects=[]; forecast=self.economic_forecast(state); own=self.positions(state.id)
        for key,info in BUILDINGS.items():
            if info['tech'] not in state.tech: continue
            sites=[p for p in own if self.cell(p).terrain!='water' and (self.cell(p).building=='radiation_test_range' and self.cell(p).radiation>0 if key=='radiation_station' else self.cell(p).building is None) and (not info.get('terrain') or self.cell(p).terrain in info['terrain']) and (not self.cell(p).radiation or info.get('radioactive')) and (key!='radiation_test_range' or not self.cell(p).population)]
            if not sites: continue
            sites.sort(key=lambda p:(-self.cell(p).population if info['capacity']>20 else self.cell(p).population,p[1],p[0]))
            p=sites[0]; cost=info['cost']; priority=info['priority']
            if any(forecast['resources'][k]['status'] in ('critical','deficit','bottleneck') for k in info['outputs']): priority+=20
            projects.append(dict(project_id=f'{state.id}/{key}/{p[0]}:{p[1]}/L1',building=key,name=info['name'],cell=list(p),level=1,cost=cost,affordable_with_reserve=all(state.stocks.get(k,0)>=v+(forecast['resources'][k]['reserve'] if k in ('money','food','resource') else 0) for k,v in cost.items()),priority=priority,daily_gain=info['outputs'],daily_inputs=info['inputs'],required_workers=info['workers'],capacity=info['capacity'],population=self.cell(p).population,other_legal_sites=sites[1:4],money_payback_days=None,effect=f'Эпоха II · рабочих {info["workers"]}; вместимость {info["capacity"]}; нужны все входы и своя технология'))
        return projects

    def modern_context(self,state):
        transition=copy.deepcopy(TECHNOLOGIES['industrialization'])
        if self.era_for(state)<2:
            return dict(era=1,transition=transition,missing_prerequisites=[t for t in transition['requires'] if t not in state.tech],cost_gap={k:max(0,v-state.stocks.get(k,0)) for k,v in transition['cost'].items()},goal='Не отставай: современные корпуса во много раз сильнее старых армий. Развивай лаборатории и арсеналы, накопи стоимость собственного перехода; чужая эпоха тебя не переводит.')
        own=self.positions(state.id); plan=self.industrial_plan(state)
        return dict(era=2,resource_names=RESOURCE_NAMES,workforce=plan['workforce'],idle_workers=plan['idle_workers'],housing_capacity=sum(self.population_capacity(state,self.cell(p)) for p in own),population=plan['population'],debt=state.modern.get('debt',0),contract_claims=copy.deepcopy(state.modern.get('claims',[])),unrest=state.modern.get('unrest',0),last_crisis=copy.deepcopy(state.modern.get('last_report',{})),buildings_catalog=copy.deepcopy(BUILDINGS),units_catalog=copy.deepcopy(UNITS),missiles_catalog=copy.deepcopy(MISSILES),supply_pacts=self.supply_context(state),
                    demography=self.population_status(state),rules='Пассивный рост +10% в день с накоплением дроби; нужны жилые места. При нуле жителей доступны платные settle и population_campaign (последний требует urban_planning), прежнее население для них в эпохе II не требуется. Рабочих 55% граждан, один гражданин не работает на двух заводах; нужны все штатные рабочие. Входы расходуются ежедневно, нехватка снижает выпуск. Сначала добыча/вода, энергия, материалы, затем оружие. Указы требуют жильё и огромные реальные запасы. Труд дорог, экипаж уходит из гражданской экономики. Пакты оплачиваются ежедневно до дохода; срыв даёт штраф и долг. Полигон загрязняет ровно свою клетку, станция заменяет полигон на ней. Ракетная дальность — условные клетки игры. Не путай строительство промышленности с её снабжением.')
