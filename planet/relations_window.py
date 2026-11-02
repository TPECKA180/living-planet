"""Independent pygame window for one state's private diplomatic perspective."""
from contextlib import closing
import json
import sqlite3
import sys
import time
from pathlib import Path

import pygame as pg

from .console_monitor import parent_alive
from .engine import World
from .modern_catalog import RESOURCE_NAMES

BG=(13,19,26); PANEL=(23,32,42); TEXT=(225,232,232); MUTED=(141,157,164)
GREEN=(92,207,178); RED=(235,126,109); GOLD=(223,178,103)
LABELS=RESOURCE_NAMES
STANCES=dict(neutral='Нейтральная оценка',friend='Партнёр',rival='Соперник',enemy='Враждебная оценка')


def read_world(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        row=db.execute('SELECT data FROM snapshot WHERE id=1').fetchone()
    return World.restore(json.loads(row[0]))


class SnapshotReader:
    """Keep read-only connection; SQLite data_version detects actual commits."""
    def __init__(self,path):
        self.db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
        self.version=None; self.world=None
    def read(self):
        version=self.db.execute('PRAGMA data_version').fetchone()[0]
        if self.world is None or version!=self.version:
            row=self.db.execute('SELECT data FROM snapshot WHERE id=1').fetchone()
            self.world=World.restore(json.loads(row[0])); self.version=version
        return self.world
    def close(self): self.db.close()


class RelationsView:
    def __init__(self,world,sid):
        pg.init(); self.screen=pg.display.set_mode((1120,820),pg.RESIZABLE)
        self.world=world; self.sid=sid; self.peer=next(s.id for s in world.states if s.id!=sid)
        self.font=pg.font.SysFont('segoeui',18); self.small=pg.font.SysFont('segoeui',14)
        self.heading=pg.font.SysFont('segoeui',27,bold=True)
        self.tab=0; self.scroll=0; self.buttons=[]; self.max_scroll=0
        self.forecast=None; self.forecast_world=None
        pg.display.set_caption(f'Живая планета v7.5.2 · Отношения · {world.state(sid).name}')

    def text(self,value,x,y,color=TEXT,font=None): self.screen.blit((font or self.font).render(str(value),True,color),(x,y))
    def box(self,rect,color=PANEL): pg.draw.rect(self.screen,color,rect,border_radius=10)
    def wrap(self,value,x,y,width,color=TEXT,font=None):
        font=font or self.font
        for paragraph in str(value).split('\n'):
            line=''
            for word in paragraph.split():
                if line and font.size(line+' '+word)[0]>width:
                    self.text(line,x,y,color,font); y+=font.get_linesize()+4; line=''
                line=(line+' '+word).strip()
            self.text(line,x,y,color,font); y+=font.get_linesize()+4
        return y

    def button(self,label,rect,action,active=False):
        self.box(rect,GREEN if active else (38,50,62)); self.text(label,rect[0]+12,rect[1]+10,BG if active else TEXT,self.small)
        self.buttons.append((pg.Rect(rect),action))

    def draw(self):
        self.buttons=[]; self.screen.fill(BG); width,height=self.screen.get_size()
        state=self.world.state(self.sid); peer=self.world.state(self.peer)
        self.text(f'{state.name} · ПОЛИТИЧЕСКОЕ ДОСЬЕ',26,23,state.color,self.heading)
        self.text(f'День {self.world.day} · личная оценка государства и подтверждённые события',28,63,MUTED,self.small)
        for i,other in enumerate(s for s in self.world.states if s.id!=state.id):
            record=self.world.relation(state.id,other.id); y=114+i*104
            self.button(other.name,(26,y,250,92),'peer:'+other.id,other.id==self.peer)
            color=BG if other.id==self.peer else MUTED
            self.wrap(f'Доверие {record["trust"]:+d} · {STANCES[record["stance"]]}',39,y+44,226,color,self.small)
        x=300; w=width-x-26
        self.box((x,104,w,height-130))
        record=self.world.relation(state.id,peer.id)
        self.text(f'{state.name} → {peer.name}',x+22,122,peer.color,self.heading)
        actual=self.world.conflict_status(state.id,peer.id)
        self.text(actual,x+w-110,130,RED if actual=='ВОЙНА' else GREEN)
        self.text(f'Доверие {record["trust"]:+d}/100  ·  сделок {record["trade_count"]}',x+24,164,MUTED)
        self.text('Торговля: '+dict(normal='Обычная',preferred='Предпочтительный партнёр',avoid='Избегать')[record['trade_policy']],x+24,195,GOLD)
        if self.world.economic_block(state.id,peer.id): self.text('ЭМБАРГО',x+w-126,195,RED)
        for i,label in enumerate(('Досье','Экономика','Хроника')):
            self.button(label,(x+22+i*150,238,140,37),'tab:'+str(i),self.tab==i)
        content=pg.Rect(x+24,297,w-48,height-352); self.screen.set_clip(content)
        y=content.y-self.scroll
        if self.tab==0:
            for treaty in self.world.vassal_treaties:
                if treaty['status']=='active' and {state.id,peer.id}=={treaty['lord'],treaty['subject']}:
                    y=self.wrap(f"ВАССАЛЬНЫЙ ДОГОВОР\n{self.world.state(treaty['subject']).name} платит {treaty['tribute_percent']}% денежного дохода; {self.world.state(treaty['lord']).name} обязан защищать. До дня {treaty['until_day']}; выплачено {treaty['paid_total']:g}.",content.x,y,content.width,GOLD,self.small)+18
            y=self.wrap('ОЦЕНКА И НАМЕРЕНИЯ',content.x,y,content.width,GREEN,self.small)+9
            y=self.wrap(record['memo'] or 'Государство ещё не сформировало отдельную оценку.',content.x,y,content.width)+20
            incoming=[m for m in self.world.messages if m['sender']==peer.id and m['recipient'] in (state.id,'all')]
            if incoming:
                y=self.wrap('ПОСЛЕДНИЕ СЛОВА ПАРТНЁРА',content.x,y,content.width,MUTED,self.small)+7
                y=self.wrap(incoming[-1]['text'][:600],content.x,y,content.width,TEXT,self.small)+18
            y=self.wrap('ОБИДЫ И ПРИЧИНЫ НЕДОВЕРИЯ',content.x,y,content.width,GOLD,self.small)+9
            if not record['grievances']: y=self.wrap('Зафиксированных личных претензий пока нет.',content.x,y,content.width,MUTED)
            for grievance in reversed(record['grievances']): y=self.wrap(f"День {grievance['day']} · {grievance['text']}",content.x,y,content.width)+12
            y+=16
            y=self.wrap('ТРАНЗАКЦИИ',content.x,y,content.width,GREEN,self.small)+9
            imports=', '.join(f'{LABELS.get(k,k)} {v}' for k,v in record['imports'].items()) or 'нет'
            exports=', '.join(f'{LABELS.get(k,k)} {v}' for k,v in record['exports'].items()) or 'нет'
            y=self.wrap(f"Импорт: {imports}\nЭкспорт: {exports}\nУплачено: {record['paid']} · получено: {record['received']}",content.x,y,content.width,MUTED)
            if record['peace_requested']: y=self.wrap('Это государство предложило прекращение войны.',content.x,y+12,content.width,GOLD)
            for pledge in reversed(self.world.political_context(state)['pledges']):
                if {pledge['sender'],pledge['recipient']}=={state.id,peer.id}:
                    y=self.wrap(f"Обещание #{pledge['id']}: {pledge['kind']} · {pledge['status']} · срок {pledge['due_day']} · поставлено {pledge['delivered']}/{pledge['amount']}",content.x,y+12,content.width,GOLD,self.small)
        elif self.tab==1:
            if self.forecast_world is not self.world:
                self.forecast=self.world.economic_forecast(state); self.forecast_world=self.world
            forecast=self.forecast
            y=self.wrap('СОБСТВЕННЫЕ ПОТРЕБНОСТИ ПЕРЕД ТОРГОВЛЕЙ',content.x,y,content.width,GREEN,self.small)+10
            for key,item in forecast['resources'].items():
                label=LABELS.get(key,key)
                y=self.wrap(f"{label}: {item['stock']:g} · добыча +{item['production']:g} · содержание −{item['upkeep']:g} · ожидаемый баланс {item['net']:+g}/день",content.x,y,content.width,RED if item['net']<0 else TEXT,self.small)+6
            y+=12
            for offer in self.world.trade_offers:
                if offer['status']=='open' and offer['partner']==state.id and offer['seller']==peer.id:
                    a=self.world.assess_trade(state,offer,forecast)
                    y=self.wrap(f"Сделка #{offer['id']}: {offer['amount']} {LABELS[offer['resource']]} за {a['total']}. Нужда: {dict(high='высокая',medium='средняя',low='низкая')[a['need']]}",content.x,y,content.width,GOLD)+6
                    for flag in a['risk_flags']: y=self.wrap(flag,content.x,y,content.width,RED,self.small)+6
            y=self.wrap(forecast['basis'],content.x,y+10,content.width,MUTED,self.small)
        else:
            y=self.wrap('ПОДТВЕРЖДЁННЫЕ СОБЫТИЯ',content.x,y,content.width,GREEN,self.small)+10
            for fact in reversed(record['facts']):
                day=fact['day'] if fact['day'] is not None else 'неизвестен (импорт)'
                y=self.wrap(f"День {day} · {fact['text']}",content.x,y,content.width)+13
            letters=[m for m in self.world.messages if (m['sender']==state.id and m['recipient']==peer.id) or (m['sender']==peer.id and m['recipient'] in (state.id,'all'))]
            y=self.wrap('ПЕРЕПИСКА',content.x,y+14,content.width,GOLD,self.small)+10
            for letter in reversed(letters[-30:]): y=self.wrap(f"День {letter['day']} · {self.world.state(letter['sender']).name}: {letter['text']}",content.x,y,content.width,TEXT,self.small)+12
        self.max_scroll=max(0,y+self.scroll-content.bottom+12); self.screen.set_clip(None)
        self.text('Колесо — прокрутка · данные обновляются из сохранения',x+24,height-44,MUTED,self.small)
        pg.display.flip()


def main():
    path=Path(sys.argv[1]); sid=sys.argv[2]; parent=int(sys.argv[3])
    reader=SnapshotReader(path)
    view=RelationsView(reader.read(),sid); clock=pg.time.Clock(); last_refresh=time.monotonic()
    view.draw()
    while parent_alive(parent):
        for event in pg.event.get():
            if event.type==pg.QUIT: reader.close(); pg.quit(); return
            if event.type==pg.VIDEORESIZE: view.screen=pg.display.set_mode((max(1000,event.w),max(700,event.h)),pg.RESIZABLE)
            elif event.type==pg.MOUSEWHEEL: view.scroll=max(0,min(view.max_scroll,view.scroll-event.y*42))
            elif event.type==pg.MOUSEBUTTONDOWN and event.button==1:
                for rect,action in view.buttons:
                    if rect.collidepoint(event.pos):
                        if action.startswith('peer:'): view.peer=action.split(':')[1]
                        else: view.tab=int(action.split(':')[1])
                        view.scroll=0; break
        if time.monotonic()-last_refresh>1.5:
            try: view.world=reader.read()
            except (OSError,ValueError,sqlite3.Error): pass
            last_refresh=time.monotonic()
        view.draw(); clock.tick(20)
    reader.close(); pg.quit()


if __name__=='__main__': main()
