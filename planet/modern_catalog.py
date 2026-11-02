"""Fictional strategy-game values. All second-era content lives in one catalogue."""
BASE_RESOURCES=('food','resource','metal','science','matter','money')
RESOURCE_NAMES=dict(food='Еда',resource='Сырьё',metal='Металл',science='Общая наука',matter='Материя',money='Деньги',
    coal='Уголь',oil='Нефть',gas='Газ',water='Вода',electricity='Электроэнергия',steel='Сталь',concrete='Бетон',chemicals='Химикаты',fertilizer='Удобрения',fuel='Топливо',electronics='Электроника',machinery='Оборудование',medicine='Лекарства',consumer_goods='Потребтовары',weapons_i='Оружие I',weapons_ii='Оружие II',weapons_iii='Оружие III',engineering_science='Инженерные знания',physics_science='Физические знания',computing_science='Вычислительные знания',isotopes='Изотопы',warheads='Боевые модули',missiles_i='Ракеты I',missiles_ii='Ракеты II',missiles_iii='Ракеты III')
MODERN_RESOURCES=tuple(k for k in RESOURCE_NAMES if k not in BASE_RESOURCES)
SCIENCES=('engineering_science','physics_science','computing_science')
TECHNOLOGIES={}
def tech(key,name,requires,cost,effect,site=None):
    row=dict(id=key,name=name,requires=list(requires),cost=dict(cost),effect=effect,era=1 if key=='industrialization' else 2,site=site)
    row.update({k:cost.get(k,0) for k in ('money','science','matter')}); TECHNOLOGIES[key]=row

