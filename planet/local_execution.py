"""No-inference command preparation. Invalid commands face the ordinary engine."""
import copy,re
from .intelligence import normalize_decision
from .economic_ai import signature
from .commerce import ECONOMIC_ACTIONS
from .execution_ai import preview_orders
from .isolation import checked_context
from .learning import decision_signature

def prepare_locally(world,state,decision,config):
    context=checked_context(state,world.context(state,config),decision)
    result=copy.deepcopy(decision);issues=[];fixes=[]
    def issue(kind,message):issues.append(dict(type=kind,success=False,message=message))
    for key in ('notes','plan'):
        if not isinstance(result.get(key),str) or not result[key].strip():result[key]=getattr(state,key)
    if not isinstance(result.get('thinking'),str):result['thinking']='Локальная подготовка сохранённых приказов; исходный характер сохранён.'
    if not isinstance(result.get('actions'),list):
        issue('actions','Некорректный список действий: ресурсные операции не выдумываются');result['actions']=[]
    try:result=normalize_decision(result,context)
    except (ValueError,TypeError,KeyError,AttributeError):issue('normalization','Не удалось нормализовать часть параметров; их проверит движок')
    actions=result['actions']
    if len(actions)>12:
        issue('action_limit',f'Превышен лимит12: дополнительные {len(actions)-12} приказов не поставлены в очередь');actions=actions[:12];result['actions']=actions
    review=result.get('construction_review')
    if isinstance(review,dict) and review.get('choice')=='build':
        project_id=review.get('project_id')
        project=next((p for p in context.get('construction',{}).get('projects',[]) if p['project_id']==project_id),None)
        # Decode only an explicitly selected own project, never choose a new site.
        if project is None and isinstance(project_id,str):
            match=re.fullmatch(re.escape(state.id)+r'/([a-z_]+)/(-?\d+):(-?\d+)/L(\d+)',project_id)
            if match:project=dict(building=match[1],cell=[int(match[2]),int(match[3])],level=int(match[4]))
        if project:
            action=dict(type='build',args={key:copy.deepcopy(project[key]) for key in ('cell','building','level')})
            duplicate=any(isinstance(a,dict) and a.get('type')=='build' and isinstance(a.get('args'),dict) and a['args'].get('cell')==action['args']['cell'] and a['args'].get('building',a['args'].get('type'))==action['args']['building'] and a['args'].get('level',1)==action['args']['level'] for a in actions)
            if not duplicate:
                if len(actions)<12:actions.append(action);fixes.append('Добавлен только явно выбранный строительный проект')
                else:issue('build','Выбранному проекту не хватило места в12 приказах; прочие действия сохранены')
        elif not any(isinstance(a,dict) and a.get('type')=='build' for a in actions):issue('build','Нет конкретного проекта или build: из одного обещания постройка не создаётся')
    treasury=result.get('economic_review')
    if isinstance(treasury,dict):
        orders=treasury.get('orders',[])
        if not isinstance(orders,list):issue('economic_orders','Казначейские orders должны быть списком');orders=[]
        for order in orders[:4]:
            if not isinstance(order,dict) or order.get('type') not in ECONOMIC_ACTIONS or not isinstance(order.get('args'),dict):issue('economic_orders','Некорректный казначейский приказ не добавлен');continue
            try:duplicate=next((a for a in actions if signature(a)==signature(order)),None)
            except (ValueError,TypeError):duplicate=None
            if duplicate is not None:
                for key in ('reason','allow_risk'):
                    if key in order['args']:duplicate['args'][key]=copy.deepcopy(order['args'][key])
            elif len(actions)<12:actions.append(copy.deepcopy(order))
            else:issue(order['type'],'Казначейскому приказу не хватило места в12 действиях')
        if len(orders)>4:issue('economic_orders','Дополнительные казначейские приказы сверх4 не добавлены')
    if not isinstance(result.get('diplomacy'),list):result['diplomacy']=[];issue('diplomacy','Некорректный список сообщений не отправлен')
    if not isinstance(result.get('relation_reviews',{}),dict):result['relation_reviews']={};issue('relations','Некорректное досье не применяется')
    if result.get('strategic_assessment'):
        from .deliberation import validate_assessment
        try:validate_assessment(result,state,context)
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            result['unvalidated_strategic_assessment']=result.pop('strategic_assessment');result['strategic_review_required']=str(exc)
            issue('strategy','Неполный разбор сохранён как черновик; прежняя стратегия и реальные приказы не заменяются')
    if result.get('military_response') is not None and not isinstance(result['military_response'],dict):result.pop('military_response');issue('military_response','Неверный военный комментарий не является приказом')
    if isinstance(result.get('military_response'),dict) and not isinstance(result['military_response'].get('reason'),str):result['military_response']['reason']=''
    military=context.get('military',{})
    if military.get('enemies') and not military.get('combat_count') and military.get('recruitment_options'):
        recruits=[a for a in actions if isinstance(a,dict) and (a.get('type')=='recruit_modern' or a.get('type')=='unit' and a.get('args',{}).get('unit',a.get('args',{}).get('type'))=='army')]
        if not recruits:issue('war_without_army','Идёт война, боевых частей нет, доступен платный найм, но приказ unit/recruit_modern не выбран. На следующем ходе сначала оцени создание армии; письмо и движение army не нанимают войска.')
    result['local_preparation']=dict(day=world.day,mode='local',issues=issues,fixes=fixes,
        note='Обоснования и язык не являются условием исполнения. Цены, владение, технологии, война и ресурсы проверяются обычным движком; невалидные действия не получают поблажек.')
    result['execution_preflight']=preview_orders(world,state.id,result)
    result['execution_ready']=dict(day=world.day,signature=decision_signature(result))
    return result
