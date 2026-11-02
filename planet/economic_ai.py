"""Compile explicit treasury intentions; letters alone never manufacture resources."""
import copy,json
from .commerce import ECONOMIC_ACTIONS
from .isolation import checked_context


def economic_review_schema():
    return dict(type='object',properties=dict(mode=dict(type='string',enum=['execute','negotiate','deceive','decline','none']),reason=dict(type='string',minLength=20,maxLength=2000),orders=dict(type='array',maxItems=4,items=dict(type='object',properties=dict(type=dict(type='string',enum=list(ECONOMIC_ACTIONS)),args=dict(type='object')),required=['type','args'],additionalProperties=False))),required=['mode','reason','orders'],additionalProperties=False)


def signature(action):
    if not isinstance(action,dict) or not isinstance(action.get('args',{}),dict): raise ValueError('Нужен объект действия с args')
    kind=action.get('type',action.get('action')); args=copy.deepcopy(action.get('args',{}))
    if kind in ECONOMIC_ACTIONS:
        for key in ('cell','reason','memo','grievance','allow_risk'): args.pop(key,None)
    def normalized(v):
        if isinstance(v,dict): return {k:normalized(value) for k,value in v.items()}
        if isinstance(v,list): return [normalized(x) for x in v]
        if type(v) is float and v.is_integer(): return int(v)
        return v
    return json.dumps([kind,normalized(args)],ensure_ascii=False,sort_keys=True)


