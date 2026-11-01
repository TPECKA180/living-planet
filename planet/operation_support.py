"""Executable options, never inferred consent from diplomatic prose."""
import copy,math

MILITARY_ACTIONS={'unit','recruit_modern','move','army','explore','hold','bombard','embark','disembark','missile_strike','declare_war','build','fortify','repair_wall','reinforce'}

def treasury_options(context):
    sid=context['state'];stocks=context.get('stocks',{});options=[]
    for offer in context.get('trade_offers',[]):
        if offer.get('partner')!=sid or offer.get('status')!='open':continue
        total=offer['amount']*offer['price']
        analysis=next((a for a in context.get('trade_analysis',[]) if a['offer_id']==offer['id']),{})
        options.append(dict(action=dict(type='accept_trade',args=dict(offer_id=offer['id'])),total_payment=total,
            enough_money=stocks.get('money',0)>=total,need=analysis.get('need'),risk_flags=analysis.get('risk_flags',[]),
            rule='Это только шаблон. Для настоящего согласия скопируй в economic_review.orders/actions; для сознательного блефа mode=deceive, перевода нет.'))
    for key,kind,arg in (('exchanges','accept_exchange','exchange_id'),):
        for offer in context.get('commerce',{}).get(key,[]):
            if offer.get('partner')==sid and offer.get('status')=='open':options.append(dict(action=dict(type=kind,args={arg:offer['id']}),mode=offer.get('mode'),give=offer.get('give'),receive=offer.get('receive')))
    for pact in context.get('modern',{}).get('supply_pacts',[]):
        if pact.get('partner')==sid and pact.get('status')=='open':options.append(dict(action=dict(type='accept_supply',args=dict(pact_id=pact['id'])),resource=pact.get('resource'),amount=pact.get('amount'),price=pact.get('price')))
    # Public proposal examples use only the actor's own surplus, not private peer stocks.
    peers=[s['id'] for s in context.get('states',[]) if s['id']!=sid and not s.get('eliminated')]
    for resource,item in context.get('economy',{}).get('resources',{}).items():
        if resource=='money' or item.get('net',-1)<0:continue
        surplus=stocks.get(resource,0)-2*item.get('reserve',0)
        if surplus<20 or not peers:continue
        amount=min(100,int(surplus//4))
        options.append(dict(action=dict(type='trade',args=dict(partner=peers[0],resource=resource,amount=amount,price=1)),
            draft=True,rule='Пример предложения из собственного избытка: сам выбери партнёра, объём и выгодную цену. Без accept_trade товар не перейдёт.'))
        if sum(o.get('draft',False) for o in options)>=3:break
    return options[:16]

def offensive_options(world,state,units):
    borders=world.strategic_context(state)['border_targets'];targets=[]
    for peer,rows in borders.items():
        if world.war_permission(state.id,peer):continue
        for row in rows:targets.append((peer,row))
    if not targets:return []
    nearest=lambda u:min(abs(u['cell'][0]-r['cell'][0])+abs(u['cell'][1]-r['cell'][1]) for _,r in targets)
    options=[]
    for unit in sorted((u for u in units if not u.get('embarked_on')),key=nearest)[:8]:
        candidates=sorted(targets,key=lambda pair:(not world.at_war(state.id,pair[0]),abs(unit['cell'][0]-pair[1]['cell'][0])+abs(unit['cell'][1]-pair[1]['cell'][1]),pair[1]['defender_strength']))
        for peer,row in candidates[:3]:
            war=world.at_war(state.id,peer)
            route=world.find_route(unit,row['cell'],assume_war_with=None if war else peer)
            if not route:continue
            strength=world.effective_strength(unit);defense=row['defender_strength']+row['fortification']
            cost=sum(22 if world.cell(p).owner not in (None,state.id) else 2 for p in route)
            orders=[] if war else [dict(type='declare_war',args=dict(partner=peer,reason=f'Ограниченная операция за клетку {row["cell"]}; локальное соотношение {strength:g}/{defense:g}'))]
            orders.append(dict(type='move',args=dict(unit_id=unit['id'],target_cell=row['cell'])))
            options.append(dict(partner=peer,unit_id=unit['id'],target=row['cell'],orders=orders,at_war=war,
                our_strength=strength,observed_defense=defense,wall_hp=row['wall_hp'],minimum_route_cost=cost,
                days=math.ceil(len(route)/max(1,world.speed_for(state,unit['type']))),
                opportunity=(defense==0 or strength>=.8*defense) and state.stocks['money']>=min(cost,22*world.speed_for(state,unit['type'])),
                rule='При opportunity рассмотри ограниченное наступление без требования глобального превосходства. Риск, стены, снабжение и ответ врага остаются; решение и приказы выбираешь сам.'))
            break
    return options

def append_explicit_orders(result,issues,fixes):
    from .commerce import ECONOMIC_ACTIONS
    from .economic_ai import signature
    actions=result['actions']
    for section,allowed in (('economic_review',ECONOMIC_ACTIONS),('military_response',MILITARY_ACTIONS)):
        value=result.get(section)
        if not isinstance(value,dict):continue
        orders=value.get('orders',[])
        if not isinstance(orders,list):continue
        for order in orders[:4]:
            if not isinstance(order,dict) or order.get('type') not in allowed or not isinstance(order.get('args'),dict):continue
            if any(signature(a)==signature(order) for a in actions if isinstance(a,dict) and isinstance(a.get('args'),dict)):continue
            if len(actions)>=12:
                issues.append(dict(type='order_capacity',success=False,message=f'{section}: явному приказу не хватило места среди12; выбери приоритет в основном actions.'));continue
            actions.append(copy.deepcopy(order));fixes.append(f'Добавлен явный приказ {section}: '+order['type'])
