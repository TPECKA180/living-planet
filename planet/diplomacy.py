"""Private political dossiers plus objective, engine-written diplomatic facts."""
import copy
from .performance import mutation

from .rules import RuleError


def profile():
    return dict(trust=0,stance='neutral',trade_policy='normal',memo='',grievances=[],
                facts=[],trade_count=0,imports={},exports={},paid=0,received=0,embargo=False,peace_requested=False,last_review_day=None)


class Diplomacy:
    def relation(self,sid,partner):
        state=self.state(sid); self.state(partner)
        if sid==partner: raise RuleError('Нужно другое государство')
        if partner not in state.relations: state.relations[partner]=profile()
        for key,value in profile().items(): state.relations[partner].setdefault(key,value)
        return state.relations[partner]

    def relation_fact(self,sid,partner,kind,text,trust_delta=0):
        record=self.relation(sid,partner)
        record['facts'].append(dict(day=self.day,kind=kind,text=text))
        record['trust']=max(-100,min(100,record['trust']+trust_delta))

    def at_war(self,a,b): return sorted((a,b)) in self.wars

    def conflict_status(self,a,b):
        return 'ВОЙНА' if self.at_war(a,b) else 'СОЮЗ' if b in self.state(a).allies else 'МИР'

    @mutation
    def set_war(self,a,b,reason,attack=False,defensive=False):
        pair=sorted((a,b))
        if pair in self.wars: return
        permission=self.war_permission(a,b)
        if permission: raise RuleError(permission)
        if not defensive: self.record_aggression(a,b)
        self.wars.append(pair)
        first=self.state(a); second=self.state(b)
        was_allied=b in first.allies
        first.allies=[sid for sid in first.allies if sid!=b]
        second.allies=[sid for sid in second.allies if sid!=a]
        for sid,peer in ((a,b),(b,a)):
            record=self.relation(sid,peer); record['stance']='enemy'; record['peace_requested']=False
        self.relation_fact(a,b,'war',f'Начата война: {reason}',-20)
        self.relation_fact(b,a,'betrayal' if was_allied else 'war',f'{first.name} '+('напал' if attack else 'объявил войну')+f': {reason}',-70 if was_allied else -45)
        self.relation(b,a)['grievances'].append(dict(day=self.day,text=f'{first.name} '+('напал' if attack else 'объявил войну')+f': {reason}',source='engine'))
        self.log('war',f'{first.name} и {second.name}: война. {reason}')
        self.protect_vassal(a,b)

    def record_trade(self,seller,buyer,resource,amount,total):
        self.record_delivery(seller,buyer,resource,amount)
        self.record_delivery(buyer,seller,'money',total)
        for sid,peer,flow in ((seller,buyer,'exports'),(buyer,seller,'imports')):
            record=self.relation(sid,peer); record['trade_count']+=1
            record[flow][resource]=record[flow].get(resource,0)+amount
            record['received' if flow=='exports' else 'paid']+=total
            self.relation_fact(sid,peer,'trade',f'Сделка: {amount} {resource}, сумма {total}.',3)

    def economic_block(self,a,b):
        return self.relation(a,b)['embargo'] or self.relation(b,a)['embargo']

    def diplomatic_action(self,state,kind,args):
        partner=self.state(args.get('partner'))
        if partner.id==state.id: raise RuleError('Партнёром должно быть другое государство')
        if partner.eliminated and kind!='relationship': raise RuleError('Государство уже выбыло; новые войны и санкции ему не объявляются')
        record=self.relation(state.id,partner.id)
        if kind=='relationship':
            updates={key:args[key] for key in ('trust','stance','trade_policy','memo') if key in args}
            if 'trust' in updates and (type(updates['trust']) is not int or not -100<=updates['trust']<=100): raise RuleError('trust: целое от -100 до 100')
            if 'stance' in updates and updates['stance'] not in ('neutral','friend','rival','enemy'): raise RuleError('Неверная политическая оценка')
            if 'trade_policy' in updates and updates['trade_policy'] not in ('normal','preferred','avoid'): raise RuleError('Неверная торговая политика')
            for key in ('memo','grievance'):
                if key in args and (not isinstance(args[key],str) or len(args[key])>4000): raise RuleError('Некорректная заметка отношений')
            if 'trust' in updates and hasattr(self,'_opinion_baselines'):
                key=(state.id,partner.id); previous=self._opinion_baselines.get(key,record['trust'])
                proposed=updates['trust']; updates['trust']=max(-100,min(100,record['trust']+proposed-previous))
                self._opinion_baselines[key]=proposed
            record.update(updates); record['last_review_day']=self.day
            if self.at_war(state.id,partner.id): record['stance']='enemy'
            if args.get('grievance'): record['grievances'].append(dict(day=self.day,text=args['grievance'],source='agent'))
            return f'Оценка отношений с {partner.name} обновлена'
        if kind=='declare_war':
            reason=args.get('reason')
            if not isinstance(reason,str) or not reason.strip(): raise RuleError('Объясните причину объявления войны')
            self.set_war(state.id,partner.id,reason)
            return f'Война с {partner.name}: {reason}'
        if kind=='peace':
            if not self.at_war(state.id,partner.id): raise RuleError('Между государствами нет войны')
            record['peace_requested']=True
            if self.relation(partner.id,state.id)['peace_requested']:
                self.wars.remove(sorted((state.id,partner.id)))
                for sid,peer in ((state.id,partner.id),(partner.id,state.id)):
                    item=self.relation(sid,peer); item['peace_requested']=False; item['stance']='rival' if item['trust']<0 else 'neutral'
                    self.relation_fact(sid,peer,'peace','Обе стороны согласились прекратить войну',10)
                self.log('peace',f'{state.name} и {partner.name} заключили мир.')
                return f'Взаимный мир с {partner.name}'
            self.relation_fact(partner.id,state.id,'peace_offer','Предложено прекращение войны')
            return f'Предложен мир {partner.name}; ожидается ответное действие peace'
        if kind=='embargo':
            if type(args.get('enabled')) is not bool: raise RuleError('enabled должен быть true/false')
            record['embargo']=args['enabled']
            text='Торговля запрещена' if record['embargo'] else 'Эмбарго снято'
            self.relation_fact(partner.id,state.id,'embargo',text,-10 if record['embargo'] else 0)
            self.log('diplomacy',f'{state.name} → {partner.name}: {text}')
            return text
        raise RuleError('Неизвестное дипломатическое действие')

    def initialise_relations(self,historical=False):
        historical=historical and not any(state.relations for state in self.states)
        for state in self.states:
            for other in self.states:
                if state.id==other.id: continue
                item=self.relation(state.id,other.id)
                if historical and other.id in state.allies:
                    item['trust']=max(item['trust'],15); item['stance']='friend'
                    item['facts'].append(dict(day=self.day,kind='alliance',text='Союз унаследован из сохранения'))
        if historical:
            for offer in self.trade_offers:
                if offer.get('status')=='accepted':
                    self.record_trade(offer['seller'],offer['partner'],offer['resource'],offer['amount'],offer['price']*offer['amount'])
                    for sid,peer in ((offer['seller'],offer['partner']),(offer['partner'],offer['seller'])):
                        fact=self.relation(sid,peer)['facts'][-1]
                        fact['day']=offer.get('accepted_day'); fact['imported']=True
            for move in self.movement_log:
                peer=move.get('previous_owner')
                if peer and peer!=move['owner']:
                    self.relation(peer,move['owner'])['facts'].append(dict(day=move['day'],kind='attack',text=f'В сохранении зафиксирована атака клетки {move["target"]}'))

    def relations_context(self,state):
        result={}
        for other in self.states:
            if other.id==state.id: continue
            item=copy.deepcopy(self.relation(state.id,other.id))
            item['facts']=item['facts'][-25:]; item['grievances']=item['grievances'][-15:]
            item['at_war']=self.at_war(state.id,other.id); item['allied']=other.id in state.allies
            item['embargo_active']=self.economic_block(state.id,other.id)
            item['partner_name']=other.name
            item['vassal_of']=other.vassal_of
            result[other.id]=item
        return result
