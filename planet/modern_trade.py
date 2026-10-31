"""Recurring paid supply contracts: real delivery, default, claims and cancellation."""
import math,copy
from .rules import RuleError
from .modern_catalog import RESOURCE_NAMES


def integer(value,low,high,label):
    if type(value) is not int or not low<=value<=high: raise RuleError(f'{label}: целое {low}–{high}')
    return value


class ModernTrade:
    def check_resource_transfer(self,seller,buyer,resource):
        if resource not in RESOURCE_NAMES: raise RuleError('Неизвестный ресурс')
        if resource not in self.resource_keys(seller) or resource not in self.resource_keys(buyer): raise RuleError('Новые ресурсы доступны только странам, самостоятельно открывшим эпоху II')

    def supply_action(self,state,kind,args):
        if kind=='supply_pact':
            buyer=self.state(args.get('partner')); resource=args.get('resource'); self.check_resource_transfer(state,buyer,resource)
            if buyer.id==state.id or buyer.eliminated or self.era_for(buyer)<2: raise RuleError('Нужен другой действующий партнёр эпохи II')
            if self.economic_block(state.id,buyer.id): raise RuleError('Поставки запрещены эмбарго')
            if resource=='money': raise RuleError('Деньги являются оплатой, не предметом поставки')
            amount=integer(args.get('amount'),1,1000000,'Ежедневный объём'); duration=integer(args.get('duration',10),3,60,'Срок')
            price=args.get('price'); penalty=args.get('penalty',0)
            if type(price) not in (int,float) or not math.isfinite(price) or not .01<=price<=1000: raise RuleError('Цена за единицу: 0.01–1000')
            if type(penalty) not in (int,float) or not math.isfinite(penalty) or not 0<=penalty<=amount*price*3: raise RuleError('Штраф: от нуля до трёх дневных платежей')
            if sum(p['seller']==state.id and p['status'] in ('open','active') for p in self.supply_pacts)>=20: raise RuleError('Не более 20 открытых/действующих пактов')
            pact=dict(id=self.next_supply,seller=state.id,partner=buyer.id,resource=resource,amount=amount,price=price,duration=duration,penalty=penalty,status='open',day=self.day,expires=self.day+5,paid=0,delivered=0,defaults=0,last_day=-1,seller_reason=str(args.get('reason',''))[:2000])
            self.next_supply+=1; self.supply_pacts.append(pact)
            return f'Предложен пакт #{pact["id"]}: {amount} {resource}/день за {amount*price:g}, срок {duration}, штраф {penalty:g}'
        if type(args.get('pact_id')) is not int: raise RuleError('pact_id должен быть целым номером пакта')
        pact=next((p for p in self.supply_pacts if p['id']==args.get('pact_id')),None)
        if not pact or state.id not in (pact['seller'],pact['partner']): raise RuleError('Нет своего пакта')
        if kind=='accept_supply':
            if state.id!=pact['partner'] or pact['status']!='open' or pact['expires']<self.day: raise RuleError('Пакт недоступен для принятия')
            if self.economic_block(pact['seller'],state.id): raise RuleError('Эмбарго')
            item=self.economic_forecast(state)['resources'][pact['resource']]; daily=pact['amount']*pact['price']
            risk=daily>state.stocks['money']*.25 or item['base_net']>=0 and item['stock']>=item['reserve'] or daily>max(0,self.economic_forecast(state)['resources']['money']['base_net'])
            if risk and not (args.get('allow_risk') is True and isinstance(args.get('reason'),str) and len(args['reason'].strip())>=12): raise RuleError('Дорогой/избыточный пакт: нужны осознанные allow_risk=true и reason, сравните полный платёж за срок')
            pact.update(status='active',starts_day=self.day+1,until_day=self.day+pact['duration'],buyer_reason=str(args.get('reason',''))[:2000])
            self.relation_fact(state.id,pact['seller'],'supply_signed',f'Пакт #{pact["id"]}: {daily:g}/день, всего {daily*pact["duration"]:g}, штраф {pact["penalty"]:g}',2)
            return f'Подписан пакт #{pact["id"]}; первая поставка завтра'
        if pact['status'] not in ('open','active'): raise RuleError('Пакт уже закрыт')
        peer=pact['partner'] if state.id==pact['seller'] else pact['seller']
        if pact['status']=='active': self.contract_claim(state.id,peer,pact['penalty'],pact['id'])
        pact['status']='cancelled'; self.relation_fact(peer,state.id,'supply_cancelled',f'Пакт #{pact["id"]} расторгнут',-10)
        return f'Пакт #{pact["id"]} расторгнут, учтён договорной штраф'

    def contract_claim(self,debtor,creditor,amount,pact_id):
        if amount<=0: return
        own,peer=self.state(debtor),self.state(creditor); paid=min(own.stocks['money'],amount)
        if paid: self.move_bundle(own,peer,dict(money=paid),'contract_penalty',pact_id)
        if paid<amount: own.modern.setdefault('claims',[]).append(dict(creditor=creditor,amount=round(amount-paid,4),pact_id=pact_id))

    def process_supply(self):
        for state in self.states:
            for claim in state.modern.get('claims',[]):
                if claim.get('repudiated'): continue
                peer=self.state(claim['creditor']); paid=min(claim['amount'],state.stocks['money']*.1)
                if paid: self.move_bundle(state,peer,dict(money=paid),'contract_debt',claim['pact_id'])
                claim['amount']=round(claim['amount']-paid,4)
            if 'claims' in state.modern: state.modern['claims']=[c for c in state.modern['claims'] if c['amount']>.001]
        for pact in self.supply_pacts:
            if pact['status']=='open' and pact['expires']<self.day: pact['status']='expired'
            if pact['status']!='active' or pact.get('last_day')==self.day: continue
            if self.day>pact['until_day']: pact['status']='completed'; continue
            if self.day<pact['starts_day']: continue
            seller,buyer=self.state(pact['seller']),self.state(pact['partner']); amount=pact['amount']; resource=pact['resource']; unit=pact['price']
            pact['last_day']=self.day
            delivered,paid,fault=self.supply_terms(pact,seller.stocks,buyer.stocks,self.day)
            receipt_ids=[]
            if delivered:
                receipt_ids=[self.move_bundle(seller,buyer,{resource:delivered},'supply_delivery',pact['id']),self.move_bundle(buyer,seller,dict(money=paid),'supply_payment',pact['id'])]
            pact['paid']+=paid; pact['delivered']+=delivered; pact['last_delivery']=dict(day=self.day,amount=delivered,paid=paid,receipt_ids=receipt_ids)
            if delivered: self.record_trade_statistics(seller,buyer,resource,delivered,paid)
            if delivered<amount:
                pact['defaults']+=1
                debtor,creditor=(seller,buyer) if fault==seller.id else (buyer,seller)
                self.contract_claim(debtor.id,creditor.id,pact['penalty'],pact['id'])
                self.relation_fact(creditor.id,debtor.id,'supply_default',f'Срыв пакта #{pact["id"]}: {delivered}/{amount}; штраф {pact["penalty"]:g}',-12)
                self.log('crisis',f'Срыв пакта #{pact["id"]}: {seller.name} → {buyer.name}, поставлено {delivered}/{amount}; договорные потери {pact["penalty"]:g}.',visible_to=[seller.id,buyer.id])

    def supply_context(self,state):
        result=[]
        for p in self.supply_pacts:
            if state.id not in (p['seller'],p['partner']): continue
            row=self.visible_trade_offer(state,p); daily=p['amount']*p['price']
            row.update(daily_payment=daily,total_commitment=daily*p['duration'],remaining_days=max(0,p.get('until_day',self.day+p['duration'])-self.day),warning='Не гарантированный доход: проверь резервы, снабжение, штраф, эмбарго, долг и зависимость от поставщика.')
            result.append(row)
        return copy.deepcopy(result)

    def project_supply(self,state):
        """Own treasury is known; counterparties' future cooperation is a conditional assumption."""
        cache=getattr(self,'_analysis_index',None)
        projections=cache.setdefault('supply_projections',{}) if cache is not None else {}
        projection=projections.get(state.id)
        if projection is None:
            balances={s.id:dict(s.stocks) if s.id==state.id else {k:10**12 for k in s.stocks} for s in self.states}; risk={s.id:[] for s in self.states}; obligation={s.id:0.0 for s in self.states}; day=self.day+1
            for s in self.states:
                for claim in s.modern.get('claims',[]):
                    if s.id!=state.id and claim['creditor']!=state.id: continue
                    if claim.get('repudiated'): continue
                    paid=min(claim['amount'],balances[s.id]['money']*.1); balances[s.id]['money']-=paid; balances[claim['creditor']]['money']+=paid
            for p in self.supply_pacts:
                if p['status']!='active' or not p['starts_day']<=day<=p['until_day']: continue
                seller,buyer=self.state(p['seller']),self.state(p['partner']); sb,bb=balances[seller.id],balances[buyer.id]; key=p['resource']; amount=p['amount']; price=p['price']
                obligation[buyer.id]+=amount*price
                delivery,paid,fault=self.supply_terms(p,sb,bb,day,observer=state.id)
                sb[key]-=delivery; bb[key]+=delivery; sb['money']+=paid; bb['money']-=paid
                if delivery<amount:
                    creditor=buyer.id if fault==seller.id else seller.id
                    paid=min(balances[fault]['money'],p['penalty']); balances[fault]['money']-=paid; balances[creditor]['money']+=paid
                    row=dict(pact_id=p['id'],expected_delivery=delivery,contracted=amount,penalty=p['penalty'],debtor=fault)
                    risk[seller.id].append(row); risk[buyer.id].append(row)
            projection=dict(balances=balances,risk=risk,obligation=obligation)
            projections[state.id]=projection
        balances=projection['balances'][state.id]
        return dict(stocks=dict(balances),net={k:round(balances.get(k,0)-state.stocks.get(k,0),4) for k in self.resource_keys(state)},at_risk=copy.deepcopy(projection['risk'][state.id]),daily_purchase_commitment=projection['obligation'][state.id],uncertain=True,external_delivery_assumed=True,warning='Знаем свои запасы. Чужие поставки и платежи предполагаются по условиям, но могут быть сознательно сорваны; это не гарантированный доход и не доступ к чужой казне/замыслам.')

    def supply_terms(self,pact,seller_balance,buyer_balance,day,observer=None):
        seller,buyer=self.state(pact['seller']),self.state(pact['partner']); amount=pact['amount']; price=pact['price']
        withheld=pact.get('withheld',{})
        if observer is not None: withheld={observer:withheld.get(observer,-1)}
        if seller.eliminated or withheld.get(seller.id,-1)>=day or self.relation(seller.id,buyer.id)['embargo']: return 0,0,seller.id
        if buyer.eliminated or withheld.get(buyer.id,-1)>=day or self.relation(buyer.id,seller.id)['embargo']: return 0,0,buyer.id
        available=max(0,int(seller_balance.get(pact['resource'],0))); affordable=max(0,int((buyer_balance['money']+1e-8)/price))
        delivered=min(amount,available,affordable)
        fault=seller.id if available<amount and available<=affordable else buyer.id if delivered<amount else None
        return delivered,round(delivered*price,4),fault
