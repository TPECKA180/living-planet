"""Compile explicit intent and check the complete ordered command list on a disposable world."""
import copy
import re
from .construction_ai import ConstructionAI
from .economic_ai import EconomicAI
from .decision_format import construction_review_schema
from .economic_ai import economic_review_schema
from .intelligence import normalize_decision,validate_actions,action_schema
from .isolation import checked_context
from .rules import RuleError
from .military_ai import military_schema,validate_military,MILITARY_RULES,war_intent


def compile_orders(context,decision):
    result=normalize_decision(decision,context)
    if isinstance(result.get('construction_review'),dict):
        result=ConstructionAI().compile_construction(context,result)
    if isinstance(result.get('economic_review'),dict):
        actor=type('Actor',(),{'id':context['state']})()
        result=EconomicAI().compile_economy(actor,context,result)
    validate_actions(result,context)
    if len(result.get('actions',[]))>12: raise ValueError('После согласования всех разделов больше 12 приказов')
    return result


def preview_orders(world,sid,decision):
    from .engine import World
    sandbox=World.restore(world.data()); state=sandbox.state(sid)
    rows=[]
    for index,action in enumerate(decision.get('actions',[])):
        try:
            message=sandbox.execute(state,action)
            rows.append(dict(index=index,type=action.get('type'),success=True,message=message))
        except (RuleError,TypeError,KeyError,AttributeError,OverflowError) as exc:
            rows.append(dict(index=index,type=action.get('type') if isinstance(action,dict) else None,success=False,message=str(exc)))
    return dict(day=world.day,scope='Собственные приказы по порядку до чужих решений и движения войск; не гарантия результата общего хода',
                results=rows,failed=sum(not row['success'] for row in rows),stocks_after=copy.deepcopy(state.stocks))


def missing_today_build(decision):
    if any(a.get('type')=='build' for a in decision.get('actions',[]) if isinstance(a,dict)): return False
    review=decision.get('construction_review',{})
    correction=decision.get('execution_intent_correction',{})
    if review.get('choice') in ('save','defer') and correction.get('review')==review:
        return False
    texts=[decision.get('thinking',''),review.get('reason','')]
    for text in texts:
        if not isinstance(text,str): continue
        text=re.sub(r'\bне\s+(?:строю|строим|возвожу|возводим|построю|построим|построить|строить)\b','',text,flags=re.I)
        if re.search(r'\b(?:строю|строим|возвожу|возводим)\b|\bсегодня\b[^.!?\n]{0,100}\b(?:построю|построим|построить|строить)\b',text,re.I):return True
    return False


class ExecutionAI:
    def prepare_execution(self,world,state,decision):
        context=checked_context(state,world.context(state,self.config),decision)
        result=copy.deepcopy(decision); self.bind_actor(state.id)
        model=self.config.get('state_models',{}).get(state.id) or self.config.get('model')
        from .engine import PRICES
        props=dict(actions=dict(type='array',maxItems=12,items=action_schema(PRICES,context)),
                   construction_review=construction_review_schema(context),economic_review=economic_review_schema())
        from .commerce import ECONOMIC_ACTIONS
        props['economic_review']['properties']['orders']['items']=action_schema(ECONOMIC_ACTIONS,context)
        if war_intent(result,context):props['military_response']=military_schema(world.day)
        schema=dict(type='json_schema',json_schema=dict(name='execution_repair',strict=True,schema=dict(type='object',properties=props,required=list(props),additionalProperties=False)))
        limit=max(1,int(self.config.get('decision_repair_attempts',3)))
        for attempt in range(limit+1):
            try:
                result=compile_orders(context,result)
                report=preview_orders(world,state.id,result)
                if missing_today_build(result): raise ValueError('Заявлено строительство сегодня, но нет build: выбери настоящий проект или честно исправь причину отсрочки')
                if report['failed']: raise ValueError('Предварительное исполнение отклонило приказы: '+str([r for r in report['results'] if not r['success']]))
                validate_military(result,context)
                result['execution_preflight']=report
                return result
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                error=str(exc)
            if attempt==limit: break
            self.emit('status','Проверка исполнения · '+state.name+': '+error)
            keys=('identity','private_owner','state','day','size','stocks','tech','technology_catalog','action_sites','action_contracts',
                  'construction','military','naval','modern','trade_offers','trade_analysis','commerce','economy','rules','mobility','units')
            technical={k:context[k] for k in keys if k in context}
            touched=set()
            for action in result.get('actions',[]):
                for key in ('cell','target_cell'):
                    p=action.get('args',{}).get(key)
                    if isinstance(p,list) and len(p)==2 and all(type(v) is int for v in p):
                        touched.update((p[0]+dx,p[1]+dy) for dx in (-1,0,1) for dy in (-1,0,1))
            technical['map']=[row for row in context.get('map',[]) if tuple(row[:2]) in touched]
            payload=dict(technical,current_actions=result.get('actions',[]),
                         construction_review=result.get('construction_review'),economic_review=result.get('economic_review'),
                         own_plan=result.get('plan'),own_letters=result.get('diplomacy'),error=error,_response_schema=schema)
            prompt='''Ты технический советник своей страны. Исправь только исполнимость actions, construction_review и economic_review. Все прочие поля, характер, письма и политические намерения уже сохранены. Проверка исполнила собственные приказы ПО ПОРЯДКУ на копии мира и не списала реальные ресурсы. Согласуй общий бюджет, клетки, технологии, реальные цены, роли сделок и лимит 12. Стройка build в обзоре требует настоящего build; orders добавляются в actions. Если сначала нужна постройка лаборатории, поставь build перед research; если сначала нужен заём/поставка, соблюдай зависимости. Не удаляй полезный приказ молча: при невозможности объясни перенос в reason и revisit_day. Не выдумывай платежи из писем и не заменяй намеренный deceive честной передачей. Избегай повторов и исправляй конкретную ошибку. Можно явно пересмотреть проект/экономические приказы в пределах своей прежней цели, но нельзя распоряжаться чужим ходом. Чужие будущие поставки не гарантированы. Разговор сам не строит, предложение не означает принятие, move задаёт маршрут, а не мгновенную победу. Только JSON по схеме; объяснения по-русски.'''
            if war_intent(result,context):
                props['military_response']=military_schema(world.day)
                schema['json_schema']['schema']['required']=list(props)
                prompt+=MILITARY_RULES
            update=self.complete(prompt,payload,model)
            if not isinstance(update,dict): continue
            for key in props:
                if key in update: result[key]=copy.deepcopy(update[key])
            if isinstance(update.get('construction_review'),dict) and update['construction_review'].get('choice') in ('save','defer'):
                result['execution_intent_correction']=dict(review=copy.deepcopy(update['construction_review']),
                    note='Техническое уточнение: сегодняшняя стройка явно отложена; прежний текст не является фактом исполнения.')
        from .brain import AutomaticRetry
        retry=AutomaticRetry('Приказы '+state.name+' ещё не согласованы: '+error+'. Основной ответ сохранён; автоматический повтор без пропуска дня.')
        retry.repaired_decision=result;retry.owner=state.id
        raise retry
