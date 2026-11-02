"""Research catalogue and one shared calculation path for income and forecasts."""
import math
from .rules import RuleError
from .modern_catalog import UNITS

BASE_TECHS=('army','lab','mine','agriculture','navigation')
# id, Russian name, prerequisite(s), money, science, matter, actual effect
ROWS=[
 ('irrigation','Орошение',('agriculture',),120,40,0,'+25% еды с травы'),
 ('crop_rotation','Севооборот',('irrigation',),160,60,0,'Ещё +25% еды с травы'),
 ('forestry','Лесное хозяйство',('agriculture',),120,40,0,'+25% сырья из лесов'),
 ('deep_mining','Глубокие шахты',('mine',),160,60,0,'+25% металла с гор'),
 ('steelworks','Сталелитейное дело',('deep_mining',),200,80,10,'+25% выхода зданий-шахт'),
 ('scholarship','Научная школа',('lab',),140,50,0,'+25% науки с научных клеток'),
 ('universities','Университеты',('scholarship',),220,100,15,'+25% выхода лабораторий'),
 ('banking','Банки',(),160,60,0,'+20% денежного выхода замков и таверн'),
 ('taxation','Налоговая администрация',('banking',),200,80,0,'+1 деньги с каждой своей клетки'),
 ('granaries','Зернохранилища',('agriculture',),140,50,0,'Расход еды на жителя: 2 → 1,5'),
 ('recycling','Повторное использование',('mine',),160,60,0,'Расход сырья на жителя: 1 → 0,75'),
 ('masonry','Каменное строительство',(),120,40,0,'−25% сырья на постройку'),
 ('engineering','Инженерия',('masonry',),200,80,10,'Постройка: 160 денег; улучшение земли: 240'),
 ('conscription','Организованный набор',('army',),160,60,0,'Найм юнита: 45 вместо 60 денег'),
 ('logistics','Военная логистика',('army',),220,90,15,'+1 шаг в день сухопутным юнитам'),
 ('cartography','Картография',('navigation',),140,50,0,'+1 шаг разведчикам; обзор в контексте до двух клеток от границы'),
 ('military_medicine','Военная медицина',('army',),220,90,15,'Открывает reinforce: восстановление силы за материю'),
 ('fortification','Фортификация',('masonry','army'),220,90,15,'Открывает укрепления: до 3 снижения входящего урона защитнику'),
 ('alchemy','Прикладная алхимия',('lab',),240,100,20,'Открывает convert: материя → еда, сырьё, металл или наука'),
 ('aether_forging','Эфирная ковка',('alchemy','engineering'),320,140,30,'+25% выхода арсеналов; открывает повышение уровня здания'),
]
TECHNOLOGIES={key:dict(id=key,name=key,requires=[],money=100,science=30,matter=0,effect=effect) for key,effect in zip(BASE_TECHS,
 ('Сила найма 6–10','Улучшение научных клеток','Улучшение гор и залежей','Улучшение травы и леса','Строительство кораблей; сухопутные юниты всё равно не ходят по воде'))}
for key,name in zip(BASE_TECHS,('Военное дело','Методы исследования','Горное дело','Земледелие','Навигация')): TECHNOLOGIES[key]['name']=name
for key,name,requires,money,science,matter,effect in ROWS:
    TECHNOLOGIES[key]=dict(id=key,name=name,requires=list(requires),money=money,science=science,matter=matter,effect=effect)
TECHS=tuple(TECHNOLOGIES)


