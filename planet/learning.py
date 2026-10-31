"""Private reward ledger and persistent reflective memory; no model-weight training."""
import copy,hashlib,json,math

def decision_signature(decision):
    keys=('owner','actions','diplomacy','relation_reviews','construction_review','economic_review','military_response','notes','plan','learning_notes','learning_review')
    return hashlib.sha256(json.dumps({k:decision.get(k) for k in keys},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def ready(decision,day):return decision.get('execution_ready')==dict(day=day,signature=decision_signature(decision))

def review_schema(context):
    text=dict(type='string',minLength=10,maxLength=2000)
    props=dict(hypothesis=text,metric=dict(type='string',enum=sorted(set(context.get('stocks',{}))|{'score','territory','population','military_strength'})),
               direction=dict(type='string',enum=['increase','decrease']),target_change=dict(type='number',exclusiveMinimum=0,maximum=1e9),
               horizon_days=dict(type='integer',minimum=1,maximum=10),stop_condition=text,next_action=text)
    return dict(anyOf=[dict(type='null'),dict(type='object',properties=props,required=list(props),additionalProperties=False)])

class Learning:
    def learning_record(self,sid):
        if not hasattr(self,'learning'):self.learning={}
        record=self.learning.setdefault(sid,dict(score=0.0,events=[],notes='',notes_history=[],last_reward_day=-1,subjects_rewarded=[]))
        for key,value in dict(episodes=[],experiments=[],active_experiment=None).items():record.setdefault(key,value)
        return record

    def learning_context(self,sid):
        record=self.learning_record(sid)
        episodes=record['episodes'];ranked=sorted((e for e in episodes if e.get('reward_version')=='6.8.1-daily'),key=lambda e:e['score_delta'])
        def summaries(rows):
            result=[]
            for episode in rows:
                item=copy.deepcopy(episode)
                item.setdefault('reward_version','legacy-monthly')
                breakdown=item.pop('reward_breakdown',[]);item['reward_totals']={reason:round(sum(e['delta'] for e in breakdown if e['reason']==reason),6) for reason in {e['reason'] for e in breakdown}}
                for key in ('before','after'):
                    if key in item:item[key]={k:v for k,v in item[key].items() if k in ('score','territory','population','military_strength','money','food')}
                for key in ('income','resource_delta'):
                    if key in item:item[key]={k:v for k,v in item[key].items() if v}
                item['actions']=[dict(type=a.get('type'),success=a.get('success'),args={k:v for k,v in a.get('args',{}).items() if k not in ('reason','memo','grievance')}) for a in item.get('actions',[])]
                result.append(item)
            return result
        return dict(score=record['score'],notes=record['notes'],recent_rewards=copy.deepcopy(record['events'][-24:]),
                    recent_episodes=summaries(episodes[-5:]),best_examples=summaries(ranked[-2:]),worst_examples=summaries(ranked[:2]),
                    active_experiment=copy.deepcopy(record['active_experiment']),experiment_results=copy.deepcopy(record['experiments'][-4:]),last_review_error=record.get('review_error'),
                    rule='Начисление раз в ДЕНЬ: лидер по положительному запасу каждого ресурса +1 (ничья делит очко), отрицательный net каждого ресурса -1/день. Нейтральная клетка +0.005, захват +0.5, потеря -1; стать вассалом -2, новый вассал +4 один раз на пару, потерять вассала -2; новая технология +0.25, отказ приказа -0.05. learning_review задаёт измеримый эксперимент; достижение проверяет движок, но оно не создаёт дополнительных очков. Эпизоды показывают факты, а не доказывают причинность. Анализируй ошибки, удачные и неудачные примеры; обновляй learning_notes по результатам. Это память и обратная связь, без обучения весов. null сохраняет заметки/продолжает текущий эксперимент.')

    def learning_metrics(self,state):
        return dict(score=self.learning_record(state.id)['score'],territory=len(self.positions(state.id)),population=sum(self.cell(p).population for p in self.positions(state.id)),
                    military_strength=round(sum(self.effective_strength(u) for u in self.units if u['owner']==state.id),4),**{k:state.stocks.get(k,0) for k in self.resource_keys(state)})

    def start_experiment(self,state,review):
        if review is None:return
        if not isinstance(review,dict):raise ValueError('learning_review должен быть объектом или null')
        if set(review)!={'hypothesis','metric','direction','target_change','horizon_days','stop_condition','next_action'}:raise ValueError('learning_review содержит пропущенные или неизвестные поля')
        metrics=self.learning_metrics(state)
        if review.get('metric') not in metrics or review.get('direction') not in ('increase','decrease'):raise ValueError('Неверная метрика/направление learning_review')
        if type(review.get('horizon_days')) is not int or not 1<=review['horizon_days']<=10:raise ValueError('Горизонт эксперимента 1–10 дней')
        target=review.get('target_change')
        if type(target) not in (int,float) or not math.isfinite(target) or not 0<target<=1e9:raise ValueError('target_change: положительное конечное число')
        if any(not isinstance(review.get(k),str) or not 10<=len(review[k].strip())<=2000 for k in ('hypothesis','stop_condition','next_action')):raise ValueError('Нужны гипотеза, условие остановки и следующий шаг')
        record=self.learning_record(state.id);previous=record['active_experiment']
        record.pop('review_error',None)
        if previous and all(previous.get(k)==v for k,v in review.items()):return
        if previous:
            record['experiments'].append(dict(**previous,status='revised',closed_day=self.day))
        record['active_experiment']=dict(**copy.deepcopy(review),start_day=self.day,due_day=self.day+review['horizon_days']-1,baseline=metrics[review['metric']])

    def daily_rewards(self,add):
        resources={r for s in self.states if not s.eliminated for r in self.resource_keys(s)}
        for resource in sorted(resources):
            eligible=[s for s in self.states if not s.eliminated and resource in self.resource_keys(s)]
            best=max((s.stocks.get(resource,0) for s in eligible),default=0)
            leaders=[s for s in eligible if s.stocks.get(resource,0)==best] if best>0 else []
            for s in leaders:add(s.id,1/len(leaders),'daily_leader',resource=resource)
        for state in self.states:
            if not state.eliminated:
                for resource,item in self.economic_forecast(state)['resources'].items():
                    if item['net']<0:add(state.id,-1,'daily_deficit',resource=resource)

    def reward_baseline(self):
        return dict(owners=[c.owner for c in self.cells],lords={s.id:self.learning_record(s.id).get('last_lord',s.vassal_of) for s in self.states},tech={s.id:set(s.tech) for s in self.states},metrics={s.id:self.learning_metrics(s) for s in self.states})

    def settle_rewards(self,before):
        # Per-actor guard permits exact save/restore without paying a day twice.
        active={s.id for s in self.states if self.learning_record(s.id)['last_reward_day']<self.day}
        if not active:return
        def add(sid,amount,reason,**detail):
            if sid not in active:return
            record=self.learning_record(sid);record['score']=round(record['score']+amount,6)
            record['events'].append(dict(day=self.day,delta=round(amount,6),reason=reason,**detail))
        gains={s.id:dict(neutral=0,captured=0,lost=0) for s in self.states}
        for previous,cell in zip(before['owners'],self.cells):
            if previous==cell.owner:continue
            if cell.owner in gains:gains[cell.owner]['neutral' if previous is None else 'captured']+=1
            if previous in gains:gains[previous]['lost']+=1
        for state in self.states:
            sid=state.id;record=self.learning_record(sid);counts=gains[sid]
            for kind,value in (('neutral',.005),('captured',.5),('lost',-1)):
                if counts[kind]:add(sid,counts[kind]*value,'territory_'+kind,count=counts[kind])
            old_lord=before['lords'][sid];lord=state.vassal_of
            if lord!=old_lord:
                if old_lord:add(old_lord,-2,'vassal_lost',subject=sid)
                if lord:
                    add(sid,-2,'became_vassal',lord=lord)
                    lord_record=self.learning_record(lord)
                    if sid not in lord_record['subjects_rewarded']:
                        add(lord,4,'new_vassal',subject=sid)
                        if lord in active:lord_record['subjects_rewarded'].append(sid)
            learned=set(state.tech)-before['tech'][sid]
            if learned:add(sid,.25*len(learned),'research',technologies=sorted(learned))
            failed=len(state.decision_outcome.get('rejected',[])) if state.decision_outcome.get('day')==self.day else 0
            if failed:add(sid,-.05*failed,'rejected_orders',count=failed)
        if self.day>0:self.daily_rewards(add)
        for sid in active:
            record=self.learning_record(sid);state=self.state(sid);metrics=self.learning_metrics(state);prior=before['metrics'][sid]
            outcome=state.decision_outcome if state.decision_outcome.get('day')==self.day else {}
            record['episodes'].append(dict(day=self.day,reward_version='6.8.1-daily',before=copy.deepcopy(prior),after=copy.deepcopy(metrics),score_delta=round(metrics['score']-prior['score'],6),territory_delta=metrics['territory']-prior['territory'],
                resource_delta={k:round(metrics[k]-prior.get(k,0),4) for k in self.resource_keys(state)},income=copy.deepcopy(self.daily_income.get(sid,{})),accepted=outcome.get('accepted',0),rejected_count=len(outcome.get('rejected',[])),errors=outcome.get('rejected',[])[:3],
                actions=copy.deepcopy(outcome.get('action_results',[])),strategy_day=record['notes_history'][-1]['day'] if record['notes_history'] else None,
                reward_breakdown=[copy.deepcopy(e) for e in record['events'] if e['day']==self.day]))
            experiment=record['active_experiment']
            if experiment and self.day>=experiment['due_day']:
                delta=metrics[experiment['metric']]-experiment['baseline'];achieved=delta>=experiment['target_change'] if experiment['direction']=='increase' else delta<=-experiment['target_change']
                record['experiments'].append(dict(**experiment,status='evaluated',closed_day=self.day,actual_change=round(delta,6),achieved=achieved));record['active_experiment']=None
            record['last_reward_day']=self.day;record['last_lord']=state.vassal_of