tech('industrialization','Эпохальный переход: индустриальная цивилизация',('universities','engineering','steelworks','banking','aether_forging'),dict(money=50000,science=15000,matter=4000),'Открывает ТОЛЬКО вашей стране эпоху II, промышленность, массовое население и новые ресурсы')
ROWS=[
 ('urban_planning','Массовое жилищное строительство',(),6000,1500,250,{},'Жилые кварталы на 200 жителей; массовые демографические указы'),
 ('highrise','Высотные города',('urban_planning',),12000,2500,600,dict(engineering_science=800),'Небоскрёб: вместимость клетки 500 жителей'),
 ('mass_agriculture','Промышленное сельское хозяйство',(),6000,1600,250,{},'Фермы: 120 рабочих и до 3000 еды в день на уровень'),
 ('petrochemistry','Нефтехимия',(),7000,1800,300,dict(engineering_science=200),'НПЗ, химия, удобрения'),
 ('electrical_grid','Национальная энергосеть',(),5000,1200,200,{},'Газовая энергетика, +15% выработки энергии'),
 ('renewable_energy','Возобновляемая энергетика',('electrical_grid',),10000,2500,500,dict(engineering_science=600),'Солнечные станции без топливного входа'),
 ('industrial_automation','Промышленная автоматизация',(),10000,2200,500,dict(engineering_science=500),'+25% выпуска всех промышленных предприятий без увеличения входов'),
 ('machine_tools','Станкостроение',(),6500,1600,250,dict(engineering_science=150),'Машиностроительные заводы'),
 ('electronics','Электронная промышленность',('machine_tools',),9000,2000,350,dict(engineering_science=400),'Электронные заводы, вычислительные центры'),
 ('public_health','Общественное здравоохранение',('petrochemistry',),8000,1800,300,{},'Фармзаводы, больницы, лечебный указ'),
 ('consumer_economy','Массовое потребление',('urban_planning',),7000,1500,250,{},'Потребительские фабрики, финансовые центры'),
 ('modern_infantry','Современная пехота',(),8000,2000,350,dict(engineering_science=200),'Оружие I, мотопехота: базовая сила 120'),
 ('armored_warfare','Бронетанковые армии',('modern_infantry','machine_tools'),13000,3000,600,dict(engineering_science=700),'Оружие II, танки и механизированные корпуса'),
 ('precision_weapons','Высокоточное оружие',('armored_warfare','electronics'),18000,4000,900,dict(computing_science=800,engineering_science=900),'Оружие III, элитные корпуса и реактивные войска'),
 ('artillery_systems','Артиллерийские системы',('modern_infantry',),9000,2300,400,dict(engineering_science=400),'Артиллерия с дистанционной атакой'),
 ('drone_warfare','Беспилотные формирования',('electronics','precision_weapons'),16000,3000,700,dict(computing_science=800),'Дроновые бригады с дистанционной атакой'),
 ('modern_fortification','Железобетонная оборона',(),7000,1800,300,dict(engineering_science=150),'Бетонные стены, бункеры, крепости, противотанковые рубежи'),
 ('air_defense','Противовоздушная оборона',('electronics','modern_fortification'),12000,2500,500,dict(computing_science=400),'ПВО и мобильная ПВО; защита от ракет и дронов'),
 ('radar_network','Радиолокационная сеть',('air_defense',),10000,2000,500,dict(computing_science=600),'Радар усиливает близкую противоракетную оборону'),
 ('civil_defense','Гражданская оборона',('modern_fortification','public_health'),9000,1800,400,{},'Убежища; снижение потерь населения от ударов'),
 ('modern_logistics','Современная логистика',('machine_tools',),10000,2300,450,dict(engineering_science=500),'-25% топлива/оружия на ежедневное снабжение современных формирований'),
 ('physics_institutes','Физические институты',(),8000,2000,400,{},'Физические лаборатории, отдельная физическая наука'),
 ('nuclear_physics','Радиационная физика',('physics_institutes',),16000,4500,1200,dict(physics_science=1500),'Радиационный полигон на пустой своей клетке: необратимое загрязнение без очистки'),
 ('radiological_research','Исследования на полигоне',('nuclear_physics',),18000,5000,1500,dict(physics_science=2000,engineering_science=1000),'Научная станция строится ТОЛЬКО вместо полигона на той же загрязнённой клетке'),
 ('ballistics_i','Ракетная программа I',('radiological_research','artillery_systems'),24000,6000,1800,dict(physics_science=2500,engineering_science=2000),'Ракеты I, специальный завод и пусковая шахта'),
 ('ballistics_ii','Ракетная программа II',('ballistics_i','precision_weapons'),40000,9000,3000,dict(physics_science=4500,engineering_science=3500,computing_science=2000),'Ракеты II: дальность 16 игровых клеток'),
 ('strategic_missiles','Стратегические ракеты III',('ballistics_ii','radar_network'),70000,15000,5000,dict(physics_science=8000,engineering_science=5000,computing_science=4000),'Ракеты III: дальность 32, удар по клетке и её соседям'),
 ('missile_defense','Противоракетная оборона',('ballistics_ii','radar_network'),35000,7000,2000,dict(physics_science=2000,computing_science=3000),'Комплексы ПРО: сильнее ПВО против ракет'),
 ('environmental_recovery','Восстановление среды',('radiological_research','public_health'),20000,4000,1000,dict(physics_science=1000),'Очистка загрязнённых клеток и снижение промышленной заболеваемости'),
 ('fiscal_stability','Финансовое регулирование',('consumer_economy',),18000,3500,700,dict(computing_science=600),'-25% гражданских денежных расходов; доступ к займу и погашению'),
 ('advanced_materials','Перспективные материалы',('precision_weapons',),18000,3500,800,dict(physics_science=1000),'Заводы боевых модулей для ракет'),
 ('research_network','Научная кооперация институтов',('electronics','physics_institutes'),14000,3000,600,dict(computing_science=500),'+25% общей, инженерной, физической и вычислительной науки'),
]
for key,name,req,money,science,matter,extra,effect in ROWS:
    tech(key,name,('industrialization',)+req,dict(money=money,science=science,matter=matter,**extra),effect,'radiation_station' if key in ('ballistics_i','ballistics_ii','strategic_missiles') else None)