class EconomicAI:
    def compile_economy(self,state,context,decision):
        result=copy.deepcopy(decision); review=result.get('economic_review')
        if not isinstance(result.get('actions'),list) or len(result['actions'])>12: raise ValueError('Нужно не более 12 действий')
        if not isinstance(review,dict) or review.get('mode') not in ('execute','negotiate','deceive','decline','none'): raise ValueError('Нужен economic_review с execute/negotiate/deceive/decline/none')
        if not isinstance(review.get('reason'),str) or len(review['reason'].strip())<20: raise ValueError('Объясни конкретную выгоду/отказ/обман и фактическое действие с ресурсами')
        orders=review.get('orders')
        if not isinstance(orders,list) or len(orders)>4: raise ValueError('economic_review.orders: до 4 казначейских приказов')
        for order in orders:
            if not isinstance(order,dict) or order.get('type') not in ECONOMIC_ACTIONS or not isinstance(order.get('args'),dict): raise ValueError('Экономический приказ должен иметь допустимые type,args')
            match=next((a for a in result['actions'] if signature(a)==signature(order)),None)
            if match is not None:
                for key in ('allow_risk','reason'):
                    if key in order['args']: match.setdefault('args',{})[key]=copy.deepcopy(order['args'][key])
            else:
                if len(result['actions'])>=12: raise ValueError('Казначейскому приказу нет места в 12 действиях: явно освободи место или измени намерение; ни одно действие не будет молча удалено')
                result['actions'].append(copy.deepcopy(order))
        financial=[a for a in result['actions'] if a.get('type',a.get('action')) in ECONOMIC_ACTIONS]
        if review['mode']=='execute' and not financial: raise ValueError('execute требует настоящего финансового действия; письмо «отправляю» не переводит ресурс')
        if review['mode']=='none' and financial: raise ValueError('В actions есть экономические действия: выбери соответствующий mode, а не none')
        for action in financial:
            kind=action.get('type',action.get('action')); args=action.get('args',{})
            if kind=='accept_trade':
                offer=next((o for o in context.get('trade_offers',[]) if o['id']==args.get('offer_id')),None)
                if type(args.get('offer_id')) is not int or not offer or offer['partner']!=state.id: raise ValueError('accept_trade: выбери offer_id из входящих предложений, адресованных ТЕБЕ; продавец не принимает сделку за покупателя')
            if kind=='accept_exchange':
                offer=next((e for e in context.get('commerce',{}).get('exchanges',[]) if e['id']==args.get('exchange_id')),None)
                if type(args.get('exchange_id')) is not int or not offer or offer['partner']!=state.id: raise ValueError('accept_exchange: только входящий exchange_id адресата')
            if kind=='accept_supply':
                offer=next((e for e in context.get('modern',{}).get('supply_pacts',[]) if e['id']==args.get('pact_id')),None)
                if type(args.get('pact_id')) is not int or not offer or offer['partner']!=state.id: raise ValueError('accept_supply: только входящий pact_id адресата')
        review['compiled_orders']=copy.deepcopy(financial); result.pop('economic_review_required',None)
        return result

    def review_economy(self,state,context,decision):
        if decision.get('origin_patch') not in ('6.1','6.2','6.3','6.4','6.5','6.6','6.7','6.8','6.8.1','6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0','7.5.3'): return decision
        context=checked_context(state,context,decision); self.bind_actor(state.id); result=copy.deepcopy(decision)
        if self.config.get('decision_compiler',False):
            from .intelligence import normalize_decision
            result=normalize_decision(result,context)
        try: return self.compile_economy(state,context,result)
        except (ValueError,TypeError,KeyError) as exc: error=str(exc)
        from .brain import AutomaticRetry
        model=self.config.get('state_models',{}).get(state.id) or self.config.get('model')
        props=dict(economic_review=economic_review_schema(),actions=dict(type='array',maxItems=12,items=dict(type='object')))
        schema=dict(type='json_schema',json_schema=dict(name='treasury_review',strict=True,schema=dict(type='object',properties=props,required=list(props),additionalProperties=False)))
        prompt='Ты правитель '+state.name+'. Исправь только казначейскую часть и согласуй её с собственными письмами. Основные мысли, характер, дипломатия и стратегия уже сохранены; заново их не генерируй. Верни economic_review и actions до12. Настоящее согласие/перевод требует приказа; trade лишь предложение, accept_trade исполняет покупатель, transfer переводит сразу. Все эти действия без cell. Можно сознательно обмануть: mode=deceive допускает ложное письмо и отсутствие поставки, а advance/credit позволяет оставить уже полученную чужую часть через breach_exchange. Не превращай обман в принудительное честное исполнение. Не принимай своё предложение за адресата. orders дополняются в actions без двойного исполнения. Сохрани полезные прежние приказы и выбранную стройку; при переполнении явно выбери до12 итоговых действий. Причины по-русски. Только JSON.'
        previous=self.active; self.active='Казначейство · '+state.name
        from .intelligence import REVIEW_GUIDANCE,action_schema
        prompt+=REVIEW_GUIDANCE
        if self.config.get('decision_compiler',False):
            props['economic_review']['properties']['orders']['items']=action_schema(ECONOMIC_ACTIONS,context)
            props['actions']['items']=action_schema(context.get('rules',{}).get('action_prices',ECONOMIC_ACTIONS),context)
        try:
            for _ in range(max(1,int(self.config.get('decision_repair_attempts',3)))):
                payload=dict(identity=dict(id=state.id,name=state.name),private_owner=state.id,day=context['day'],stocks=context['stocks'],commerce=context.get('commerce'),trade_offers=context.get('trade_offers'),trade_analysis=context.get('trade_analysis'),decision_support=context.get('decision_support'),supply_pacts=context.get('modern',{}).get('supply_pacts',[]),own_letters=result.get('diplomacy'),actions=result['actions'],construction_review=result.get('construction_review'),construction=context.get('construction'),economic_review=result.get('economic_review'),error=error,_response_schema=schema)
                update=self.complete(prompt,payload,model)
                if isinstance(update.get('economic_review'),dict): result['economic_review']=update['economic_review']
                if isinstance(update.get('actions'),list): result['actions']=update['actions']
                try:
                    compiled=self.compile_economy(state,context,result)
                    if compiled.get('construction_review',{}).get('choice')=='build': compiled=self.compile_construction(context,compiled)
                    self.validate_decision(compiled,state,context); return self.russify(compiled,model)
                except (ValueError,TypeError,KeyError) as exc: error=str(exc); self.emit('status','Уточняем только казначейские приказы: '+error)
            raise AutomaticRetry('Казначейство требует уточнения; основной ответ сохранён, повтор через 5 секунд.')
        finally: self.active=previous
