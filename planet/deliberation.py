"""Short accountable strategic conclusions, validated alongside the main decision."""
import re

DEEP_RULES='''
ПАТЧ 5.2 — РЕАЛЬНАЯ БОРЬБА ЗА ВЕЛИЧИЕ.
Конечная цель — относительное превосходство и самостоятельность государства: богатеть вместе со всеми недостаточно, если соперник растёт быстрее и навязывает тебе волю. Старые миролюбивые notes — память характера, а не запрет изменить политику. Сохраняй индивидуальность, но не превращай каждую страну в безусловного пацифиста.
strategic_brief — проверяемые расчёты: запасы через3/7 дней при неизменных условиях, выполнимый рост, исследования, локальные варианты нападения, ошибки прошлого исполнения. Для settle бери свободную координату из settlement_sites и не превышай affordable_settlers_now. Для research бери id из researchable_now; уже исследованное из tech повторять нельзя. Не путай оценку будущего с уже доступными ресурсами. Чужие скрытые запасы и намерения неизвестны.
Каждый день сопоставь минимум3 разных курса с выгодой, риском и ответом соперника. При общей границе или войне один вариант обязательно war: оцени настоящую цель, стоимость, локальный бой, общий баланс и сюзеренов. Если война сейчас выгодна, переходи от слов к declare_war и move, готовь подкрепления. Если нет — назови конкретный барьер и срок/условие перехода к давлению, а не бесконечное «сотрудничество ради мира».
Завоевание оценивай относительно соперника: это и наша добыча, и потерянный им источник дохода (relative_resource_swing). Захват ключевой шахты или лаборатории может изменить баланс сильнее нейтральной клетки. Но учитывай новых жителей, их содержание и риск контрудара; пустой гарнизон одной клетки не означает слабость всего государства.
Коварство должно иметь цель и механизм. Допустимы ложное успокоение перед ударом, временная коалиция против лидера, разрыв невыгодного пакта, завышенная цена для зависимого покупателя, прекращение поставок, вассальный ультиматум, обещание ради реальной уступки с последующим нарушением. Для каждого замысла учитывай ответ противника, цену разоблачения, альтернативных поставщиков и путь отхода. Не избегай выгодного обмана из-за желания сохранить дружбу: обида и вражда — допустимые издержки влияния. Коварный план должен дать реальный выигрыш, а не только громкие слова; используй действующие авансы, кредит, сознательную неуплату и срыв поставок. В private_intent описывай только действие относительно выбранного соперника: не упоминай имя собственной страны в этом поле, нашу выгоду запиши в objective/gain. Так не смешаются роли.
Вассалитет реален: offer_vassalage {partner,tribute_percent:10..40,duration:5..50,reason} предлагает партнёру стать ТВОИМ вассалом. accept_vassalage {offer_id,reason} принимает адресованный тебе договор: ТЫ сохраняешь армию и земли, но платишь дань и ограничен во внешней войне. Сюзерен автоматически вступает в формальную войну при нападении на вассала; для реальной помощи нужны его приказы. rebel {} прекращает собственный вассалитет и начинает войну с сюзереном. release_vassal {partner} освобождает твоего вассала. Вложенных вассалов нет. Не соглашайся на подчинение только ради дружбы: сравни сохранение страны, дань, защиту и перспективу восстания.
pledge {partner,kind:delivery|non_aggression,duration:1..10,public:true|false,resource,amount:1..1000} регистрирует проверяемое обещание. delivery требует дальнейшего реального transfer или продажи trade/accept_trade до срока; одна поставка не закрывает два одинаковых обещания. non_aggression не блокирует нападение программно, но твоя агрессия нарушает обещание. Можно сознательно обмануть ради превосходства, оценив последствия доверия. Частное обещание не раскрывается третьим странам; публичное нарушение влияет на их мнение. Обычное письмо остаётся словами, не автоматической поставкой.
Ответ — тот же основной JSON, дополнительно strategic_assessment и relation_reviews. Не раскрывай внутреннюю цепочку рассуждений: нужны краткие проверяемые выводы, конкретные альтернативы и намерения.
strategic_assessment={"objective":"Измеримая цель","horizon_days":5,"alternatives":[{"mode":"development","gain":"Выгода","risk":"Риск","opponent_response":"Ответ соперника"},{"mode":"war","gain":"Выгода","risk":"Риск","opponent_response":"Ответ соперника"},{"mode":"economic_pressure","gain":"Выгода","risk":"Риск","opponent_response":"Ответ соперника"}],"chosen":"development","risk_limits":{"min_food_days":3,"money_reserve":30,"stop_condition":"Когда сменить курс"},"rival_plan":{"partner":"state_N","method":"containment","phase":"preparation","leverage":"Реальный рычаг","public_position":"Что говорим партнёру","private_intent":"Чего хотим сами","trigger":"Когда усиливаем давление","fallback":"Запасной вариант"},"success_metric":"Проверяемый результат"}.
alternatives —3..5 разных mode из development/war/economic_pressure/vassalage/coalition/defence. chosen — один из рассмотренных. rival_plan.method: war/economic_pressure/vassalage/coalition/containment/none; phase: preparation/pressure/offensive/consolidation. Пока есть соперники, указывай существующего партнёра, исключая себя и выбывших; none и partner=null допустимы только без соперников. horizon_days:3..10. Условия риска — собственные пределы, не право создать деньги из ничего.
relation_reviews — объект {"state_N":{"trust":0,"stance":"neutral","trade_policy":"normal","memo":"Краткая оценка по-русски"}}. Заполни партнёров из required_relation_reviews в этом же ответе. Это экономит отдельные запросы, но не убирает досье. trust:-100..100; stance:neutral/friend/rival/enemy; trade_policy:normal/preferred/avoid. Не придумывай фактов. Чужие private_intent и досье не доступны тебе.
'''