BUILDINGS={}
def building(key,name,technology,workers,cost,inputs=None,outputs=None,**extra):
    BUILDINGS[key]=dict(id=key,name=name,tech=technology,workers=workers,cost=cost,inputs=inputs or {},outputs=outputs or {},capacity=20,max_level=3,priority=50,**extra)

building('housing_block','Жилой квартал','urban_planning',0,dict(money=2500,resource=150,metal=80),capacity_override=200)
building('skyscraper','Небоскрёб','highrise',0,dict(money=9000,steel=200,concrete=400,electronics=40),dict(electricity=30,money=60),capacity_override=500)
building('coal_mine','Угольный разрез','industrialization',20,dict(money=2000,resource=120,metal=80),dict(money=40),dict(coal=180),priority_override=95)
building('oil_well','Нефтяная скважина','industrialization',35,dict(money=3000,resource=150,metal=130),dict(money=60,resource=10),dict(oil=150),priority_override=95)
building('gas_well','Газовая скважина','industrialization',30,dict(money=2800,resource=140,metal=100),dict(money=50),dict(gas=150),priority_override=95)
building('waterworks','Водоканал','industrialization',10,dict(money=2000,resource=150,metal=60),dict(money=45),dict(water=3000),priority_override=100)
building('coal_power','Тепловая электростанция','industrialization',40,dict(money=3500,resource=200,metal=180),dict(coal=40,money=100),dict(electricity=1500),priority_override=90)
building('gas_power','Газовая электростанция','electrical_grid',40,dict(money=5000,steel=100,concrete=100),dict(gas=35,money=100),dict(electricity=2000),priority_override=90)
building('solar_power','Солнечная электростанция','renewable_energy',20,dict(money=10000,steel=100,electronics=120),dict(electronics=1,money=60),dict(electricity=1100),priority_override=90)
building('concrete_plant','Цементно-бетонный завод','industrialization',30,dict(money=2500,resource=200,metal=70),dict(resource=60,money=50),dict(concrete=220),priority_override=85)
building('steel_mill','Сталелитейный комбинат','industrialization',60,dict(money=4000,resource=250,metal=150),dict(coal=40,metal=100,electricity=100,money=90),dict(steel=180),priority_override=80)
building('lumber_complex','Лесопромышленный комплекс','industrialization',45,dict(money=3000,resource=100,metal=80),dict(electricity=60,money=50),dict(resource=900),terrain=['forest'],priority_override=85)
building('ore_complex','Горно-обогатительный комбинат','industrialization',60,dict(money=3500,resource=200,metal=100),dict(electricity=100,money=65),dict(metal=700),terrain=['resource','mountain'],priority_override=85)
building('industrial_farm','Агропромышленная ферма','mass_agriculture',120,dict(money=5000,resource=300,metal=120),dict(fertilizer=20,electricity=40,money=80),dict(food=3000),terrain=['grass'],priority_override=100)
building('chemical_plant','Химический завод','petrochemistry',45,dict(money=4500,steel=100,concrete=100),dict(oil=25,electricity=100,money=80),dict(chemicals=160),priority_override=78)
building('fertilizer_plant','Завод удобрений','petrochemistry',40,dict(money=3500,steel=80,concrete=80),dict(chemicals=20,gas=20,electricity=60,money=60),dict(fertilizer=180),priority_override=75)
building('refinery','Нефтеперерабатывающий завод','petrochemistry',70,dict(money=5500,steel=160,concrete=180),dict(oil=60,electricity=120,money=120),dict(fuel=220),priority_override=76)
building('machine_factory','Машиностроительный завод','machine_tools',90,dict(money=6000,steel=180,concrete=140),dict(steel=40,electricity=140,money=150),dict(machinery=70),priority_override=65)
building('electronics_factory','Электронный завод','electronics',100,dict(money=7500,steel=120,concrete=150,machinery=40),dict(metal=35,chemicals=20,electricity=200,money=180),dict(electronics=100),priority_override=65)
building('pharma_factory','Фармацевтический завод','public_health',70,dict(money=6500,steel=100,concrete=120),dict(chemicals=30,electricity=100,money=120),dict(medicine=100),priority_override=70)
building('consumer_factory','Фабрика потребтоваров','consumer_economy',100,dict(money=6500,steel=100,concrete=140),dict(resource=100,chemicals=20,electricity=100,money=150),dict(consumer_goods=180),priority_override=55)
building('financial_center','Финансовый центр','consumer_economy',140,dict(money=12000,steel=150,concrete=250,electronics=80),dict(consumer_goods=30,electricity=180,computing_science=5),dict(money=3500),priority_override=60)
building('hospital','Городская больница','public_health',50,dict(money=4500,steel=80,concrete=140),dict(medicine=20,electricity=80,money=100),dict(),service='health')
building('engineering_institute','Инженерный институт','industrialization',40,dict(money=4000,resource=150,metal=120),dict(metal=10,money=100),dict(engineering_science=200,science=100),priority_override=72)
building('physics_lab','Физический институт','physics_institutes',80,dict(money=6500,steel=100,concrete=160),dict(electricity=150,money=180),dict(physics_science=300,science=150),priority_override=60)
building('computing_center','Вычислительный центр','electronics',80,dict(money=8000,steel=100,electronics=100),dict(electricity=220,electronics=2,money=200),dict(computing_science=350,science=100),priority_override=60)
building('university','Университетский кампус','industrialization',120,dict(money=5500,resource=200,metal=100),dict(money=180,resource=20),dict(science=900,matter=60),priority_override=70)
for tier,technology,workers in ((1,'modern_infantry',100),(2,'armored_warfare',150),(3,'precision_weapons',200)):
    inputs=dict(steel=35*tier,electricity=100*tier,money=120*tier)
    if tier>1: inputs.update(electronics=10*tier,machinery=5*tier)
    if tier==3: inputs['weapons_ii']=25
    building('weapons_factory_'+str(tier),'Оружейный завод '+str(tier),technology,workers,dict(money=7000*tier,steel=150*tier,concrete=200*tier),inputs,{'weapons_'+('i'*tier):60 if tier<3 else 40},priority_override=50)
