"""Checkable strategic evidence, not invented hidden reasoning or enemy budgets."""
import math
from .performance import read_analysis
from .military_ai import MilitaryPlanning


class Planning(MilitaryPlanning):
    @read_analysis
    def legal_action_sites(self,state):
        own=self.positions(state.id); modern=self.era_for(state)==2
        labs=[p for p in own if self.cell(p).integrity>0 and (self.cell(p).building=='lab' and self.cell(p).terrain=='science' or modern and self.cell(p).building in ('university','engineering_institute','physics_lab','computing_center','radiation_station'))]
        research=[t['id'] for t in self.research_catalog(state) if labs and t['available'] and all(state.stocks.get(k,0)>=v for k,v in t.get('cost',{k:t[k] for k in ('money','science','matter')}).items())]
        return dict(research_cells=labs,affordable_research=research,settlement_cells=[p for p in own if not self.cell(p).population and self.cell(p).terrain!='water' and not self.cell(p).radiation][:24],
                    rule='research: бери свою реальную научную клетку и ещё не изученную доступную технологию; settle: стартовая клетка без жителя. Деньги/ресурсы всё равно проверяются при исполнении.')

    @read_analysis
    def decision_brief(self,state,forecast=None):
        forecast=forecast or self.economic_forecast(state)
        strategy=self.strategic_context(state); own=self.positions(state.id)
        units=[u for u in self.units if u['owner']==state.id and not u.get('embarked_on')]
        by_id={row['state']:row for row in strategy['ranking']}
        active=[row for row in strategy['ranking'] if not row['eliminated']]
        leader=active[0] if active else by_id[state.id]; me=by_id[state.id]
        horizon={key:dict(stock=item['stock'],net=item['net'],after_3_days=round(item['stock']+3*item['net'],2),after_7_days=round(item['stock']+7*item['net'],2),reserve=item['reserve'],status=item['status']) for key,item in forecast['resources'].items()}
        war_options=[]
        for peer,targets in strategy['border_targets'].items():
            target_state=self.state(peer)
            # Prefer high-value weakly guarded points, not arbitrary coordinate order.
            targets=sorted(targets,key=lambda t:(t['defender_strength'],not bool(t['building']),not bool(t['population'])))[:3]
            for target in targets:
                p=target['cell']; candidates=sorted((u for u in units if u['type']!='ship' and abs(u['cell'][0]-p[0])+abs(u['cell'][1]-p[1])<=10),key=lambda u:(abs(u['cell'][0]-p[0])+abs(u['cell'][1]-p[1]),-u['strength']))[:2]
                options=[]
                for unit in candidates:
                    route=self.find_route(unit,p,assume_war_with=peer)
                    if route is None: continue
                    attack=self.effective_strength(unit); defense=target['defender_strength']; armor=target['fortification']
                    attacker_after=attack-defense; defender_after=defense-max(1,attack-armor) if defense else 0
                    wall_hp=target.get('wall_hp',0)
                    siege_strikes=math.ceil(wall_hp/max(attack,.0001)) if wall_hp else 0
                    price=max(0,len(route)-1)*2+22*(max(1,siege_strikes)+(1 if wall_hp and defense else 0))
                    if wall_hp:
                        attacker_after=attack-defense
                        defender_after=defense

                    gains=self.production_for_cell(state,self.cell(p))
                    cell=self.cell(p)
                    for resource,upkeep in self.citizen_upkeep(state).items(): gains[resource]-=upkeep*cell.population
                    # A lower-information baseline, not the opponent's secret technology/budget.
                    denied=dict.fromkeys(gains,0.0); output={'grass':'food','forest':'resource','mountain':'metal','science':'science','resource':'resource'}.get(cell.terrain)
                    if output: denied[output]+=cell.level
                    denied['money']=4+cell.population
                    if cell.building in ('lab','mine','castle','tavern','arsenal'):
                        output={'lab':'science','mine':'metal','castle':'money','tavern':'money','arsenal':'matter'}[cell.building]
                        denied[output]+=10*cell.building_level*(1 if cell.population else .1)
                    denied['food']-=2*cell.population; denied['resource']-=cell.population
                    swing={key:round(gains[key]+denied[key],2) for key in gains}
                    warnings=[]
                    if wall_hp: warnings.append('Стена: нужна осада, указан минимум ударов без учёта снижения силы от гарнизона')
                    if unit.get('tower_buff') and unit['tower_buff']['expires_day']<self.day+(len(route)-1)//self.speed_for(state,unit['type']): warnings.append('Бонус башни может закончиться до прибытия')
                    if target_state.vassal_of: warnings.append('В войну вступит сюзерен '+target_state.vassal_of)
                    if state.vassal_of: warnings.append('Самостоятельная наступательная война ограничена вассальным договором')
                    if peer in state.allies: warnings.append('Для реального нападения сначала declare_war разрывает союз')
                    if any(item['status']=='critical' for key,item in forecast['resources'].items() if key in ('food','resource')): warnings.append('Собственный критический дефицит снабжения')
                    if by_id[peer]['military_strength']>me['military_strength']: warnings.append('Суммарная сила противника больше собственной; локальная победа не гарантирует выигрыш войны')
                    if price>state.stocks['money']-forecast['resources']['money']['reserve']: warnings.append('Операция расходует денежный резерв')
                    options.append(dict(partner=peer,unit_id=unit['id'],target=p,path=route,minimum_cost=price,minimum_days=(len(route)+self.speed_for(state,unit['type'])-1)//self.speed_for(state,unit['type']),
                                        defender_strength=defense,fortification=armor,attacker_after_first_exchange=max(0,attacker_after),defender_after_first_exchange=max(0,defender_after),
                                        captures_on_first_exchange=attacker_after>0 and defender_after<=0 and wall_hp<=attack,wall_hp=wall_hp,minimum_siege_strikes=siege_strikes,daily_gain_if_held=gains,money_payback_days=round(price/max(gains['money'],.01),1),
                                        relative_resource_swing=swing,relative_money_payback_days=round(price/max(swing['money'],.01),1),denial_estimate='Доход отнят у противника и добавлен нам; неизвестные бонусы его технологий не учтены',risks=warnings))
                if options: war_options.append(min(options,key=lambda o:(not o['captures_on_first_exchange'],o['minimum_cost'])))
        war_options=sorted(war_options,key=lambda o:(not o['captures_on_first_exchange'],len(o['risks']),o['minimum_cost']))[:6]
        trades=[o for o in self.trade_offers if o['status']=='accepted' and state.id in (o['seller'],o['partner']) and o.get('accepted_day',o.get('day',0)) is not None and o.get('accepted_day',o.get('day',0))>=self.day-10]
        known_exports={}
        for offer in trades:
            if offer['seller']==state.id:
                key=(offer['partner'],offer['resource']); known_exports[key]=known_exports.get(key,0)+offer['amount']
        settlements=min(10,int(state.stocks['money']//50),int(state.stocks['food']//30),int(state.stocks['resource']//10),sum(not self.cell(p).population and self.cell(p).terrain!='water' and not self.cell(p).radiation for p in own))
        if sum(self.cell(p).population for p in own)<2: settlements=0
        lab=any(self.cell(p).building=='lab' and self.cell(p).terrain=='science' for p in own)
        if self.era_for(state)==2: lab=lab or any(self.cell(p).building in ('university','engineering_institute','physics_lab','computing_center','radiation_station') for p in own)
        research=[t['id'] for t in self.research_catalog(state) if t['available'] and lab and all(state.stocks.get(key,0)>=value for key,value in t.get('cost',{key:t[key] for key in ('money','science','matter')}).items())]
        settlement_sites=sorted((p for p in own if not self.cell(p).population and self.cell(p).terrain!='water' and not self.cell(p).radiation),key=lambda p:(self.cell(p).building is None,p[1],p[0]))[:12]
        return dict(
            competition=dict(leader=leader['state'],own_score=me['score'],leader_score=leader['score'],relative_score=round(me['score']/max(leader['score'],1),2),
                             pressure='Удержать лидерство, ограничивая рост соперников' if leader['state']==state.id else 'Сократить отставание: безопасный рост не достаточен, если лидер растёт быстрее'),
            resource_horizon=horizon,war_options=war_options,affordable_settlers_now=max(0,settlements),settlement_sites=settlement_sites,researchable_now=research,
            known_export_leverage=[dict(partner=peer,resource=resource,delivered_last_10_days=amount,confidence='Известны свои поставки; полная зависимость и запасы партнёра неизвестны') for (peer,resource),amount in known_exports.items()],
            recent_execution_feedback=[dict(item) for item in state.history[-12:]],
            assessment_rule='Сравни не меньше трёх вариантов: развитие, силовое/экономическое принуждение, коалиция/вассалитет. Для каждого — выгода, риск, ответ соперника и условия отказа. Выбери выполнимые действия сегодня и цель на 3–10 дней. Публичные обещания отделяй от частной выгоды.',
            uncertainty='Горизонт запасов — сценарий неизменных условий, не предсказание. Тактика рассчитана по видимым целям и текущей силе: подкрепления, скрытые намерения и будущие события неизвестны. Ни мысли, ни точные бюджеты соперника не раскрыты.')