MODES={'development','war','economic_pressure','vassalage','coalition','defence'}


def supplement_schema(peers,assessment=True,fields=None,rivals=None):
    def obj(properties): return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
    text=dict(type='string',minLength=5,maxLength=4000)
    profile=obj(dict(trust=dict(type='integer',minimum=-100,maximum=100),stance=dict(type='string',enum=['neutral','friend','rival','enemy']),trade_policy=dict(type='string',enum=['normal','preferred','avoid']),memo=text))
    properties=dict(relation_reviews=obj({peer:profile for peer in peers}))
    if assessment:
        alternative=obj(dict(mode=dict(type='string',enum=sorted(MODES)),gain=text,risk=text,opponent_response=text))
        plan=obj(dict(partner=dict(type=['string','null']),method=dict(type='string',enum=['war','economic_pressure','vassalage','coalition','containment','none']),phase=dict(type='string',enum=['preparation','pressure','offensive','consolidation']),leverage=text,public_position=text,private_intent=text,trigger=text,fallback=text))
        plan['properties']['private_intent']={**text,'description':'Частная конечная цель относительно выбранного соперника; 3–5 этапов кампании и измеримые условия перехода. Не раскрывать в письмах.'}
        plan['properties']['trigger']={**text,'description':'Наблюдаемый сигнал следующего этапа, срок проверки; отдельно факт и предположение.'}
        plan['properties']['fallback']={**text,'description':'Лучший ответ соперника, наша контрмера, предел потерь и путь отхода.'}
        if rivals is not None: plan['properties']['partner']=dict(enum=list(rivals) if rivals else [None])
        properties['strategic_assessment']=obj(dict(objective=text,horizon_days=dict(type='integer',minimum=3,maximum=10),alternatives=dict(type='array',minItems=3,maxItems=5,items=alternative),chosen=dict(type='string',enum=sorted(MODES)),risk_limits=obj(dict(min_food_days=dict(type='number',minimum=0,maximum=30),money_reserve=dict(type='number',minimum=0,maximum=1e9),stop_condition=text)),rival_plan=plan,success_metric=text))
        if fields:
            properties['strategic_assessment']=obj({key:value for key,value in properties['strategic_assessment']['properties'].items() if key in fields})
    return dict(type='json_schema',json_schema=dict(name='strategic_supplement',strict=True,schema=obj(properties)))


def needed_reviews(context):
    result=[]; day=context['day']
    active={s['id'] for s in context.get('states',[]) if not s.get('eliminated')}
    for peer,record in context.get('relations',{}).items():
        if peer not in active: continue
        reviewed=record.get('last_review_day')
        important=any(f.get('day') is not None and reviewed is not None and f['day']>=reviewed and f['kind'] in ('war','betrayal','trade','embargo','territory_loss','vassalage','promise_broken','rebellion','supply_default','supply_cancelled','supply_signed','exchange_betrayal','debt_repudiated','credit_exposure') for f in record.get('facts',[]))
        if not record.get('memo') or reviewed is None or day-reviewed>=5 or important: result.append(peer)
    return result