building('concrete_wall','Железобетонная стена','modern_fortification',0,dict(money=3500,steel=100,concrete=300),barrier=400,armor=20)
building('bunker','Бункерный комплекс','modern_fortification',20,dict(money=5000,steel=180,concrete=400),dict(money=80,electricity=30),barrier=600,armor=60)
building('fortress','Современная крепость','modern_fortification',60,dict(money=10000,steel=350,concrete=800,weapons_i=50),dict(money=200,electricity=60,weapons_i=1),barrier=1200,armor=100)
building('anti_tank_line','Противотанковый рубеж','modern_fortification',20,dict(money=4000,steel=180,concrete=150),dict(money=60),armor=80)
building('air_defense_site','Комплекс ПВО','air_defense',40,dict(money=8000,steel=180,electronics=120,weapons_ii=40),dict(money=150,electricity=120,weapons_ii=1),intercept=60,radius=2)
building('radar','Радиолокационный узел','radar_network',30,dict(money=6500,steel=100,electronics=180),dict(money=100,electricity=160),service='radar')
building('missile_defense_site','Комплекс ПРО','missile_defense',70,dict(money=18000,steel=350,electronics=300,weapons_iii=80),dict(money=350,electricity=250,weapons_iii=2),intercept=85,radius=3)
building('shelter','Гражданское убежище','civil_defense',15,dict(money=5000,steel=100,concrete=400),dict(money=50,electricity=30),service='shelter')
building('radiation_test_range','Радиационный полигон','nuclear_physics',0,dict(money=20000,matter=1500,steel=400,concrete=600),radioactive=True,max_level_override=1)
building('radiation_station','Особая научная станция','radiological_research',150,dict(money=30000,matter=2000,steel=500,electronics=200),dict(electricity=350,medicine=8,electronics=5,money=500),dict(physics_science=1200,isotopes=12),radioactive=True,max_level_override=1,priority_override=65)
building('warhead_factory','Завод боевых модулей','advanced_materials',180,dict(money=25000,steel=500,electronics=200,machinery=150),dict(isotopes=5,steel=100,electronics=30,electricity=500,money=900),dict(warheads=8))
for tier,technology in ((1,'ballistics_i'),(2,'ballistics_ii'),(3,'strategic_missiles')):
    building('missile_factory_'+str(tier),'Ракетный завод '+str(tier),technology,150+50*tier,dict(money=20000*tier,steel=400*tier,concrete=500*tier,machinery=100*tier),dict(steel=100*tier,electronics=30*tier,fuel=60*tier,warheads=tier,electricity=400*tier,money=700*tier),{'missiles_'+('i'*tier):2},priority_override=40)
