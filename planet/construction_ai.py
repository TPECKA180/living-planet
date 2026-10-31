"""Turn an explicitly selected legal project into a real action, never free spending."""
import copy
from .isolation import checked_context
from .decision_format import construction_review_schema


class ConstructionAI:
    def compile_construction(self,context,decision):
        result=copy.deepcopy(decision); review=result.get('construction_review')
        if not isinstance(review,dict): raise ValueError('Нужна оценка строительства с выбором проекта либо конкретной отсрочкой')
        if review.get('choice') not in ('build','save','defer'): raise ValueError('choice: build/save/defer')
        if not isinstance(review.get('reason'),str) or len(review['reason'].strip())<20: raise ValueError('Нужно конкретное обоснование стройки/отсрочки')
        if review['choice']!='build': result.pop('construction_review_required',None); return result
        project_id=review.get('project_id')
        if project_id is None:
            if any(a.get('type')=='build' for a in result['actions']): result.pop('construction_review_required',None); return result
            raise ValueError('Выбрано build, но нет ни project_id, ни настоящего build в actions. Выбери конкретный проект, а не обещание построить потом.')
        project=next((p for p in context.get('construction',{}).get('projects',[]) if p['project_id']==project_id),None)
        if project is None: raise ValueError('Проект отсутствует в текущем собственном каталоге')
        action=dict(type='build',args=dict(cell=list(project['cell']),building=project['building'],level=project['level']))
        duplicate=any(a.get('type')=='build' and a.get('args',{}).get('cell')==action['args']['cell'] and a.get('args',{}).get('building',a.get('args',{}).get('type'))==project['building'] and a.get('args',{}).get('level',1)==project['level'] for a in result['actions'])
        if not duplicate:
            if any(a.get('type')=='build' and a.get('args',{}).get('cell')==action['args']['cell'] for a in result['actions']):
                raise ValueError('Выбранный проект конфликтует с другой стройкой на той же клетке. Согласуй проект и actions; второе здание не будет добавлено.')
            if len(result['actions'])>=12: raise ValueError('Для выбранного проекта нет места в12 действиях. Верни не более11 остальных действий либо явно отложи проект.')
            result['actions'].append(action)
        review['compiled_action']=action; result.pop('construction_review_required',None)
        return result

    def review_construction(self,state,context,decision):
        if decision.get('origin_patch') not in ('5.3','6.0','6.1','6.2','6.3','6.4','6.5','6.6','6.7','6.8','6.8.1','6.8.2','6.8.3','6.8.4','7.0','7.0.1','7.5.0'): return decision
        context=checked_context(state,context,decision); self.bind_actor(state.id)
        result=copy.deepcopy(decision)
        if self.config.get('decision_compiler',False):
            from .intelligence import normalize_decision
            result=normalize_decision(result,context)
        try: return self.compile_construction(context,result)
        except ValueError as exc: error=str(exc)
        model=self.config.get('state_models',{}).get(state.id) or self.config.get('model')
        properties=dict(construction_review=construction_review_schema(context))
        # Only when the12-slot limit is the problem may the model explicitly revise its own action order.
        revise_actions=len(result.get('actions',[]))>=12
        if revise_actions: properties['actions']=dict(type='array',maxItems=11,items=dict(type='object'))
        schema=dict(type='json_schema',json_schema=dict(name='construction_choice',strict=True,schema=dict(type='object',properties=properties,required=list(properties),additionalProperties=False)))
        prompt='Ты правитель '+state.name+' ('+state.id+'''). Исправь только решение о стройке. Твои основной план, переписка и память уже сохранены. У тебя есть точный каталог проектов с местами, ценами и отдачей. choice=build означает СТРОИТЬ СЕГОДНЯ: выбери project_id из каталога; движок добавит настоящий платный build в конец твоего списка, если ты ещё не перечислил его сам. Это не бесплатное здание. При отсрочке выбери defer/save и объясни конкретную причину. Не путай выбор build с обещанием когда-нибудь построить. Если нужно освободить место среди12 действий, явно выбери до11 остальных действий, не меняя их смысл произвольно. Только JSON по схеме, пояснения по-русски.'''
        previous=self.active; self.active='Строительный проект · '+state.name
        from .intelligence import REVIEW_GUIDANCE,action_schema
        prompt+=REVIEW_GUIDANCE
        if revise_actions and self.config.get('decision_compiler',False):
            properties['actions']['items']=action_schema(context.get('rules',{}).get('action_prices',[]),context)
        try:
            for _ in range(max(1,int(self.config.get('decision_repair_attempts',3)))):
                payload=dict(identity=dict(id=state.id,name=state.name),day=context['day'],stocks=context.get('stocks'),economy=context.get('economy'),construction=context.get('construction'),decision_support=context.get('decision_support'),notes=result.get('notes'),plan=result.get('plan'),current_actions=result.get('actions'),old_review=result.get('construction_review'),error=error,_response_schema=schema)
                update=self.complete(prompt,payload,model)
                if isinstance(update.get('construction_review'),dict): result['construction_review']=update['construction_review']
                if revise_actions and isinstance(update.get('actions'),list): result['actions']=update['actions']
                try:
                    compiled=self.compile_construction(context,result); self.validate_decision(compiled,state,context)
                    return self.russify(compiled,model)
                except (ValueError,TypeError,KeyError) as exc:
                    error=str(exc); self.emit('status','Уточняем только выбор строительного проекта: '+error)
            from .brain import AutomaticRetry
            raise AutomaticRetry('Выбор стройки требует уточнения. Основной ответ сохранён; повтор через5 секунд.')
        finally: self.active=previous
