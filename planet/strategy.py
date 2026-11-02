from .performance import memo_analysis
"""Public strategic balance, explicit surrender and persistent defeat."""
from .rules import RuleError


class Strategy:
    @memo_analysis
    def strategic_context(self,state):
        ranking=[]
        for other in self.states:
            owned=self.positions(other.id); units=[u for u in self.units if u['owner']==other.id]
            population=sum(self.cell(p).population for p in owned)
            strength=sum(self.effective_strength(u) for u in units)
            production=self.production_summary(other)
            economic_capacity=round(max(0,sum(production[key] for key in ('food','resource','metal','science','matter'))/5+production['money']/20),1)
            ranking.append(dict(state=other.id,name=other.name,territory=len(owned),population=population,
                                military_strength=strength,units=len(units),eliminated=other.eliminated,vassal_of=other.vassal_of,
                                economic_capacity=economic_capacity,score=len(owned)+population*3+strength*2+len(other.tech)*5+economic_capacity))
        base_scores={row['state']:row['score'] for row in ranking}
        for row in ranking:
            influence=round(sum(base_scores.get(t['subject'],0)*.25 for t in self.vassal_treaties if t['lord']==row['state'] and t['status']=='active'),1)
            dependence=round(row['score']*.15,1) if row['vassal_of'] else 0
            row.update(base_score=row['score'],political_influence=influence,dependence_penalty=dependence,score=round(row['score']+influence-dependence,1))
        ranking.sort(key=lambda row:(not row['eliminated'],row['score']),reverse=True)
        borders={}
        for p in self.positions(state.id):
            for q in self.adjacent(p):
                cell=self.cell(q)
                if cell.owner and cell.owner!=state.id and cell.terrain!='water':
                    borders.setdefault(cell.owner,[])
                    if q not in [item['cell'] for item in borders[cell.owner]] and len(borders[cell.owner])<16:
                        unit=self.unit_at(q)
                        borders[cell.owner].append(dict(cell=q,terrain=cell.terrain,building=cell.building,population=cell.population,
                                                       defender_strength=self.effective_strength(unit) if unit else 0,fortification=self.defense_armor(cell,unit),wall_hp=self.wall_hitpoints(cell)))
        return dict(ranking=ranking,border_targets=borders,
                    surrender_demands=[d for d in self.surrender_demands if state.id in (d['sender'],d['recipient']) and d['status']=='open'],
                    goal='Стать первым по развитию и силе. При общей границе сравни выгодную войну, захват источников дохода и экономическое давление с мирным ростом. Уничтожение государства означает ликвидацию его власти в игре, а не обязательную гибель населения.')

    def eliminate_state(self,loser,winner=None,surrender=False):
        if loser.eliminated: return
        for contract in self.vassal_treaties:
            if contract['status']=='active' and loser.id in (contract['lord'],contract['subject']): self.end_vassal_contract(contract,'ended_defeat')
        for offer in self.vassal_offers:
            if loser.id in (offer['lord'],offer['subject']) and offer['status']=='open': offer['status']='closed_defeat'
        loser.eliminated=True; loser.defeated_by=winner.id if winner else None
        for cell in self.cells:
            if cell.owner==loser.id and cell.terrain=='water':cell.owner=None
        loser.allies=[]
        for state in self.states: state.allies=[sid for sid in state.allies if sid!=loser.id]
        self.wars=[pair for pair in self.wars if loser.id not in pair]
        for offer in self.trade_offers:
            if loser.id in (offer['seller'],offer['partner']) and offer['status']=='open': offer['status']='cancelled_defeat'
        for pact in self.supply_pacts:
            if loser.id in (pact['seller'],pact['partner']) and pact['status'] in ('open','active'): pact['status']='closed_defeat'
        for deal in self.exchanges:
            if loser.id in (deal['seller'],deal['partner']) and deal['status'] in ('open','awaiting_delivery'): deal.update(status='closed_defeat',resolved_day=self.day)
        for demand in self.surrender_demands:
            if loser.id in (demand['sender'],demand['recipient']) and demand['status']=='open': demand['status']='closed'
        self.log('defeat',f'{loser.name}: '+('капитуляция перед '+winner.name if surrender and winner else 'государство ликвидировано: нет территории и юнитов')+'. История и характер сохранены.')

    def check_eliminations(self):
        for state in self.states:
            if not state.eliminated and not any(self.cell(p).terrain!='water' for p in self.positions(state.id)) and not any(u['owner']==state.id for u in self.units):
                self.eliminate_state(state)

    def surrender_action(self,state,kind,args):
        partner=self.state(args.get('partner'))
        if partner.id==state.id or partner.eliminated or not self.at_war(state.id,partner.id): raise RuleError('Капитуляция возможна только между действующими противниками в войне')
        if kind=='demand_surrender':
            reason=args.get('reason')
            if not isinstance(reason,str) or len(reason.strip())<8: raise RuleError('Нужно обоснование требования капитуляции')
            if any(d['sender']==state.id and d['recipient']==partner.id and d['status']=='open' for d in self.surrender_demands): raise RuleError('Требование уже передано')
            self.surrender_demands.append(dict(sender=state.id,recipient=partner.id,day=self.day,reason=reason,status='open'))
            self.relation_fact(partner.id,state.id,'ultimatum','Потребована полная капитуляция: '+reason,-10)
            return f'Требование капитуляции {partner.name}; без его действия surrender передача владений не происходит'
        # Only the losing state's own decision can authorise complete annexation.
        for cell in self.cells:
            if cell.owner==state.id: cell.owner=partner.id
        for unit in self.units:
            if unit['owner']==state.id: unit['owner']=partner.id; unit['order']=dict(kind='hold',issued_day=self.day)
        loot={key:value for key,value in state.stocks.items() if value>0}
        if loot: self.move_bundle(state,partner,loot,'surrender',credit_promises=False)
        self.relation_fact(partner.id,state.id,'surrender','Принята полная капитуляция; территория, население, здания, запасы и юниты переданы')
        self.eliminate_state(state,partner,True)
        return f'{state.name} капитулировал перед {partner.name}'