building('missile_silo','Ракетная шахта','ballistics_i',50,dict(money=18000,steel=500,concrete=900,electronics=200),dict(money=250,electricity=100),armor=80)
for row in BUILDINGS.values():
    row['capacity']=row.pop('capacity_override',row['capacity']); row['priority']=row.pop('priority_override',row['priority']); row['max_level']=row.pop('max_level_override',row['max_level'])

UNITS={
 'motorized':dict(name='Мотопехотная бригада',tech='modern_infantry',strength=120,speed=4,crew=40,weapon='weapons_i',weapons=60,fuel=20,money=120,steel=40),
 'mechanized':dict(name='Механизированный корпус',tech='armored_warfare',strength=220,speed=4,crew=70,weapon='weapons_ii',weapons=100,fuel=45,money=220,steel=120),
 'tank_corps':dict(name='Танковый корпус',tech='armored_warfare',strength=320,speed=3,crew=80,weapon='weapons_ii',weapons=140,fuel=70,money=300,steel=220),
 'artillery':dict(name='Артиллерийская бригада',tech='artillery_systems',strength=170,speed=2,crew=50,weapon='weapons_i',weapons=100,fuel=25,money=180,steel=100,range=3),
 'rocket_corps':dict(name='Реактивный корпус',tech='precision_weapons',strength=420,speed=3,crew=100,weapon='weapons_iii',weapons=120,fuel=80,money=450,steel=250,range=5),
 'drone_swarm':dict(name='Беспилотная бригада',tech='drone_warfare',strength=240,speed=5,crew=35,weapon='weapons_iii',weapons=80,fuel=15,money=250,steel=80,range=4),
 'elite_corps':dict(name='Корпус специального назначения',tech='precision_weapons',strength=300,speed=4,crew=60,weapon='weapons_iii',weapons=100,fuel=25,money=350,steel=80),
 'mobile_air_defense':dict(name='Мобильная ПВО',tech='air_defense',strength=140,speed=3,crew=40,weapon='weapons_ii',weapons=80,fuel=30,money=220,steel=120,intercept=35,radius=1),
}
MISSILES={key:dict(tech=tech,range=distance,damage=damage,penetration=pen,area=area) for key,tech,distance,damage,pen,area in (
 ('missiles_i','ballistics_i',8,180,0,0),('missiles_ii','ballistics_ii',16,450,20,0),('missiles_iii','strategic_missiles',32,1000,35,1))}
NEW_ACTIONS=('edict','factory_policy','repair_building','demolish','remediate','recruit_modern','bombard','missile_strike','supply_pact','accept_supply','cancel_supply','borrow','repay')
