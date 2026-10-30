"""One deterministic supply ledger used by production, crises and forecasts."""
import math,copy
from .modern_catalog import BASE_RESOURCES,MODERN_RESOURCES,RESOURCE_NAMES,BUILDINGS,UNITS,SCIENCES
from .performance import memo_analysis


class ModernEconomy:
    def era_for(self,state): return 2 if 'industrialization' in state.tech else 1
    def resource_keys(self,state): return BASE_RESOURCES+MODERN_RESOURCES if self.era_for(state)==2 else BASE_RESOURCES
    def population_capacity(self,state,cell):
        if cell.terrain=='water' or cell.radiation>0: return 0
        if self.era_for(state)==1: return max(1,cell.population) # Captured cities never silently erase their people.
        return BUILDINGS.get(cell.building,{}).get('capacity',20)
    def workforce(self,state):
        fraction=.7 if state.modern.get('mobilization_until',-1)>=self.day else .55
        return int(sum(self.cell(p).population for p in self.positions(state.id))*fraction)
    def modern_upkeep(self,state):
        factor=.75 if 'modern_logistics' in state.tech else 1
        return {u['id']:dict(food=UNITS[u['type']]['crew']*2,money=UNITS[u['type']]['money'],fuel=UNITS[u['type']]['fuel']*factor,**{UNITS[u['type']]['weapon']:max(1,UNITS[u['type']]['weapons']*.025)*factor}) for u in self.units if u['owner']==state.id and u['type'] in UNITS}

    @memo_analysis
    def industrial_plan(self,state,starting_stocks=None):
        keys=self.resource_keys(state); gross=dict.fromkeys(keys,0.0); inputs=dict.fromkeys(keys,0.0); required=dict.fromkeys(keys,0.0)
        pop=sum(self.cell(p).population for p in self.positions(state.id))
        for p in self.positions(state.id):
            for key,value in self.production_for_cell(state,self.cell(p)).items(): gross[key]+=value
        starting_stocks=state.stocks if starting_stocks is None else starting_stocks
        available={key:starting_stocks.get(key,0)+gross[key] for key in keys}
        civilian={k:pop*v for k,v in self.citizen_upkeep(state).items()}
        # Five days to connect water after transition; food/raw are never waived.
        if self.day>state.modern.get('entered_day',self.day)+5: civilian['water']=pop
        civilian.update(electricity=pop*.2,money=pop*(.75 if 'fiscal_stability' in state.tech else 1))
        labor=self.workforce(state); left=labor; buildings=[]
        sites=[p for p in self.positions(state.id) if self.cell(p).building in BUILDINGS]
        sites.sort(key=lambda p:(-self.cell(p).factory_priority if self.cell(p).factory_priority is not None else -BUILDINGS[self.cell(p).building]['priority'],p[1],p[0]))
        for p in sites:
            cell=self.cell(p); info=BUILDINGS[cell.building]; level=cell.building_level
            eligible=info['tech'] in state.tech and (cell.building!='radiation_station' or cell.radiation>0)
            enabled=cell.factory_enabled and eligible
            workers=info['workers']*level; staffed=enabled and left>=workers
            allocated=workers if staffed else 0
            if staffed: left-=workers
            ratio=cell.integrity/100 if staffed else 0.0
            needs={key:value*level*ratio for key,value in info['inputs'].items()}
            reasons=[]
            if not eligible: reasons.append('technology')
            if not cell.factory_enabled: reasons.append('mothballed')
            if enabled and not staffed: reasons.append('labor')
            for key,value in needs.items():
                required[key]+=value
                # Prevent factories from using the last civilian food/raw stock.
                usable=max(0,available.get(key,0)-civilian.get(key,0)) if key in ('food','resource') else available.get(key,0)
                if value and usable<value: reasons.append(key)
            supply=min([1.0]+[max(0,available.get(k,0)-(civilian.get(k,0) if k in ('food','resource') else 0))/v for k,v in needs.items() if v])
            utilization=max(0,min(1,ratio*supply)); actual_in={k:round(v*level*utilization,4) for k,v in info['inputs'].items()}
            outputs={}
            for key,value in info['outputs'].items():
                bonus=(1.25 if 'industrial_automation' in state.tech else 1)*(1.15 if key=='electricity' and 'electrical_grid' in state.tech else 1)*(1.25 if (key in SCIENCES or key=='science') and 'research_network' in state.tech else 1)
                stability=max(.5,1-state.modern.get('unrest',0)*.004)
                outputs[key]=round(value*level*utilization*bonus*stability,4)
            for key,value in actual_in.items(): available[key]-=value; inputs[key]+=value
            for key,value in outputs.items(): available[key]+=value; gross[key]+=value
            buildings.append(dict(cell=list(p),building=cell.building,name=info['name'],level=level,workers=workers,assigned=allocated,utilization=round(utilization,4),inputs=actual_in,outputs=outputs,bottlenecks=reasons))
        unit_supply={}
        for uid,needs in self.modern_upkeep(state).items():
            ratio=min([1.0]+[max(0,available[k]-civilian.get(k,0))/v for k,v in needs.items() if v])
            unit_supply[uid]=max(0,min(1,ratio))
            for key,value in needs.items():
                required[key]+=value; actual=value*unit_supply[uid]; available[key]-=actual; inputs[key]+=actual
        service={}
        for key,value in civilian.items():
            required[key]+=value; actual=min(max(0,available[key]),value); available[key]-=actual; inputs[key]+=actual
            service[key]=actual/value if value else 1
        debt=state.modern.get('debt',0); debt_payment=min(max(0,available['money']),debt*.04)
        available['money']-=debt_payment; inputs['money']+=debt_payment
        required['money']+=debt*.04
        # Real storage limit: electric power cannot accumulate indefinitely.
        electricity_capacity=max(1000,gross['electricity']*2); spilled=max(0,available['electricity']-electricity_capacity)
        available['electricity']-=spilled
        missing={k:round(max(0,required[k]-inputs[k]),4) for k in keys}
        return dict(population=pop,workforce=labor,assigned_workers=labor-left,idle_workers=left,buildings=buildings,gross=gross,inputs=inputs,required=required,missing=missing,civilian=service,unit_supply=unit_supply,
                    end_stocks={k:round(max(0,v),4) for k,v in available.items()},electricity_spilled=spilled,debt_payment=debt_payment)

    def modern_income(self,state):
        plan=self.industrial_plan(state); before=copy.deepcopy(state.stocks)
        state.stocks.update(plan['end_stocks']); status=state.modern
        unpaid=plan['population']*(.75 if 'fiscal_stability' in state.tech else 1)*(1-plan['civilian'].get('money',1))
        status['debt']=round(max(0,status.get('debt',0)*1.02-plan['debt_payment'])+unpaid,2)
        hardship=max(1-plan['civilian'].get('food',1),1-plan['civilian'].get('resource',1),1-plan['civilian'].get('water',1))
        deprivation=(1-plan['civilian'].get('electricity',1))*2
        health=state.stocks.get('medicine',0)>=max(1,plan['population']*.01)
        consumer=state.stocks.get('consumer_goods',0)>=max(1,plan['population']*.02)
        state.modern['unrest']=round(max(0,min(100,status.get('unrest',0)+hardship*30+deprivation*4+(0 if health else 1)+(0 if consumer else 1)+(6 if unpaid else 0)-4)),2)
        mortality=min(.12,hardship*.08+(.02 if status['unrest']>=90 else 0))
        if 'environmental_recovery' in state.tech: mortality*=.8
        if any(r['building']=='hospital' and r['utilization']>=.5 for r in plan['buildings']): mortality*=.7
        status['bankrupt']=status['debt']>max(50000,plan['population']*100)
        casualties=0
        for p in self.positions(state.id):
            cell=self.cell(p)
            if cell.population:
                overcrowding=max(0,cell.population-self.population_capacity(state,cell))
                losses=min(cell.population,math.ceil(cell.population*mortality) if mortality else 0)+min(overcrowding,max(1,math.ceil(overcrowding*.05)))
                losses=min(cell.population,losses); cell.population-=losses; casualties+=losses
        if health: state.stocks['medicine']-=plan['population']*.01
        if consumer: state.stocks['consumer_goods']-=plan['population']*.02
        for unit in list(self.units):
            if unit['owner']!=state.id: continue
            if unit['type'] in UNITS:
                unit['supply_ratio']=plan['unit_supply'].get(unit['id'],0)
                if unit['supply_ratio']<.5:
                    unit['strength']=round(unit['strength']*(.97+.03*unit['supply_ratio']),4)
                    if unit['strength']<1: self.remove_unit(unit)
        status['operating']={f'{r["cell"][0]}:{r["cell"][1]}':r['utilization'] for r in plan['buildings']}
        status['last_report']=dict(day=self.day,workforce=plan['workforce'],idle_workers=plan['idle_workers'],unrest=status['unrest'],debt=status['debt'],civilian=plan['civilian'],casualties=casualties,bottlenecks=[r for r in plan['buildings'] if r['bottlenecks']])
        if hardship or casualties or unpaid or any(r['bottlenecks'] and 'mothballed' not in r['bottlenecks'] for r in plan['buildings']):
            self.log('crisis',f'{state.name}: промышленный кризис · недовольство {status["unrest"]:g} · долг {status["debt"]:g} · потери жителей {casualties}.',visible_to=[state.id])
        self.daily_income[state.id]={k:round(state.stocks[k]-before.get(k,0),4) for k in self.resource_keys(state)}
        return plan['gross']['money']

    @memo_analysis
    def modern_forecast(self,state):
        contracts=self.project_supply(state); plan=self.industrial_plan(state,contracts['stocks']); details={}
        for key in self.resource_keys(state):
            use=max(plan['inputs'][key],plan['required'][key]); net=plan['gross'][key]-use+contracts['net'].get(key,0)
            if key in ('medicine','consumer_goods'): use+=plan['population']*(.01 if key=='medicine' else .02); net=plan['gross'][key]-use+contracts['net'].get(key,0)
            reserve=use*3 if key!='money' else max(use*3,state.operations.get('reserve_money',30),1000)
            stock=state.stocks.get(key,0); status='critical' if net<0 and stock/-net<=3 else 'deficit' if net<0 else 'bottleneck' if plan['missing'][key] else 'low_reserve' if stock<reserve else 'stable'
            details[key]=dict(stock=stock,production=round(plan['gross'][key],2),upkeep=round(use,2),planned_cost=0,base_net=round(net,2),net=round(net,2),reserve=round(reserve,2),runway_days=round(stock/-net,1) if net<0 else None,status=status,unmet_demand=plan['missing'][key],signed_pact_net=contracts['net'].get(key,0))
        tribute=self.tribute_forecast().get(state.id,0)
        details['money']['net']+=tribute; details['money']['base_net']+=tribute
        details['money']['reserve']+=contracts['daily_purchase_commitment']*3
        if any(r['debtor']==state.id for r in contracts['at_risk']): details['money']['status']='critical'
        contracts['projected_default_penalties']=sum(r['penalty'] for r in contracts['at_risk'] if r['debtor']==state.id)
        return dict(resources=details,population=plan['population'],tribute_balance=tribute,crisis_risks=[dict(resource=k,days=v['runway_days'],status=v['status']) for k,v in details.items() if v['status'] in ('critical','deficit','bottleneck')],industry=plan,signed_pacts=contracts,
                    basis='Текущие заводы по приоритету: реальные рабочие, входы, снабжение армии, население. Неподписанные сделки не считаются доходом; будущие решения и удары неизвестны.',uncertain=True,planned_mobile_units=0)
