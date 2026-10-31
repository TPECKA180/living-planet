"""Executable recruitment options and accountable wartime decisions, never free armies."""
from .modern_catalog import UNITS,BUILDINGS
import re

MILITARY_RULES='''
ПАТЧ 7.5.0 — ОБЯЗАТЕЛЬНО ПРОВЕРЯЙ СОЗДАНИЕ АРМИИ В ВОЙНУ. В начале каждого военного хода посчитай собственные combat_units и прочитай recruitment_options. Если боевых частей нет или фронту нужны подкрепления и найм доступен, первым вариантом рассматривай mobilize: добавь настоящий unit с unit="army" либо recruit_modern в actions. Не трать весь бюджет на второстепенную стройку/торговлю, оставив войну без войск. Один приказ с count=N может нанять доступную группу. Письмо «создам армию», действие army для перемещения и разведчик НЕ создают боевые части. Если сознательно не нанимаешь, укажи конкретный расчёт: бюджет с учётом снабжения/маршрута, силы и участок, препятствие или альтернативную операцию и срок пересмотра; общая фраза о мире или нехватке входных данных при переданных шаблонах не заменяет решения. Никто не создаёт и не оплачивает войска вместо тебя. Не устраивай бездумный найм при голоде: организуй оплату, металл, свободные клетки и снабжение реальными приказами.
ПАТЧ 6.8 — ВОЙНУ ВЕДУТ ПРИКАЗЫ. Объявление войны и грозное письмо не создают солдат, не захватывают клетки и не защищают границу. army как TYPE ДЕЙСТВИЯ — приказ ПЕРЕМЕЩЕНИЯ уже существующего unit_id. Для СОЗДАНИЯ обычной армии нужен unit {cell,unit:"army",strength:1..10}; выше5 требуется технология army. recruit_modern создаёт открытый современный тип по его цене, экипажу и снабжению. Бери готовые реальные шаблоны из military.recruitment_options, но суммируй их стоимость с остальными приказами. Каждый найм занимает свободную собственную сухопутную клетку; два юнита на одной клетке не появляются. Нет клетки — сначала перемести своё формирование и проверь порядок действий. Нет денег/металла/экипажа — поставь конкретную закупку/производство, укрепление или отход, а не повторяй пустое обещание мобилизации.
Военный минимум УДАЛЁН. Никто не наймёт войска вместо тебя. unit/recruit_modern с count=N создают группу без лимита двух; число ограничено ресурсами, экипажем и свободными клетками. Один такой приказ занимает одно место из12. Найм всей группы атомарный: если средств или мест не хватает, не нанимается никто. policy.unit_limit относится только к дежурным разведчикам и не ограничивает явный боевой найм. При войне сопоставь боевые части, силы врага, снабжение, резерв и сроки. Найми достаточную группу до второстепенных трат, если выгода оправданна. military_response mobilize/maneuver/fortify/hold/defer должен соответствовать приказам, маршруту или конкретному барьеру; пересмотр не позже двух дней. Меньшая общая армия допускает ограниченную операцию с локальным перевесом, но уверенность без расчёта не является преимуществом.
ПОГРАНИЧНАЯ ОБОРОНА. У общей границы оцени стены на вероятных направлениях вторжения и ценных проходах; башни — рядом с фронтом и гарнизоном, чтобы свой юнит реально удержал их полный день. Во время войны стены и башни на угрожаемом участке важнее декоративной стройки в тылу, если не срывают найм и снабжение. wall — преграда, армия её осаждает; tower не стена и не создаёт гарнизон. Полный день в tower даёт бонус со следующего дня; строительство и немедленный уход бонус не дают. Считай цену и место, не заполняй всю границу постройками без нужды и не оставляй армию без денег на движение. Важно защищать производство, подступы и резерв, а не только накапливать здания. Проверяй реальные action_results и фактический найм, а не считай план выполненным.
'''


def military_schema(day):
    return dict(type='object',properties=dict(choice=dict(type='string',enum=['mobilize','maneuver','fortify','hold','defer']),
        reason=dict(type='string',minLength=30,maxLength=1800),revisit_day=dict(type='integer',minimum=day,maximum=day+2),
        orders=dict(type='array',maxItems=4,items=dict(type='object',properties=dict(type=dict(type='string'),args=dict(type='object')),required=['type','args'],additionalProperties=False))),
        required=['choice','reason','revisit_day','orders'],additionalProperties=False)


def war_intent(decision,context):
    return bool(context.get('military',{}).get('enemies')) or any(a.get('type')=='declare_war' for a in decision.get('actions',[]) if isinstance(a,dict))