class Technology:
    def citizen_upkeep(self,state):
        ration=.8 if self.era_for(state)==2 and state.modern.get('rationing_until',-1)>=self.day else 1
        return dict(food=(1.5 if 'granaries' in state.tech else 2)*ration,resource=.75 if 'recycling' in state.tech else 1)

    def production_for_cell(self,state,cell):
        out=dict.fromkeys(('food','resource','metal','science','matter','money'),0.0)
        if cell.terrain=='water':return out
        key={'grass':'food','forest':'resource','mountain':'metal','science':'science','resource':'resource'}.get(cell.terrain)
        if key:
            bonuses={'grass':('irrigation','crop_rotation'),'forest':('forestry',),'mountain':('deep_mining',),'science':('scholarship',)}
            out[key]+=cell.level*(1+.25*sum(t in state.tech for t in bonuses.get(cell.terrain,())))
        out['money']+=4+cell.population+int('taxation' in state.tech)
        if self.era_for(state)==2 and state.modern.get('emergency_tax_until',-1)>=self.day: out['money']+=cell.population*.8
        if cell.building in ('lab','mine','tavern','castle','arsenal'):
            output={'lab':'science','mine':'metal','tavern':'money','castle':'money','arsenal':'matter'}[cell.building]
            bonus={'lab':('universities',.25),'mine':('steelworks',.25),'tavern':('banking',.2),'castle':('banking',.2),'arsenal':('aether_forging',.25)}[cell.building]
            out[output]+=10*cell.building_level*(1 if cell.population else .1)*(1+bonus[1]*int(bonus[0] in state.tech))
        return {key:round(value,2) for key,value in out.items()}

    def unit_price(self,state): return 45 if 'conscription' in state.tech else 60

    def research_catalog(self,state):
        return [dict(value,researched=key in state.tech,available=key not in state.tech and all(t in state.tech for t in value['requires'])) for key,value in TECHNOLOGIES.items()]+self.modern_catalog(state)

    def matter_action(self,state,kind,args):
        if kind=='reinforce':
            unit=next((u for u in self.units if u['id']==args.get('unit_id') and u['owner']==state.id),None)
            if 'military_medicine' not in state.tech or not unit: raise RuleError('Нужны military_medicine и свой юнит')
            if unit['type'] in UNITS and self.era_for(state)<2: raise RuleError('Современная техника закрыта до своей эпохи II')
            if unit.get('embarked_on') or self.cell(unit['cell']).owner!=state.id: raise RuleError('Пополнение только на своей клетке вне транспорта')
            amount=args.get('amount',1)
            if type(amount) not in (int,float) or not math.isfinite(amount) or not .01<=amount<=10 or unit['strength']+amount>unit['max_strength']+1e-8: raise RuleError('Пополнение не может превысить исходную силу юнита')
            cost=round(5*amount,2)
            if state.stocks['matter']<cost or state.stocks['money']<10*amount: raise RuleError('На единицу силы нужно 5 материи и 10 денег')
            state.stocks['matter']-=cost; state.stocks['money']-=10*amount; unit['strength']=round(unit['strength']+amount,4)
            return f'Юнит #{unit["id"]}: восстановлено {amount} силы за {cost} материи'
        cell=self.cell(args.get('cell'))
        if cell.owner!=state.id: raise RuleError('Нужна своя клетка')
        if kind=='convert':
            amount=args.get('amount'); resource=args.get('resource'); rates=dict(food=4,resource=3,metal=2,science=2)
            if 'alchemy' not in state.tech: raise RuleError('Нужна технология alchemy')
            if type(amount) is not int or not 1<=amount<=100 or resource not in rates: raise RuleError('convert: 1–100 материи в food/resource/metal/science')
            if state.stocks['matter']<amount or state.stocks['money']<10: raise RuleError('Недостаточно материи или 10 денег')
            state.stocks['matter']-=amount; state.stocks['money']-=10; state.stocks[resource]+=amount*rates[resource]
            return f'Алхимия: {amount} материи → {amount*rates[resource]} {resource}'
        if kind=='fortify':
            if 'fortification' not in state.tech or cell.terrain=='water' or cell.fortification>=3: raise RuleError('Нужны fortification, суша и укрепление ниже уровня 3')
            money,matter,raw=60,10,10
        else:
            if 'aether_forging' not in state.tech or not cell.building or cell.building_level>=10: raise RuleError('Нужны aether_forging и здание ниже уровня 10')
            money,matter,raw=100,10*cell.building_level,20
        if state.stocks['money']<money or state.stocks['matter']<matter or state.stocks['resource']<raw: raise RuleError(f'Нужно {money} денег, {matter} материи и {raw} сырья')
        state.stocks['money']-=money; state.stocks['matter']-=matter; state.stocks['resource']-=raw
        if kind=='fortify': cell.fortification+=1; return f'Укрепление {args["cell"]}: уровень {cell.fortification}'
        if cell.building=='wall': cell.wall_hp=self.wall_hitpoints(cell)+20
        cell.building_level+=1
        return f'Здание {args["cell"]}: уровень {cell.building_level}'