def validate_assessment(result,state,context):
    value=result.get('strategic_assessment')
    if not isinstance(value,dict): raise ValueError('Нужен strategic_assessment с сравнением3 вариантов и частным планом')
    def text(obj,key):
        if not isinstance(obj.get(key),str) or len(obj[key].strip())<5 or len(obj[key])>4000: raise ValueError('Нужен содержательный текст: '+key)
    for key in ('objective','success_metric'): text(value,key)
    if type(value.get('horizon_days')) is not int or not 3<=value['horizon_days']<=10: raise ValueError('horizon_days:3..10')
    alternatives=value.get('alternatives')
    if not isinstance(alternatives,list) or not 3<=len(alternatives)<=5: raise ValueError('Нужно3..5 стратегических альтернатив')
    modes=set()
    for alternative in alternatives:
        if not isinstance(alternative,dict) or not isinstance(alternative.get('mode'),str) or alternative['mode'] not in MODES: raise ValueError('Неверный mode альтернативы')
        modes.add(alternative['mode'])
        for key in ('gain','risk','opponent_response'): text(alternative,key)
    if len(modes)!=len(alternatives) or not isinstance(value.get('chosen'),str) or value['chosen'] not in modes: raise ValueError('Альтернативы должны различаться, chosen — один из рассмотренных mode')
    if (context.get('strategy',{}).get('border_targets') or any(r.get('at_war') for r in context.get('relations',{}).values())) and 'war' not in modes: raise ValueError('При общей границе/войне обязательно оцени вариант war, даже если выбираешь другой курс')
    limits=value.get('risk_limits')
    if not isinstance(limits,dict): raise ValueError('Нужны risk_limits')
    if type(limits.get('min_food_days')) not in (int,float) or not 0<=limits['min_food_days']<=30: raise ValueError('min_food_days:0..30')
    if type(limits.get('money_reserve')) not in (int,float) or not 0<=limits['money_reserve']<=1e9: raise ValueError('Некорректный money_reserve')
    text(limits,'stop_condition')
    plan=value.get('rival_plan'); peers={s['id'] for s in context.get('states',[]) if s['id']!=state.id and not s.get('eliminated')}
    if not isinstance(plan,dict) or plan.get('method') not in ('war','economic_pressure','vassalage','coalition','containment','none'): raise ValueError('Нужен rival_plan с допустимым method')
    if plan.get('phase') not in ('preparation','pressure','offensive','consolidation'): raise ValueError('Нужна фаза rival_plan.phase')
    if peers and (not isinstance(plan.get('partner'),str) or plan['partner'] not in peers or plan['method']=='none'): raise ValueError('Нужна конкретная политика относительно действующего соперника')
    if not peers and plan.get('partner') is not None: raise ValueError('Без соперников partner=null')
    for key in ('leverage','public_position','private_intent','trigger','fallback'): text(plan,key)
    own_stem=re.escape(state.name.lower().rstrip('аыяь'))
    if peers and re.search(r'\b'+own_stem+r'\w*',plan['private_intent'].lower()):
        raise ValueError('rival_plan: перепутана собственная страна. Мы '+state.name+'; целью ослабления должен быть соперник, а не мы сами')
    reviews=result.get('relation_reviews',{})
    if not isinstance(reviews,dict): raise ValueError('relation_reviews должен быть объектом')
    explicit={a.get('args',{}).get('partner') for a in result.get('actions',[]) if a.get('type')=='relationship' and isinstance(a.get('args',{}).get('memo'),str) and a['args']['memo'].strip()}
    for peer in context.get('required_relation_reviews',[]):
        if peer in explicit: continue
        item=reviews.get(peer)
        if not isinstance(item,dict): raise ValueError('Заполни досье в основном ответе: '+peer)
        if type(item.get('trust')) is not int or not -100<=item['trust']<=100 or item.get('stance') not in ('neutral','friend','rival','enemy') or item.get('trade_policy') not in ('normal','preferred','avoid'): raise ValueError('Неверная структура досье '+peer)
        text(item,'memo')


def narrative_fields(result):
    fields={}
    if isinstance(result.get('learning_notes'),str):fields['learning_notes']=result['learning_notes']
    if isinstance(result.get('learning_review'),dict):
        for key in ('hypothesis','stop_condition','next_action'):
            if isinstance(result['learning_review'].get(key),str):fields['learning_review.'+key]=result['learning_review'][key]
    def walk(value,path):
        if isinstance(value,dict):
            for key,item in value.items():
                if key not in ('mode','chosen','method','phase','partner'): walk(item,path+'.'+key)
        elif isinstance(value,list):
            for i,item in enumerate(value): walk(item,path+'.'+str(i))
        elif isinstance(value,str): fields[path]=value
    if isinstance(result.get('strategic_assessment'),dict): walk(result['strategic_assessment'],'strategic_assessment')
    if isinstance(result.get('construction_review'),dict) and isinstance(result['construction_review'].get('reason'),str): fields['construction_review.reason']=result['construction_review']['reason']
    if isinstance(result.get('economic_review'),dict) and isinstance(result['economic_review'].get('reason'),str): fields['economic_review.reason']=result['economic_review']['reason']
    if isinstance(result.get('military_response'),dict) and isinstance(result['military_response'].get('reason'),str): fields['military_response.reason']=result['military_response']['reason']
    reviews=result.get('relation_reviews',{})
    for peer,item in (reviews.items() if isinstance(reviews,dict) else []):
        if isinstance(item,dict) and isinstance(item.get('memo'),str): fields[f'relation_reviews.{peer}.memo']=item['memo']
    return fields
