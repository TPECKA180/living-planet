from .performance import memo_analysis
"""Deterministic forecasts: production, upkeep and explicitly uncertain orders."""
import math
from .mobility import SPEED,STEP_COST,UNIT_COST,METAL_PER_STRENGTH

RESOURCES=('food','resource','metal','science','matter','money')
TILE_OUTPUT={'grass':'food','forest':'resource','mountain':'metal','science':'science','resource':'resource'}
BUILDING_OUTPUT={'lab':'science','mine':'metal','tavern':'money','castle':'money','arsenal':'matter'}


class Economy:
    @memo_analysis
    def economic_forecast(self,state):
        if self.era_for(state)==2: return self.modern_forecast(state)
        gross={key:0.0 for key in RESOURCES}; upkeep={key:0.0 for key in RESOURCES}
        population=0
        for pos in self.positions(state.id):
            cell=self.cell(pos); population+=cell.population
            for key,value in self.production_for_cell(state,cell).items(): gross[key]+=value
        for key,value in self.citizen_upkeep(state).items(): upkeep[key]=population*value
        tribute=self.tribute_forecast().get(state.id,0)
        gross['money']+=max(0,tribute); upkeep['money']+=max(0,-tribute)
        base={key:round(gross[key]-upkeep[key],2) for key in RESOURCES}
        # A dry-run of the same paid service, without changing the real world.
        # It is an estimate: new LLM orders, conflicts and crises are unknown.
        expected={key:0.0 for key in RESOURCES}
        moved_units=0
        for unit in self.units:
            if unit['owner']!=state.id or unit.get('embarked_on'): continue
            order=unit.get('order') or {}
            exploratory=order.get('kind')=='explore' or not order and unit['type']=='scout' and state.operations.get('explore',True)
            if order.get('kind')=='hold' or not exploratory and order.get('kind')!='move': continue
            route=self.find_route(unit,order.get('target'),exploratory)
            if not route: continue
            steps=min(self.speed_for(state,unit['type']),len(route)) if not exploratory else self.speed_for(state,unit['type'])
            expected['money']+=steps*STEP_COST; moved_units+=1
        wanted=min(state.operations.get('unit_limit',8),max(3,2+len(self.positions(state.id))//20))
        units=sum(u['owner']==state.id for u in self.units)
        wartime=any(self.at_war(state.id,peer.id) for peer in self.states if peer.id!=state.id and not peer.eliminated)
        recruit_possible=(not wartime and state.operations.get('recruit',True) and units<wanted and state.stocks['money']+base['money']>=self.unit_price(state)+state.operations.get('reserve_money',30) and
                          state.stocks['metal']+base['metal']>=METAL_PER_STRENGTH*3 and self.exploration_recruitment_sites(state))
        if recruit_possible: expected['money']+=self.unit_price(state)+self.speed_for(state,'scout')*STEP_COST; expected['metal']+=METAL_PER_STRENGTH*3
        net={key:round(base[key]-expected[key],2) for key in RESOURCES}
        reserves=dict(food=upkeep['food']*3,resource=upkeep['resource']*3,metal=15,science=30,matter=20 if any(t in state.tech for t in ('military_medicine','alchemy','fortification','aether_forging')) else 0,money=max(30,state.operations.get('reserve_money',30),expected['money']*2))
        details={}
        for key in RESOURCES:
            stock=state.stocks[key]
            days=round(stock/-net[key],1) if net[key]<0 else None
            if net[key]<0 and days is not None and days<=3: status='critical'
            elif net[key]<0: status='deficit'
            elif gross[key]<1 and key not in ('matter',): status='no_production'
            elif stock<reserves[key]: status='low_reserve'
            else: status='stable'
            details[key]=dict(stock=stock,production=round(gross[key],2),upkeep=upkeep[key],
                              planned_cost=expected[key],base_net=base[key],net=net[key],reserve=reserves[key],
                              runway_days=days,status=status)
        crisis=[dict(resource=key,days=details[key]['runway_days'],status=details[key]['status'])
                for key in ('food','resource') if details[key]['status'] in ('critical','deficit','low_reserve')]
        return dict(resources=details,population=population,tribute_balance=tribute,crisis_risks=crisis,
                    basis='Оценка следующего полного дня: текущая добыча, содержание и дежурные приказы. Новые решения, атаки и события не учтены.',
                    uncertain=True,planned_mobile_units=moved_units)

    def assess_trade(self,buyer,offer,forecast=None):
        resource=offer['resource']; amount=offer['amount']; total=amount*offer['price']
        forecast=forecast or self.economic_forecast(buyer)
        item=forecast['resources'][resource]
        need='high' if item['base_net']<0 or item['stock']<item['reserve'] else 'low'
        if need=='low' and resource in ('metal','science') and item['stock']<2*max(item['reserve'],1): need='medium'
        gold=forecast['resources']['money']
        after_money=buyer.stocks['money']-total
        flags=[]
        if self.economic_block(buyer.id,offer['seller']): flags.append('Сделка заблокирована действующим эмбарго')
        if after_money<gold['reserve']: flags.append('После покупки недостаточен денежный резерв на текущую политику')
        if need=='low' and total>buyer.stocks['money']*.25: flags.append('Большая трата на ресурс, который сейчас не дефицитен')
        if offer['price']>3 and need!='high': flags.append('Высокая цена без текущего дефицита')
        relationship=self.relation(buyer.id,offer['seller'])
        political=[]
        if self.at_war(buyer.id,offer['seller']): political.append('Платёж снабжает государство, с которым идёт война')
        if relationship['trust']<-30: political.append('Низкое доверие к партнёру: не учитывай обещания как гарантированный доход')
        if relationship['trade_policy']=='avoid': political.append('В собственном досье рекомендовано избегать этого партнёра')
        return dict(offer_id=offer['id'],resource=resource,current_stock=item['stock'],production=item['production'],
                    upkeep=item['upkeep'],net_per_day=item['net'],need=need,quantity=amount,unit_price=offer['price'],total=total,
                    stock_after=item['stock']+amount,money_after=after_money,
                    recommendation='avoid' if flags or political and need=='low' else 'useful' if need=='high' else 'optional',risk_flags=flags,
                    partner_trust=relationship['trust'],political_considerations=political,
                    warning='Обещания партнёра не являются гарантированным доходом. Сравни собственный дефицит, цену и альтернативы.')

    def export_risk(self,state,resource,amount):
        if resource not in ('food','resource','money') and self.era_for(state)<2: return None
        item=self.economic_forecast(state)['resources'][resource]
        left=state.stocks[resource]-amount
        if resource=='money':
            return 'Передача лишает государство денежного резерва' if left<item['reserve'] else None
        if item['base_net']<0 and left<item['upkeep']*2:
            return 'Продажа критического запаса при отрицательном балансе может вызвать голод' 
        return None
