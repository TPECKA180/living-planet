"""Useful construction proposals, full-day tower training and persistent walls."""
import math
from .performance import read_analysis,mutation
from .rules import RuleError
from .modern_catalog import BUILDINGS as MODERN_BUILDINGS,UNITS

BUILDING_OUTPUT={'lab':'science','mine':'metal','castle':'money','tavern':'money','arsenal':'matter'}
BUILDING_NAMES=dict(lab='Лаборатория',mine='Шахта',castle='Замок',tavern='Таверна',arsenal='Арсенал',tower='Башня',wall='Стена')


class Infrastructure:
    def construction_cost(self,state,level):
        return dict(money=160 if 'engineering' in state.tech else 200,resource=(15 if 'masonry' in state.tech else 20)*level)

    def tower_bonus(self,unit):
        buff=unit.get('tower_buff') or {}
        return buff.get('percent',0) if buff.get('starts_day',0)<=self.day<=buff.get('expires_day',-1) else 0

    def combat_unit(self,unit): return unit['type']=='army' or unit['type'] in UNITS

    def strength_factor(self,unit):
        if unit['type'] in UNITS and self.era_for(self.state(unit['owner']))<2: return .01
        supply=(.25+.75*unit.get('supply_ratio',1)) if unit['type'] in UNITS else 1
        return (1+self.tower_bonus(unit)/100)*supply
    def effective_strength(self,unit): return round(unit['strength']*self.strength_factor(unit),4)

    def prepare_tower_day(self):
        for unit in self.units:
            buff=unit.get('tower_buff')
            if buff and self.day>buff['expires_day']: unit['tower_buff']=None
            cell=self.cell(unit['cell'])
            unit['tower_stationing']=(dict(day=self.day,cell=list(unit['cell']),owner=unit['owner'],level=cell.building_level)
                if cell.building=='tower' and cell.owner==unit['owner'] and not unit.get('embarked_on') and unit['type']!='ship' else None)

    def finish_tower_day(self):
        for unit in self.units:
            stay=unit.get('tower_stationing'); cell=self.cell(unit['cell'])
            if unit.get('tower_last_grant_day')==self.day: continue
            if not stay or stay['day']!=self.day or stay['cell']!=unit['cell'] or stay['owner']!=unit['owner']: continue
            if cell.building!='tower' or cell.owner!=unit['owner'] or unit.get('embarked_on'): continue
            level=min(stay['level'],cell.building_level); percent=25*level
            old=unit.get('tower_buff') or {}
            if old.get('expires_day',-1)>=self.day and old.get('percent',0)>percent: continue
            unit['tower_buff']=dict(percent=percent,level=level,cell=list(unit['cell']),starts_day=self.day+1,expires_day=self.day+3)
            unit['tower_last_grant_day']=self.day
            self.log('training',f'{self.state(unit["owner"]).name}: юнит #{unit["id"]} завершил полный день в башне {level}; +{percent}% силы на дни {self.day+1}–{self.day+3}.')

    def clear_stationing(self,unit): unit['tower_stationing']=None

    def wall_hitpoints(self,cell):
        barrier=20 if cell.building=='wall' else MODERN_BUILDINGS.get(cell.building,{}).get('barrier',0)
        return max(0,cell.wall_hp if cell.wall_hp is not None else barrier*cell.building_level) if barrier else 0

    def hit_wall(self,unit,target,defender=None):
        cell=self.cell(target); damage=min(self.wall_hitpoints(cell),self.effective_strength(unit))
        cell.wall_hp=round(self.wall_hitpoints(cell)-damage,4)
        if defender:
            unit['strength']=round(unit['strength']-self.effective_strength(defender)/self.strength_factor(unit),4)
            if unit['strength']<=0: self.remove_unit(unit)
        broken=cell.wall_hp<=0
        if broken: cell.building=None; cell.building_level=0; cell.wall_hp=None
        stats=self.day_stats.setdefault(unit['owner'],{}); stats['wall_damage']=round(stats.get('wall_damage',0)+damage,4)
        self.log('siege',f'{self.state(unit["owner"]).name}: осада стены в {target}, урон {damage:g}'+(' · стена разрушена' if broken else f' · осталось {cell.wall_hp:g} прочности'))
        return broken

    @mutation
    def repair_wall(self,state,args):
        cell=self.cell(args.get('cell'))
        if cell.owner!=state.id or cell.building!='wall': raise RuleError('Нужна своя стена')
        missing=round(20*cell.building_level-self.wall_hitpoints(cell),4)
        amount=args.get('amount',min(20,missing))
        if type(amount) not in (int,float) or not math.isfinite(amount) or not 0<amount<=missing+1e-8: raise RuleError('Количество ремонта должно быть положительным и не превышать повреждения')
        money=round(amount,2); raw=round(amount*.25,2)
        if state.stocks['money']<money or state.stocks['resource']<raw: raise RuleError(f'Нужно {money:g} денег и {raw:g} сырья')
        state.stocks['money']-=money; state.stocks['resource']-=raw; cell.wall_hp=round(self.wall_hitpoints(cell)+amount,4)
        return f'Стена {args["cell"]}: восстановлено {amount:g} прочности'

    @read_analysis
    def production_summary(self,state):
        index=getattr(self,'_analysis_index',None)
        if index is not None and state.id in index.setdefault('production',{}): return dict(index['production'][state.id])
        result=dict.fromkeys(('food','resource','metal','science','matter','money'),0.0); population=0
        if self.era_for(state)==2:
            plan=self.industrial_plan(state)
            return {k:round(plan['gross'][k]-plan['inputs'][k],4) for k in plan['gross']}
        for p in self.positions(state.id):
            cell=self.cell(p); population+=cell.population
            for key,value in self.production_for_cell(state,cell).items(): result[key]+=value
        for key,value in self.citizen_upkeep(state).items(): result[key]-=value*population
        result={key:round(value,4) for key,value in result.items()}
        if index is not None: index['production'][state.id]=dict(result)
        return result

    @read_analysis
    def construction_context(self,state,forecast=None):
        forecast=forecast or self.economic_forecast(state); own=self.positions(state.id)
        empty=[p for p in own if self.cell(p).building is None and self.cell(p).terrain!='water' and not self.cell(p).radiation]
        counts={kind:sum(self.cell(p).building==kind for p in own) for kind in BUILDING_NAMES}
        reserve=forecast['resources']['money']['reserve']; raw_reserve=forecast['resources']['resource']['reserve']
        per_level=15 if 'masonry' in state.tech else 20
        max_level=min(10,max(0,int((state.stocks['resource']-raw_reserve)//per_level)))
        metal_need=forecast['resources']['metal']['net']<0 or state.stocks['metal']<30
        matter_needed=any(not t['researched'] and t['matter']>0 and all(key in state.tech for key in t['requires']) for t in self.research_catalog(state)) or any(t in state.tech for t in ('military_medicine','fortification','alchemy','aether_forging'))
        border={tuple(p) for p in own if any(self.cell(q).owner not in (None,state.id) and self.cell(q).terrain!='water' for q in self.adjacent(p))}
        hostile={tuple(p) for p in own if any(self.cell(q).owner not in (None,state.id) and self.at_war(state.id,self.cell(q).owner) and self.cell(q).terrain!='water' for q in self.adjacent(p))}
        projects=[]
        for kind in BUILDING_NAMES:
            sites=[p for p in empty if (kind!='lab' or self.cell(p).terrain=='science') and (kind!='mine' or self.cell(p).terrain in ('resource','mountain'))]
            sites.sort(key=lambda p:(not bool(self.cell(p).population) if kind in BUILDING_OUTPUT else tuple(p) not in border,self.unit_at(p) is None,p[1],p[0]))
            if kind in ('wall','tower'):
                sites.sort(key=lambda p:(tuple(p) not in hostile,tuple(p) not in border,
                    not bool(self.unit_at(p) and self.unit_at(p)['owner']==state.id and self.combat_unit(self.unit_at(p))) if kind=='tower' else False))
            if not sites: continue
            # Two realistic levels, including useful higher-level production; no automatic spending.
            levels=sorted(set([1,min(5,max_level)])) if max_level else [1]
            for level in levels:
                p=sites[0]; cost=self.construction_cost(state,level); cell=self.cell(p)
                production=dict.fromkeys(forecast['resources'],0.0)
                if kind in BUILDING_OUTPUT:
                    from .engine import Cell
                    candidate=Cell(cell.terrain,cell.level,cell.owner,kind,level,cell.population)
                    old=self.production_for_cell(state,cell); new=self.production_for_cell(state,candidate)
                    production={key:round(new[key]-old[key],4) for key in new}
                priority=100 if kind=='lab' and not counts['lab'] else 90 if kind=='arsenal' and not counts['arsenal'] and matter_needed else 75 if kind=='mine' and metal_need else 65 if kind=='lab' else 55 if kind in ('castle','tavern') else 70 if kind in ('wall','tower') and border else 30
                if kind in ('wall','tower') and tuple(p) in hostile:priority=115
                affordable=state.stocks['money']>=cost['money']+reserve and state.stocks['resource']>=cost['resource']+raw_reserve
                projects.append(dict(project_id=f'{state.id}/{kind}/{p[0]}:{p[1]}/L{level}',building=kind,name=BUILDING_NAMES[kind],cell=p,level=level,cost=cost,affordable_with_reserve=affordable,priority=priority,
                                     daily_gain=production,money_payback_days=round(cost['money']/production['money'],1) if production['money']>0 else None,
                                     population=cell.population,other_legal_sites=sites[1:4],
                                     effect=f'После полного дня: +{25*level}% силы на3 дня' if kind=='tower' else f'Преграда для чужих разведчиков/строителей; {20*level} прочности, нужна армия для осады' if kind=='wall' else 'Выход здания: полная мощность с жителем, 10% без жителя'))
        projects.extend(self.modern_construction(state))
        projects.sort(key=lambda item:(not item['affordable_with_reserve'],-item['priority'],-item['population'],-item['level']))
        recent=[r for r in self.decisions if r['state']==state.id and r['day']>=self.day-5]
        recent_builds=sum(a.get('type')=='build' for record in recent for a in record['decision'].get('actions',[]))
        successful_builds=sum(h['day']>=self.day-5 and h['text'].startswith('build ') for h in state.history)
        critical=[p for p in projects if p['affordable_with_reserve'] and p['priority']>=90]
        return dict(buildings=counts,legal_site_count=len(empty),projects=projects,build_actions_last_5_days=recent_builds,successful_builds_last_5_days=successful_builds,
                    requires_explanation=bool(critical or successful_builds==0 and any(p['affordable_with_reserve'] for p in projects)),
                    critical_projects=critical[:3],rule='Оцени строительство до заселения и исследований. Есть деньги и сырьё, но нет лаборатории/материи — это инфраструктурное узкое место. Выбери полезный проект либо объясни конкретную отсрочку; строительство не исполняется само.')