def validate_military(decision,context):
    military=context.get('military',{})
    if not war_intent(decision,context):return
    response=decision.get('military_response',{})
    if not isinstance(response,dict) or response.get('choice') not in ('mobilize','maneuver','fortify','hold','defer'):
        raise ValueError('Идёт война: нужен military_response с реальными приказами либо конкретной отсрочкой')
    if not isinstance(response.get('reason'),str) or len(response['reason'].strip())<30:
        raise ValueError('Военный ответ требует конкретной причины: силы, ресурсы, участок, действие или барьер')
    if type(response.get('revisit_day')) is not int or not context['day']<=response['revisit_day']<=context['day']+2:
        raise ValueError('Военную обстановку нужно пересмотреть не позднее двух дней')
    choice=response['choice'];actions=decision.get('actions',[])
    combat={u['id']:u for u in military.get('combat_units',[])}
    navy={u['id']:u for u in context.get('naval',{}).get('ships',[])}
    if choice=='defer':
        if re.search(r'(нет данных|данные отсутствуют|ожида\w* данны|ожида\w* полн\w* JSON)',response['reason'],re.I) and military.get('recruitment_options'):
            raise ValueError('Данные о войне, собственных войсках, ресурсах и вариантах найма переданы в military; отсутствие данных не объясняет отсрочку')
        return
    def actual(a):
        kind=a.get('type');args=a.get('args',{})
        if choice=='mobilize':return kind=='recruit_modern' or kind=='unit' and args.get('unit',args.get('type'))=='army'
        if choice=='maneuver':return (kind in ('move','army','explore','bombard','embark','disembark') and args.get('unit_id') in combat or kind in ('move','explore') and args.get('unit_id') in navy or kind=='missile_strike')
        building=args.get('building',args.get('type'));info=BUILDINGS.get(building,{})
        if choice=='fortify':return kind in ('fortify','repair_wall') or kind=='build' and (building in ('wall','tower') or info.get('barrier',0)>0 or info.get('armor',0)>0 or info.get('intercept',0)>0)
        return kind=='hold' and args.get('unit_id') in combat
    if any(actual(a) for a in actions):return
    if choice in ('maneuver','hold') and any((u.get('order') or {}).get('kind') in (('move','explore') if choice=='maneuver' else ('hold',)) for u in list(combat.values())+list(navy.values())):return
    raise ValueError('military_response='+choice+' не подкреплён подходящим реальным приказом; письмо не является действием')


class MilitaryPlanning:
    def military_context(self,state):
        enemies=[s.id for s in self.states if not s.eliminated and self.at_war(state.id,s.id)]
        units=[u for u in self.units if u['owner']==state.id and self.combat_unit(u)]
        own=self.positions(state.id)
        border=[p for p in own if any(self.cell(q).owner not in (None,state.id) and self.cell(q).terrain!='water' for q in self.adjacent(p))]
        hostile=[p for p in border if any(self.cell(q).owner in enemies for q in self.adjacent(p))]
        sites=[p for p in self.recruitment_sites(state) if not self.cell(p).radiation]
        front=hostile or border
        sites.sort(key=lambda p:min((abs(p[0]-q[0])+abs(p[1]-q[1]) for q in front),default=0))
        options=[]
        maximum=min(10 if 'army' in state.tech else 5,max(0,int(state.stocks['metal']//3)))
        if sites and state.stocks['money']>=self.unit_price(state) and maximum:
            for strength in sorted({1,maximum}):
                options.append(dict(action=dict(type='unit',args=dict(cell=list(sites[0]),unit='army',strength=strength)),
                    cost=dict(money=self.unit_price(state),metal=3*strength),requires='army только для силы выше5'))
        population=sum(self.cell(p).population for p in own)
        if sites and self.era_for(state)==2:
            for kind,info in UNITS.items():
                if info['tech'] not in state.tech:continue
                cost=self.modern_recruitment_cost(kind)
                if population-info['crew']>=2 and self.funds_available(state,cost):
                    options.append(dict(action=dict(type='recruit_modern',args=dict(cell=list(sites[0]),unit=kind)),cost=cost,crew=info['crew']))
        for option in options:
            maximum=min([len(sites)]+[int(state.stocks.get(k,0)//v) for k,v in option['cost'].items() if v>0])
            if option.get('crew'):maximum=min(maximum,max(0,(population-2)//option['crew']))
            option['max_count']=maximum
        from .operation_support import offensive_options
        return dict(enemies=enemies,combat_units=[dict(id=u['id'],type=u['type'],cell=list(u['cell']),strength=self.effective_strength(u),order=u.get('order'),embarked_on=u.get('embarked_on')) for u in units],
                    offensive_options=offensive_options(self,state,units),
                    recruitment_priority=dict(at_war=bool(enemies),no_combat_units=not units,can_recruit_now=bool(options),
                        instruction='При войне без боевых частей и доступном найме сначала оцени mobilize и добавь реальный приказ из recruitment_options. Отказ требует конкретного расчёта; армия не появится от письма.'),
                    combat_count=len(units),border_cells=border[:16],hostile_border_cells=hostile[:16],recruitment_sites=sites[:8],recruitment_options=options,
                    previous_response=next((r['decision'].get('military_response') for r in reversed(self.decisions) if r['state']==state.id),None),
                    batch_recruitment='unit/recruit_modern count=N нанимает группу без лимита двух. Нужны деньги, материалы, отдельные свободные клетки, современные экипажи. Вся группа проверяется до оплаты; ограничение 12 действий не ограничивает численность группы.',
                    standing_service='Военный минимум удалён. Боевые части создаются только явными unit/recruit_modern, policy.unit_limit не ограничивает явный найм. Автоматические разведчики в войну не нанимаются.')

