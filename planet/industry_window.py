"""Independent, read-only, live economy window opened by «Расширить»."""
import sys,time,sqlite3
from pathlib import Path
import pygame as pg
from .relations_window import RelationsView,SnapshotReader,BG,PANEL,TEXT,MUTED,GREEN,RED,GOLD
from .console_monitor import parent_alive
from .modern_catalog import RESOURCE_NAMES,BUILDINGS,UNITS


STATUSES=dict(stable='устойчиво',critical='КРИТИЧЕСКИЙ ДЕФИЦИТ',deficit='дефицит',bottleneck='не хватает входов',low_reserve='низкий резерв',no_production='нет производства',labor='не хватает рабочих',technology='не изучена технология',mothballed='законсервировано')

def amounts(values): return ', '.join(f'{RESOURCE_NAMES.get(k,k)} {v:g}' for k,v in values.items() if v) or '—'


class IndustryView(RelationsView):
    def __init__(self,world,sid):
        super().__init__(world,sid); self.screen=pg.display.set_mode((1280,900),pg.RESIZABLE)
        self.cached_world=None; self.cache={}
        pg.display.set_caption('Живая планета 7.0 · Расширенная экономика · '+world.state(sid).name)
    def draw(self):
        w=self.world; state=w.state(self.sid); width,height=self.screen.get_size(); self.buttons=[]; self.screen.fill(BG)
        if self.cached_world is not w: self.cache={}; self.cached_world=w
        if 'forecast' not in self.cache: self.cache['forecast']=w.economic_forecast(state)
        forecast=self.cache['forecast']; era=w.era_for(state)
        self.text(state.name+f' · ЭПОХА {era} · РАСШИРЕННАЯ ЭКОНОМИКА',28,22,state.color,self.heading)
        self.text(f'День {w.day} · личная экономика · сведения читаются из сохранения',30,63,MUTED,self.small)
        if era==2:
            plan=forecast['industry']; capacity=sum(w.population_capacity(state,w.cell(p)) for p in w.positions(state.id))
            self.text(f'Жители {plan["population"]:,} / мест {capacity:,} · рабочих {plan["workforce"]:,} · свободно {plan["idle_workers"]:,} · недовольство {state.modern.get("unrest",0):g} · долг {state.modern.get("debt",0):,.0f}',30,91,GOLD,self.small)
        else: self.text('Эпоха II закрыта: нужно собственное исследование «Индустриальная цивилизация». Чужой переход её не открывает.',30,91,GOLD,self.small)
        tab_width=(width-56)//6
        for i,label in enumerate(('Ресурсы','Предприятия','Технологии','Современная армия','Торговые пакты','Сделки')): self.button(label,(28+i*tab_width,126,tab_width-10,37),'tab:'+str(i),self.tab==i)
        content=pg.Rect(28,182,width-56,height-225); self.box(content); self.screen.set_clip(content.inflate(-18,-14)); x=content.x+16; y=content.y+16-self.scroll; rw=content.width-32
        if self.tab==0:
            for key,item in forecast['resources'].items():
                color=RED if item['status'] in ('critical','deficit','bottleneck') else GREEN
                self.text(RESOURCE_NAMES.get(key,key),x,y,TEXT); self.text(f'{item["stock"]:,.1f}',x+265,y,TEXT)
                self.text(f'{item["net"]:+,.1f}/день',x+455,y,color); self.text('Запас '+('∞' if item['runway_days'] is None else str(item['runway_days'])+' дн.'),x+700,y,color,self.small)
                y=self.wrap(f'Производство {item["production"]:,.1f} · расход {item["upkeep"]:,.1f} · резерв {item["reserve"]:,.1f} · {STATUSES.get(item["status"],item["status"])}'+(f' · необеспеченный спрос {item["unmet_demand"]:,.1f}' if item.get('unmet_demand') else '')+(f' · пакты {item["signed_pact_net"]:+,.1f}' if item.get('signed_pact_net') else ''),x,y+28,rw,MUTED,self.small)+19
        elif self.tab==1:
            if era==2:
                for row in forecast['industry']['buildings']:
                    y=self.wrap(f'{row["name"]} · {row["cell"]} · уровень {row["level"]} · мощность {row["utilization"]*100:.0f}% · рабочие {row["assigned"]}/{row["workers"]}',x,y,rw,GREEN if not row['bottlenecks'] else GOLD)+5
                    y=self.wrap('Входы/день: '+amounts(row['inputs'])+'\nВыходы/день: '+amounts(row['outputs'])+'\nОграничения: '+(', '.join(RESOURCE_NAMES.get(k,STATUSES.get(k,k)) for k in row['bottlenecks']) or 'нет'),x,y,rw,MUTED,self.small)+22
                y=self.wrap('ДОСТУПНЫЕ ПРОЕКТЫ · стоимость и ПОЛНЫЙ суточный расход',x,y+10,rw,GOLD)+15
                if 'projects' not in self.cache: self.cache['projects']=w.modern_construction(state)
                for p in self.cache['projects']:
                    y=self.wrap(f'{p["name"]} · {p["cell"]} · рабочих {p["required_workers"]} · мест {p["capacity"]}',x,y,rw,GREEN)+4
                    y=self.wrap('Постройка: '+amounts(p['cost'])+'\nВходы: '+amounts(p['daily_inputs'])+'\nВыходы: '+amounts(p['daily_gain']),x,y,rw,MUTED,self.small)+20
            else: y=self.wrap('Промышленность станет доступна после личного эпохального перехода. Уже сейчас развивайте арсеналы и лаборатории, чтобы накопить материю и науку.',x,y,rw,GOLD)
        elif self.tab==2:
            for t in w.research_catalog(state):
                y=self.wrap(t['name']+' · '+('ИССЛЕДОВАНО' if t['researched'] else 'ДОСТУПНО' if t['available'] else 'ЗАКРЫТО'),x,y,rw,GREEN if t['researched'] else GOLD)+4
                y=self.wrap('Цена: '+amounts(t.get('cost',{k:t[k] for k in ('money','science','matter')}))+'\nНужны: '+(', '.join(t['requires']) or 'нет')+('\nОсобое место: '+t['site'] if t.get('site') else '')+'\n'+t['effect'],x,y,rw,MUTED,self.small)+20
        elif self.tab==3:
            if era==2:
                for key,info in UNITS.items():
                    status='ДОСТУПНО' if info['tech'] in state.tech else 'Нужно '+info['tech']
                    y=self.wrap(f'{info["name"]} · {status} · сила {info["strength"]} · дальность {info.get("range",1)}',x,y,rw,GREEN)+4
                    y=self.wrap(f'Экипаж {info["crew"]} из гражданской экономики; найм {info["money"]*15} денег, {info["steel"]} стали, {info["weapons"]} {RESOURCE_NAMES[info["weapon"]]}. Суточно: {info["money"]} денег, {info["fuel"]} топлива, еда и боеприпасы.',x,y,rw,MUTED,self.small)+18
                for u in w.units:
                    if u['owner']==state.id and u['type'] in UNITS: y=self.wrap(f'#{u["id"]} {UNITS[u["type"]]["name"]} · {u["cell"]} · сила {w.effective_strength(u):g} · снабжение {u.get("supply_ratio",1)*100:.0f}%',x,y,rw,GOLD)+10
                y=self.wrap('Ракетная программа: полигон → станция на той же загрязнённой клетке → отдельные исследования → заводы и шахты. Ракеты I / II / III: 8 / 16 / 32 игровых клетки. ПВО, ПРО и радар требуют ежедневного снабжения; удар сам по себе не захватывает территорию.',x,y+14,rw,TEXT)
            else: y=self.wrap('Современные формирования и ракетная ветка закрыты до собственного перехода в эпоху II.',x,y,rw,GOLD)
        elif self.tab==4:
            for p in w.supply_context(state):
                y=self.wrap(f'Пакт #{p["id"]} · {w.state(p["seller"]).name} → {w.state(p["partner"]).name} · {dict(open="предложен",active="действует",cancelled="расторгнут",completed="завершён",expired="истёк").get(p["status"],p["status"])}',x,y,rw,GREEN)+4
                y=self.wrap(f'{p["amount"]:,} {RESOURCE_NAMES[p["resource"]]}/день · {p["daily_payment"]:,.1f} денег/день · полное обязательство {p["total_commitment"]:,.1f}\nШтраф {p["penalty"]:,.1f} · осталось {p["remaining_days"]} дней · срывов {p["defaults"]} · оплачено {p["paid"]:,.1f}\n'+p['warning'],x,y,rw,MUTED,self.small)+22
            for claim in state.modern.get('claims',[]): y=self.wrap(f'Договорной долг {w.state(claim["creditor"]).name}: {claim["amount"]:,.1f} денег · пакт #{claim["pact_id"]}',x,y,rw,RED)+15
            y=self.wrap('Пакт работает только после согласия покупателя; поставки идут со следующего дня до промышленного производства. Обещанный доход не гарантирован. Неоплаченная часть поставки не появляется из ничего. Срыв и досрочный выход могут создать штрафы и долговую зависимость.',x,y+12,rw,GOLD)
        else:
            commerce=w.commerce_context(state)
            statuses=dict(open='предложен',awaiting_delivery='ожидается встречная часть',fulfilled='исполнен',settled_late='погашен после нарушения',repudiated='сознательный отказ',defaulted='просрочен',expired='истёк',cancelled='отозван',closed_defeat='закрыт при ликвидации')
            modes=dict(secure='Одновременный обмен',advance='Аванс без гарантий',credit='Товар в кредит без гарантий')
            y=self.wrap('ДОГОВОРЫ И ФАКТИЧЕСКИЕ ПЕРЕВОДЫ · слова сами не меняют запасы',x,y,rw,GOLD)+15
            for deal in reversed(commerce['exchanges']):
                y=self.wrap(f"Обмен #{deal['id']} · {modes[deal['mode']]} · {statuses.get(deal['status'],deal['status'])}",x,y,rw,GREEN)+5
                y=self.wrap(f"{w.state(deal['seller']).name} отдаёт: {amounts(deal['give'])}\n{w.state(deal['partner']).name} отдаёт: {amounts(deal['receive'])}\nНепогашенная часть: {amounts(deal.get('owed',{})) if deal['status'] in ('awaiting_delivery','defaulted','repudiated') else 'нет'} · срок {deal.get('due_day','после принятия')}\nКвитанции: {deal['receipt_ids']}",x,y,rw,MUTED,self.small)+20
            for offer in commerce['incoming_trade_offers']:
                y=self.wrap(f"ВХОДЯЩЕЕ #{offer['id']}: {offer['amount']} {RESOURCE_NAMES.get(offer['resource'],offer['resource'])} за {offer['amount']*offer['price']:g} денег. Только {state.name} может принять accept_trade; cell не нужен.",x,y,rw,GOLD)+18
            y=self.wrap('КВИТАНЦИИ · реальные изменения запасов',x,y+12,rw,GREEN)+15
            for receipt in reversed(commerce['receipts']):
                y=self.wrap(f"#{receipt['id']} · день {receipt['day']} · {w.state(receipt['sender']).name} → {w.state(receipt['recipient']).name}: {amounts(receipt['resources'])}",x,y,rw,TEXT)+5
                own=receipt['balances'].get(state.id,{})
                y=self.wrap('Наш баланс: '+', '.join(f"{RESOURCE_NAMES.get(k,k)} {v['before']:g} → {v['after']:g}" for k,v in own.items()),x,y,rw,MUTED,self.small)+18
            y=self.wrap('Аванс и кредит допускают реальный обман: чужая часть уже передана, а должник может не отдать свою. Это портит отношения и даёт повод к санкциям/войне. Обычная одновременная покупка исполняет обе части сразу.',x,y+12,rw,GOLD)
        self.max_scroll=max(0,y+self.scroll-content.bottom+22); self.screen.set_clip(None)
        self.text('Колесо — прокрутка · окно наблюдения · данные обновляются из сохранения',30,height-30,MUTED,self.small); pg.display.flip()


def main():
    reader=SnapshotReader(Path(sys.argv[1])); view=IndustryView(reader.read(),sys.argv[2]); parent=int(sys.argv[3]); clock=pg.time.Clock(); last=0
    try:
        while parent_alive(parent):
            for event in pg.event.get():
                if event.type==pg.QUIT: return
                if event.type==pg.VIDEORESIZE: view.screen=pg.display.set_mode((max(1050,event.w),max(650,event.h)),pg.RESIZABLE)
                elif event.type==pg.MOUSEWHEEL: view.scroll=max(0,min(view.max_scroll,view.scroll-event.y*48))
                elif event.type==pg.MOUSEBUTTONDOWN and event.button==1:
                    for rect,action in view.buttons:
                        if rect.collidepoint(event.pos): view.tab=int(action.split(':')[1]); view.scroll=0; break
            if time.monotonic()-last>1.5:
                try: view.world=reader.read()
                except (OSError,ValueError,sqlite3.Error): pass
                last=time.monotonic()
            view.draw(); clock.tick(15)
    finally: reader.close(); pg.quit()

if __name__=='__main__': main()
