"""Treasury-level transfers, traceable settlement and genuinely unsecured exchanges."""
import copy,math
from .rules import RuleError
from .performance import read_analysis

FINANCIAL_ACTIONS=('trade','accept_trade','transfer','offer_exchange','accept_exchange','deliver_exchange','breach_exchange','cancel_exchange','withhold_supply','resume_supply','repudiate_debt')
ECONOMIC_ACTIONS=FINANCIAL_ACTIONS+('pledge','supply_pact','accept_supply','cancel_supply')


class Commerce:
    def check_partner(self,state,pid):
        peer=self.state(pid)
        if peer.id==state.id or peer.eliminated: raise RuleError('Нужен другой действующий партнёр')
        if self.economic_block(state.id,peer.id): raise RuleError('Передача запрещена эмбарго')
        return peer

    def validate_bundle(self,state,peer,bundle):
        if not isinstance(bundle,dict) or not 1<=len(bundle)<=4: raise RuleError('Пакет: 1–4 разных ресурса и точные количества')
        limit=1000000 if self.era_for(state)==2 else 10000
        for key,amount in bundle.items():
            self.check_resource_transfer(state,peer,key)
            if type(amount) is not int or not 1<=amount<=limit: raise RuleError(f'Количество {key}: целое 1–{limit}')
        return dict(bundle)

    def funds_available(self,state,bundle): return all(state.stocks.get(k,0)+1e-8>=v for k,v in bundle.items())
    def require_funds(self,state,bundle):
        if not self.funds_available(state,bundle): raise RuleError('Недостаточно ресурсов для фактического перевода: '+', '.join(k for k,v in bundle.items() if state.stocks.get(k,0)<v))
    def risk_acknowledged(self,args): return args.get('allow_risk') is True and isinstance(args.get('reason'),str) and len(args['reason'].strip())>=8
    def check_export_bundle(self,state,bundle,args):
        risks=[self.export_risk(state,k,v) for k,v in bundle.items()]
        if any(risks) and not self.risk_acknowledged(args): raise RuleError('; '.join(r for r in risks if r)+'; при осознанном риске укажи allow_risk=true и reason')

    def move_bundle(self,sender,recipient,bundle,kind,reference=None,credit_promises=True):
        """Caller validates all legs first. Only existing resources move; receipt records exact deltas."""
        before={s.id:{k:s.stocks.get(k,0) for k in bundle} for s in (sender,recipient)}
        for key,value in bundle.items():
            sender.stocks[key]=round(sender.stocks.get(key,0)-value,4); recipient.stocks[key]=round(recipient.stocks.get(key,0)+value,4)
            if credit_promises: self.record_delivery(sender.id,recipient.id,key,value)
        receipt=dict(id=self.next_receipt,day=self.day,kind=kind,reference=reference,sender=sender.id,recipient=recipient.id,resources=dict(bundle),
            deltas={sender.id:{k:-v for k,v in bundle.items()},recipient.id:dict(bundle)},balances={s.id:{k:dict(before=before[s.id][k],after=s.stocks[k]) for k in bundle} for s in (sender,recipient)})
        self.next_receipt+=1; self.settlements.append(receipt)
        text=f'Квитанция #{receipt["id"]}: {sender.name} → {recipient.name}: '+', '.join(f'{k} {v:g}' for k,v in bundle.items())
        for participant in (sender,recipient): participant.history.append(dict(day=self.day,text=text))
        self.log('settlement',f'Квитанция #{receipt["id"]}: {sender.name} → {recipient.name}: '+', '.join(f'{k} {v:g}' for k,v in bundle.items()),visible_to=[sender.id,recipient.id])
        return receipt['id']

    def financial_action(self,state,kind,args):
        if kind in ('withhold_supply','resume_supply','repudiate_debt'): return self.default_action(state,kind,args)
        if kind in ('offer_exchange','accept_exchange','deliver_exchange','breach_exchange','cancel_exchange'): return self.exchange_action(state,kind,args)
        if kind=='accept_trade':
            if type(args.get('offer_id')) is not int: raise RuleError('offer_id должен быть целым номером предложения')
            offer=next((o for o in self.trade_offers if o['id']==args.get('offer_id')),None)
            if not offer: raise RuleError('Нет предложения с таким offer_id')
            if offer['partner']!=state.id: raise RuleError(f'Сделку #{offer["id"]} принимает только покупатель {offer["partner"]}; продавец {offer["seller"]} не может принять её за покупателя')
            if offer['status']!='open' or offer['expires']<self.day: raise RuleError('Предложение уже закрыто или истекло')
            seller=self.check_partner(state,offer['seller']); self.check_resource_transfer(seller,state,offer['resource'])
            goods={offer['resource']:offer['amount']}; cash={'money':round(offer['amount']*offer['price'],4)}
            self.require_funds(seller,goods); self.require_funds(state,cash)
            assessment=self.assess_trade(state,offer); export=self.export_risk(seller,offer['resource'],offer['amount'])
            if export and not offer.get('allow_risk'): raise RuleError(export+'; поставщик должен разрешить этот риск в новом предложении')
            if assessment['risk_flags'] and not self.risk_acknowledged(args): raise RuleError('Экономический риск: '+'; '.join(assessment['risk_flags'])+'; при осознанном риске укажи allow_risk=true и reason')
            # Both validations precede both mutations, so no half-paid secure trade exists.
            ids=[self.move_bundle(seller,state,goods,'trade',offer['id']),self.move_bundle(state,seller,cash,'payment',offer['id'])]
            offer.update(status='accepted',accepted_day=self.day,buyer_reason=args.get('reason',''),receipt_ids=ids)
            self.record_trade_statistics(seller,state,offer['resource'],offer['amount'],cash['money'])
            return f'Сделка #{offer["id"]} ИСПОЛНЕНА: {goods} ↔ {cash}; квитанции {ids}'
        peer=self.check_partner(state,args.get('partner')); resource=args.get('resource'); amount=args.get('amount')
        limit=1000000 if self.era_for(state)==2 else 10000
        if type(amount) is not int or not 1<=amount<=limit: raise RuleError(f'Количество: целое 1–{limit}')
        self.check_resource_transfer(state,peer,resource); self.require_funds(state,{resource:amount})
        if kind=='transfer':
            self.check_export_bundle(state,{resource:amount},args); rid=self.move_bundle(state,peer,{resource:amount},'transfer')
            self.relation_fact(peer.id,state.id,'gift',f'Получено {amount} {resource}; квитанция #{rid}',5)
            return f'ПЕРЕДАНО {amount} {resource} → {peer.name}; квитанция #{rid}'
        price=args.get('price',1)
        if resource=='money' or type(price) not in (int,float) or not math.isfinite(price) or not .01<=price<=1000: raise RuleError('Предложение продажи: ресурс кроме денег, цена 0.01–1000')
        self.check_export_bundle(state,{resource:amount},args)
        if sum(o['seller']==state.id and o['status']=='open' and o['expires']>=self.day for o in self.trade_offers)>=20: raise RuleError('Сначала закройте или дождитесь истечения старых предложений; не более 20 открытых')
        offer=dict(id=self.next_offer,seller=state.id,partner=peer.id,resource=resource,amount=amount,price=price,day=self.day,expires=self.day+5,status='open',allow_risk=args.get('allow_risk') is True,seller_reason=args.get('reason',''))
        self.next_offer+=1; self.trade_offers.append(offer)
        self.log('trade_offer',f'Предложение #{offer["id"]}: {state.name} → {peer.name}, {amount} {resource} за {amount*price:g}; ждёт согласия покупателя.',visible_to=[state.id,peer.id])
        return f'Предложение #{offer["id"]} создано: {amount} {resource} за {amount*price:g}; ожидает accept_trade от {peer.id}. Ресурсы пока не переданы.'

    def record_trade_statistics(self,seller,buyer,resource,amount,total):
        # move_bundle has already credited promises; never count a single delivery twice.
        for sid,peer,flow in ((seller.id,buyer.id,'exports'),(buyer.id,seller.id,'imports')):
            row=self.relation(sid,peer); row['trade_count']+=1; row[flow][resource]=row[flow].get(resource,0)+amount; row['received' if flow=='exports' else 'paid']+=total
            self.relation_fact(sid,peer,'trade',f'Сделка: {amount} {resource}, сумма {total:g}.',3)

    def exchange_action(self,state,kind,args):
        if kind=='offer_exchange':
            peer=self.check_partner(state,args.get('partner')); give=self.validate_bundle(state,peer,args.get('give')); receive=self.validate_bundle(state,peer,args.get('receive')); mode=args.get('mode','secure'); due=args.get('due_days',3)
            if mode not in ('secure','advance','credit') or type(due) is not int or not 1<=due<=10: raise RuleError('mode secure/advance/credit, due_days 1–10')
            if set(give)&set(receive): raise RuleError('Один ресурс нельзя одновременно обещать в обе стороны; укажи чистый обмен')
            if mode in ('secure','credit'): self.require_funds(state,give)
            if mode in ('secure','credit'): self.check_export_bundle(state,give,args)
            if sum(e['seller']==state.id and e['status']=='open' for e in self.exchanges)>=12: raise RuleError('Не более 12 открытых предложений обмена')
            row=dict(id=self.next_exchange,seller=state.id,partner=peer.id,give=give,receive=receive,mode=mode,due_days=due,day=self.day,expires=self.day+5,status='open',receipt_ids=[],debtor=None,creditor=None,owed={},allow_risk=args.get('allow_risk') is True,private_reason={state.id:str(args.get('reason',''))[:2000]})
            self.next_exchange+=1; self.exchanges.append(row)
            return f'Предложен обмен #{row["id"]}, {mode}: отдаём {give}, получаем {receive}; адресат {peer.id} должен accept_exchange'
        if type(args.get('exchange_id')) is not int: raise RuleError('exchange_id должен быть целым номером обмена')
        deal=next((d for d in self.exchanges if d['id']==args.get('exchange_id')),None)
        if not deal or state.id not in (deal['seller'],deal['partner']): raise RuleError('Нет своего обмена с таким exchange_id')
        seller,buyer=self.state(deal['seller']),self.state(deal['partner'])
        if kind=='accept_exchange':
            if state.id!=buyer.id or deal['status']!='open' or deal['expires']<self.day: raise RuleError('Принять открытое предложение может только его адресат-покупатель')
            self.check_partner(state,seller.id)
            for bundle in (deal['give'],deal['receive']): self.validate_bundle(seller,buyer,bundle)
            if deal['mode']!='secure' and not self.risk_acknowledged(args): raise RuleError('Это обмен БЕЗ ГАРАНТИЙ: контрагент может оставить аванс/товар. Нужны allow_risk=true и reason')
            if deal['mode'] in ('secure','credit'): self.require_funds(seller,deal['give'])
            if deal['mode'] in ('secure','advance'): self.require_funds(buyer,deal['receive'])
            if deal['mode']=='secure':
                self.check_export_bundle(seller,deal['give'],dict(allow_risk=deal.get('allow_risk'),reason=deal['private_reason'].get(seller.id,''))); self.check_export_bundle(buyer,deal['receive'],args)
                ids=[self.move_bundle(seller,buyer,deal['give'],'exchange',deal['id']),self.move_bundle(buyer,seller,deal['receive'],'exchange',deal['id'])]
                deal.update(status='fulfilled',receipt_ids=ids,resolved_day=self.day)
            else:
                first,second,bundle,owed=(buyer,seller,deal['receive'],deal['give']) if deal['mode']=='advance' else (seller,buyer,deal['give'],deal['receive'])
                rid=self.move_bundle(first,second,bundle,'unsecured_first_leg',deal['id'])
                deal.update(status='awaiting_delivery',debtor=second.id,creditor=first.id,owed=dict(owed),due_day=self.day+deal['due_days'],receipt_ids=[rid])
                self.relation_fact(first.id,second.id,'credit_exposure',f'Обмен #{deal["id"]}: передано {bundle}; ожидается {owed} до дня {deal["due_day"]}, без автоматического взыскания')
            deal['private_reason'][state.id]=str(args.get('reason',''))[:2000]
            return f'Обмен #{deal["id"]}: {deal["status"]}; квитанции {deal["receipt_ids"]}'
        if kind=='cancel_exchange':
            if deal['seller']!=state.id or deal['status']!='open': raise RuleError('Отозвать можно только своё ещё не принятое предложение; после получения чужой части используется breach_exchange')
            deal['status']='cancelled'; return f'Предложение обмена #{deal["id"]} отозвано'
        if deal['debtor']!=state.id or deal['status'] not in ('awaiting_delivery','defaulted','repudiated'): raise RuleError('Только должник незакрытого обмена может исполнить/нарушить свою часть')
        if kind=='breach_exchange':
            if deal['status']!='awaiting_delivery': raise RuleError('Нарушение уже зафиксировано')
            self.default_exchange(deal,'repudiated'); deal['private_reason'][state.id]=str(args.get('reason',''))[:2000]
            return f'Обмен #{deal["id"]}: встречная поставка сознательно НЕ отправлена; полученная чужая часть остаётся, отношения испорчены'
        self.check_partner(state,deal['creditor']); self.require_funds(state,deal['owed'])
        rid=self.move_bundle(state,self.state(deal['creditor']),deal['owed'],'unsecured_completion',deal['id']); late=deal['status']!='awaiting_delivery'
        deal.update(status='settled_late' if late else 'fulfilled',resolved_day=self.day); deal['receipt_ids'].append(rid)
        self.relation_fact(deal['creditor'],state.id,'exchange_delivered',f'Обмен #{deal["id"]}: встречная часть действительно получена, квитанция #{rid}',4 if late else 8)
        return f'Обмен #{deal["id"]} исполнен; квитанция #{rid}'

    def default_exchange(self,deal,status):
        deal.update(status=status,resolved_day=self.day)
        text=f'Обмен #{deal["id"]}: {deal["debtor"]} получил встречную часть и не передал {deal["owed"]}'
        self.relation_fact(deal['creditor'],deal['debtor'],'exchange_betrayal',text,-35)
        self.relation(deal['creditor'],deal['debtor'])['grievances'].append(dict(day=self.day,text=text,source='engine'))
        self.log('exchange_default',text,visible_to=[deal['seller'],deal['partner']])

    def process_exchanges(self):
        for deal in self.exchanges:
            if deal['status']=='open' and deal['expires']<self.day: deal['status']='expired'
            if deal['status']=='awaiting_delivery' and self.day>deal['due_day']: self.default_exchange(deal,'defaulted')

    def default_action(self,state,kind,args):
        if kind=='repudiate_debt':
            peer=self.state(args.get('partner')); pact_id=args.get('pact_id'); claims=[c for c in state.modern.get('claims',[]) if c['creditor']==peer.id and (pact_id is None or c['pact_id']==pact_id) and not c.get('repudiated')]
            if pact_id is not None and type(pact_id) is not int: raise RuleError('pact_id: целый номер или пропущен')
            if not claims or peer.id==state.id: raise RuleError('Нет указанного неоплаченного договорного долга')
            for claim in claims: claim['repudiated']=True
            self.relation_fact(peer.id,state.id,'debt_repudiated',f'Отказ от взыскания долга {sum(c["amount"] for c in claims):g}',-30)
            return 'Долг оспорен: автоматические выплаты прекращены, претензия и враждебность сохраняются'
        if type(args.get('pact_id')) is not int: raise RuleError('pact_id должен быть целым номером пакта')
        pact=next((p for p in self.supply_pacts if p['id']==args.get('pact_id')),None)
        if not pact or pact['status']!='active' or state.id not in (pact['seller'],pact['partner']): raise RuleError('Нужен свой действующий пакт')
        if kind=='resume_supply':
            pact.setdefault('withheld',{}).pop(state.id,None); return 'Собственное прекращение поставок/платежей отменено'
        duration=args.get('duration',1)
        if type(duration) is not int or not 1<=duration<=10: raise RuleError('Срок намеренного срыва: 1–10 дней')
        pact.setdefault('withheld',{})[state.id]=self.day+duration
        return 'Поставки/платежи сознательно приостановлены; возможны договорные штрафы, претензии и ответные меры'

    @read_analysis
    def commerce_context(self,state):
        exchanges=[]
        for row in self.exchanges:
            if state.id not in (row['seller'],row['partner']): continue
            value=copy.deepcopy(row); private=value.pop('private_reason',{}); value['own_reason']=private.get(state.id,'')
            value.update(my_role='seller' if state.id==row['seller'] else 'buyer',can_accept=state.id==row['partner'] and row['status']=='open' and row['expires']>=self.day,can_deliver=state.id==row['debtor'] and row['status'] in ('awaiting_delivery','defaulted','repudiated'),guaranteed=row['mode']=='secure')
            exchanges.append(value)
        receipts=[]
        for row in reversed(self.settlements):
            if state.id not in (row['sender'],row['recipient']): continue
            value=copy.deepcopy(row); value['balances']={state.id:value['balances'].get(state.id,{})}; receipts.append(value)
            if len(receipts)==40: break
        receipts.reverse()
        important=[e for e in exchanges if e['status'] in ('awaiting_delivery','defaulted','repudiated')]
        recent=[e for e in exchanges[-40:] if e['id'] not in {item['id'] for item in important}]
        receivable={}; payable={}
        for e in important:
            dest=receivable if e['creditor']==state.id else payable
            for k,v in e['owed'].items(): dest[k]=dest.get(k,0)+v
        return dict(exchanges=(recent+important)[-120:],receipts=receipts,unsecured_receivable=receivable,unsecured_payable=payable,incoming_trade_offers=[self.visible_trade_offer(state,o) for o in self.trade_offers if o['partner']==state.id and o['status']=='open' and o['expires']>=self.day],
            rules='Переписка — слова. Реальный перевод имеет квитанцию. trade лишь создаёт предложение, accept_trade покупателя исполняет обе части сразу; cell не нужен. transfer отправляет сейчас. offer_exchange/accept_exchange позволяют бартер, аванс или кредит. В advance/credit уже полученную часть можно оставить через breach_exchange или просрочку, но появляются обида и риск ответных мер. Чужая часть без гарантий НЕ считается обеспеченным доходом. Коварство и выгодное предательство допустимы; оцени собственный выигрыш, а не одобрение партнёра.')
