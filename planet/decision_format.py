"""Constrain final JSON structure without lowering the model's reasoning budget."""
from .deliberation import supplement_schema,needed_reviews


def decision_schema(state,context,actions,deep=True,strict_actions=False):
    rivals=[s['id'] for s in context.get('states',[]) if s['id']!=state.id and not s.get('eliminated')]
    extras=supplement_schema(needed_reviews(context),deep,rivals=rivals)['json_schema']['schema']['properties']
    string=dict(type='string',minLength=1,maxLength=64000)
    properties=dict(thinking=string,notes=string,plan=string)
    properties['learning_notes']=dict(type=['string','null'] if context.get('learning',{}).get('notes') else 'string',minLength=30,maxLength=8000,description='Собственная проверяемая стратегия по наградам: гипотеза, условие, действия, риск, результат, следующий эксперимент. null сохраняет старые заметки; в первом решении нужна стратегия.')
    from .learning import review_schema
    properties['learning_review']=review_schema(context)
    if deep: properties['strategic_assessment']=extras['strategic_assessment']
    properties['relation_reviews']=extras['relation_reviews']
    properties['construction_review']=construction_review_schema(context)
    from .economic_ai import economic_review_schema
    properties['economic_review']=economic_review_schema()
    if context.get('military',{}).get('enemies'):
        from .military_ai import military_schema
        properties['military_response']=military_schema(context['day'])
    properties['diplomacy']=dict(type='array',minItems=1,maxItems=8,items=dict(type='object',properties=dict(to=dict(type='string',enum=['all']+rivals),text=dict(type='string',minLength=1,maxLength=4000)),required=['to','text'],additionalProperties=False))
    if strict_actions:
        from .intelligence import action_schema
        from .commerce import ECONOMIC_ACTIONS
        properties['notes']={**string,'type':['string','null']}
        properties['plan']={**string,'type':['string','null']}
        properties['economic_review']['properties']['orders']['items']=action_schema(ECONOMIC_ACTIONS,context)
        if 'military_response' in properties:
            from .operation_support import MILITARY_ACTIONS
            properties['military_response']['properties']['orders']['items']=action_schema(MILITARY_ACTIONS,context)
        item=action_schema(actions,context)
    else: item=dict(type='object',properties=dict(type=dict(type='string',enum=list(actions)),args=dict(type='object')),required=['type','args'],additionalProperties=False)
    properties['actions']=dict(type='array',maxItems=12,items=item)
    return dict(type='json_schema',json_schema=dict(name='state_decision',strict=True,schema=dict(type='object',properties=properties,required=list(properties),additionalProperties=False)))


def construction_review_schema(context):
    ids=[p['project_id'] for p in context.get('construction',{}).get('projects',[])]
    result=dict(type='object',properties=dict(choice=dict(type='string',enum=['build','save','defer']),project_id=dict(enum=ids+[None]),reason=dict(type='string',minLength=20,maxLength=1500),revisit_day=dict(type='integer',minimum=context['day'],maximum=context['day']+3)),required=['choice','project_id','reason','revisit_day'],additionalProperties=False)
    result['anyOf']=[dict(properties=dict(choice=dict(enum=['save','defer']),project_id=dict(type='null')))]
    if ids:result['anyOf'].append(dict(properties=dict(choice=dict(enum=['build']),project_id=dict(enum=ids))))
    return result
