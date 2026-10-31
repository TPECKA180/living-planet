"""Consensual vassal contracts and verifiable promises; words do not move assets."""
import copy
from .rules import RuleError
from .performance import read_analysis


class Politics:
    def active_vassal_contract(self,subject):
        return next((t for t in self.vassal_treaties if t['subject']==subject and t['status']=='active'),None)

    def end_vassal_contract(self,contract,status):
        contract['status']=status; contract['ended_day']=self.day
        self.state(contract['subject']).vassal_of=None
        self.log('vassalage',f"{self.state(contract['subject']).name}: вассальный договор с {self.state(contract['lord']).name} завершён ({status}).")

    def process_contracts(self):
        for contract in self.vassal_treaties:
            if contract['status']!='active': continue
            if self.state(contract['lord']).eliminated or self.state(contract['subject']).eliminated: self.end_vassal_contract(contract,'ended_defeat')
            elif self.day>contract['until_day']: self.end_vassal_contract(contract,'expired')
        for offer in self.vassal_offers:
            if offer['status']=='open' and self.day>offer['expires']: offer['status']='expired'
        for pledge in self.pledges:
            if pledge['status']=='open' and self.day>pledge['due_day']:
                self.finish_pledge(pledge,'fulfilled' if pledge['kind']=='non_aggression' else 'broken')

    @read_analysis
    def tribute_forecast(self):
        cache=getattr(self,'_analysis_index',None)
        if cache is not None and 'tributes' in cache: return dict(cache['tributes'])
        flow={s.id:0.0 for s in self.states}
        for t in self.vassal_treaties:
            if t['status']!='active' or self.day+1>t['until_day'] or self.state(t['lord']).eliminated or self.state(t['subject']).eliminated: continue
            subject=self.state(t['subject'])
            gross=sum(self.production_for_cell(subject,self.cell(p))['money'] for p in self.positions(subject.id))
            if self.era_for(subject)==2: gross=self.industrial_plan(subject)['gross']['money']
            amount=round(gross*t['tribute_percent']/100,2)
            flow[t['subject']]-=amount; flow[t['lord']]+=amount
        if cache is not None: cache['tributes']=dict(flow)
        return flow

    def pay_tribute(self,gross_money):
        for t in self.vassal_treaties:
            if t['status']!='active': continue
            subject=self.state(t['subject']); lord=self.state(t['lord'])
            if subject.eliminated or lord.eliminated: continue
            amount=min(subject.stocks['money'],round(gross_money.get(subject.id,0)*t['tribute_percent']/100,2))
            if amount: self.move_bundle(subject,lord,dict(money=amount),'tribute',t.get('id'),credit_promises=False)
            t['paid_total']=round(t['paid_total']+amount,2); t['last_payment']=dict(day=self.day,amount=amount)
            if amount: self.log('tribute',f'{subject.name} → {lord.name}: дань {amount:g} денег ({t["tribute_percent"]}% собственной денежной добычи).')

    def war_permission(self,attacker,defender):
        first=self.state(attacker); second=self.state(defender)
        if first.vassal_of==defender or second.vassal_of==attacker: return 'Сначала rebel или release_vassal: действующий вассальный договор запрещает нападение внутри пары'
        if first.vassal_of and not self.at_war(first.vassal_of,defender): return 'Вассал не начинает отдельную наступательную войну: сначала сюзерен должен воевать с этой целью'
        return None

    def protect_vassal(self,attacker,defender):
        lord=self.state(defender).vassal_of
        if lord and lord!=attacker and not self.state(lord).eliminated:
            self.set_war(lord,attacker,'Обязательная защита вассала '+self.state(defender).name,defensive=True)

    def politics_action(self,state,kind,args):
        if kind=='accept_vassalage':
            offer=next((o for o in self.vassal_offers if o['id']==args.get('offer_id')),None)
            if not offer or offer['subject']!=state.id or offer['status']!='open' or self.day>offer['expires']: raise RuleError('Нет действующего предложения вассалитета для этой страны')
            lord=self.state(offer['lord'])
            if lord.eliminated or lord.vassal_of or state.vassal_of or any(t['status']=='active' and t['lord']==state.id for t in self.vassal_treaties): raise RuleError('Нельзя создать вложенный, повторный или циклический вассалитет')
            reason=args.get('reason')
            if not isinstance(reason,str) or len(reason.strip())<8: raise RuleError('Нужно осознанное обоснование принятия вассалитета')
            if any(state.id in pair and self.state(next(sid for sid in pair if sid!=state.id)).vassal_of==lord.id for pair in self.wars): raise RuleError('Сначала завершите войну с другим вассалом этого сюзерена')
            contract=dict(lord=lord.id,subject=state.id,tribute_percent=offer['tribute_percent'],start_day=self.day,until_day=self.day+offer['duration'],paid_total=0,status='active')
            self.vassal_treaties.append(contract); state.vassal_of=lord.id; offer['status']='accepted'; offer['accepted_day']=self.day
            if self.at_war(lord.id,state.id): self.wars.remove(sorted((lord.id,state.id)))
            for own,peer in ((state.id,lord.id),(lord.id,state.id)):
                self.relation(own,peer)['stance']='friend'; self.relation(own,peer)['peace_requested']=False
                self.relation_fact(own,peer,'vassalage',f'Договор: {state.name} платит {offer["tribute_percent"]}% денежного дохода, {lord.name} обязан защищать; до дня {contract["until_day"]}',5)
            # Existing wars against the new subject also invoke the signed protection.
            for pair in list(self.wars):
                if state.id in pair: self.protect_vassal(next(sid for sid in pair if sid!=state.id),state.id)
            self.log('vassalage',f'{state.name} принял вассалитет {lord.name}.')
            return f'Принят вассалитет: дань {offer["tribute_percent"]}%, защита сюзерена, суверенные земли и армия сохранены'
        if kind=='rebel':
            contract=self.active_vassal_contract(state.id)
            if not contract: raise RuleError('Страна не является вассалом')
            lord=contract['lord']; self.end_vassal_contract(contract,'rebelled')
            self.relation_fact(lord,state.id,'rebellion','Вассал разорвал договор и поднял восстание',-30)
            self.set_war(state.id,lord,'Восстание против сюзерена')
            return 'Восстание: дань прекращена, началась война за независимость'
        partner=self.state(args.get('partner'))
        if partner.id==state.id or partner.eliminated: raise RuleError('Нужен другой действующий партнёр')
        if kind=='offer_vassalage':
            rate=args.get('tribute_percent'); duration=args.get('duration',10); reason=args.get('reason')
            if state.vassal_of or partner.vassal_of or any(t['status']=='active' and t['lord']==partner.id for t in self.vassal_treaties): raise RuleError('Только независимые страны, без вложенной вассальной иерархии')
            if type(rate) is not int or not 10<=rate<=40 or type(duration) is not int or not 5<=duration<=50: raise RuleError('Дань 10–40%, срок 5–50 дней')
            if not isinstance(reason,str) or len(reason.strip())<8: raise RuleError('Нужно обоснование предложения вассалитета')
            if any(o['lord']==state.id and o['subject']==partner.id and o['status']=='open' and self.day<=o['expires'] for o in self.vassal_offers): raise RuleError('Открытое предложение уже есть')
            self.vassal_offers.append(dict(id=self.next_vassal_offer,lord=state.id,subject=partner.id,tribute_percent=rate,duration=duration,reason=reason,day=self.day,expires=self.day+5,status='open'))
            self.next_vassal_offer+=1
            self.relation_fact(partner.id,state.id,'vassal_offer',f'Предложен вассалитет: дань {rate}%, срок {duration} дней; требуется собственное accept_vassalage')
            return f'Предложение вассалитета #{self.next_vassal_offer-1}; без согласия партнёра дань не взимается'
        if kind=='release_vassal':
            contract=self.active_vassal_contract(partner.id)
            if not contract or contract['lord']!=state.id: raise RuleError('Это не ваш вассал')
            self.end_vassal_contract(contract,'released'); self.relation_fact(partner.id,state.id,'liberation','Сюзерен предоставил независимость',10)
            return 'Вассал освобождён; договор и дань прекращены'
        if kind=='pledge':
            pledge_kind=args.get('kind'); duration=args.get('duration',3); public=args.get('public',False)
            if pledge_kind not in ('delivery','non_aggression') or type(duration) is not int or not 1<=duration<=10 or type(public) is not bool: raise RuleError('pledge: kind delivery/non_aggression, срок 1–10, public true/false')
            if pledge_kind=='non_aggression' and self.at_war(state.id,partner.id): raise RuleError('Сначала заключите реальный мир')
            resource=args.get('resource'); amount=args.get('amount')
            if pledge_kind=='delivery' and (resource not in state.stocks or type(amount) is not int or not 1<=amount<=1000): raise RuleError('Обещанная поставка: ресурс и количество 1–1000')
            if sum(p['sender']==state.id and p['status']=='open' for p in self.pledges)>=8: raise RuleError('Не более восьми незакрытых обещаний')
            pledge=dict(id=self.next_pledge,sender=state.id,recipient=partner.id,kind=pledge_kind,resource=resource if pledge_kind=='delivery' else None,amount=amount if pledge_kind=='delivery' else 0,delivered=0,day=self.day,due_day=self.day+duration,public=public,status='open')
            self.next_pledge+=1; self.pledges.append(pledge)
            self.relation_fact(partner.id,state.id,'pledge',f'Обещание #{pledge["id"]}: {pledge_kind}, срок до дня {pledge["due_day"]}')
            if public: self.log('pledge',f'{state.name} публично обещает {partner.name}: {pledge_kind}, до дня {pledge["due_day"]}.')
            return f'Зарегистрировано обещание #{pledge["id"]}; ресурсы не резервируются, нарушение будет зафиксировано'
        raise RuleError('Неизвестное политическое действие')

    def finish_pledge(self,pledge,status):
        if pledge['status']!='open': return
        pledge['status']=status; pledge['resolved_day']=self.day
        delta=5 if status=='fulfilled' else -20
        text=f'Обещание #{pledge["id"]} '+('выполнено' if status=='fulfilled' else 'нарушено')
        self.relation_fact(pledge['recipient'],pledge['sender'],'promise_'+status,text,delta)
        if status=='broken': self.relation(pledge['recipient'],pledge['sender'])['grievances'].append(dict(day=self.day,text=text,source='engine'))
        if pledge['public']:
            for watcher in self.states:
                if watcher.id not in (pledge['sender'],pledge['recipient']) and not watcher.eliminated:
                    self.relation_fact(watcher.id,pledge['sender'],'public_promise_'+status,text,1 if status=='fulfilled' else -5)
            self.log('pledge',self.state(pledge['sender']).name+': '+text)

    def record_delivery(self,sender,recipient,resource,amount):
        available=amount
        for pledge in sorted(self.pledges,key=lambda p:(p['due_day'],p['id'])):
            if available<=0: break
            if pledge['status']=='open' and pledge['kind']=='delivery' and pledge['sender']==sender and pledge['recipient']==recipient and pledge['resource']==resource and self.day<=pledge['due_day']:
                used=min(available,pledge['amount']-pledge['delivered']); pledge['delivered']+=used; available-=used
                if pledge['delivered']>=pledge['amount']: self.finish_pledge(pledge,'fulfilled')

    def record_aggression(self,attacker,defender):
        for pledge in self.pledges:
            if pledge['status']=='open' and pledge['kind']=='non_aggression' and pledge['sender']==attacker and pledge['recipient']==defender and self.day<=pledge['due_day']: self.finish_pledge(pledge,'broken')

    def political_context(self,state):
        return dict(vassal_of=state.vassal_of,
                    treaties=[copy.deepcopy(t) for t in self.vassal_treaties if state.id in (t['lord'],t['subject'])],
                    offers=[dict(o) for o in self.vassal_offers if state.id in (o['lord'],o['subject']) and o['status']=='open' and self.day<=o['expires']],
                    pledges=[dict(p) for p in self.pledges if p['public'] or state.id in (p['sender'],p['recipient'])][-40:],
                    rule='Вассал сохраняет земли, характер и армию, платит долю собственной денежной добычи и ограничен во внешних войнах. Принять договор может только он сам. Обещания можно нарушить, но движок фиксирует факт и последствия доверия.')
