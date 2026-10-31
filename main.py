"""Run: python main.py. All network work runs outside pygame's event thread."""
import argparse
import json
import os
import queue
import threading
import time
import sys
import subprocess
from pathlib import Path

from planet.brain import Brain, AutomaticRetry
from planet.console_feed import ConsoleFeed
from planet.engine import Store, World
from planet.saves import WorldLibrary

from planet.modern_catalog import BUILDINGS as MODERN_BUILDINGS,UNITS as MODERN_UNITS,RESOURCE_NAMES
ROOT=Path(__file__).resolve().parent
BG=(13,20,27); PANEL=(22,31,40); TEXT=(223,233,237); MUTED=(137,158,169); ACCENT=(92,207,178)
TERRAIN={'grass':(61,92,64),'forest':(30,64,49),'mountain':(111,119,120),'water':(26,55,80),'science':(98,76,140),'resource':(137,108,58)}
LABELS={'grass':'Трава','forest':'Лес','mountain':'Горы','water':'Вода','science':'Наука','resource':'Ресурс'}
UNIT_LABELS={'scout':'Разведчик','builder':'Строитель','army':'Армия','ship':'Корабль'}
BUILDING_LABELS={'lab':'Лаборатория','castle':'Замок','mine':'Шахта','tavern':'Таверна','arsenal':'Арсенал','tower':'Башня','wall':'Стена'}
BUILDING_LABELS.update({k:v['name'] for k,v in MODERN_BUILDINGS.items()})
UNIT_LABELS.update({k:v['name'] for k,v in MODERN_UNITS.items()})


class Runner:
    def __init__(self,world,store,config):
        self.world,self.store,self.config=world,store,config
        self.messages=queue.Queue(); self.busy=False
        self.console=ConsoleFeed(store.path.parent,config.get('external_console',False))
        self.brain=Brain(config,observer=self.observe)

    def observe(self,kind,text='',**data):
        self.console.emit(kind,text,**data)
        if kind=='status': self.messages.put(('status',text))

    def tick(self):
        if self.busy: return
        self.busy=True
        threading.Thread(target=self.work,daemon=True).start()

    def prepare_actor(self,w,state,decision,legacy=False):
        if self.config.get('local_execution',False):
            from planet.local_execution import prepare_locally
            self.messages.put(('status','Локальная проверка приказов · '+state.name+' · без нейросети'))
            return prepare_locally(w,state,decision,self.config)
        from planet.learning import decision_signature
        self.messages.put(('status','Подготовка приказов · '+state.name))
        if legacy:
            if self.config.get('deep_strategy',False):decision=self.brain.review_strategy(state,w.context(state,self.config),decision)
            elif self.config.get('review_relations',False):decision=self.brain.review_relationships(state,w.context(state,self.config),decision)
        decision=self.brain.prepare_execution(w,state,decision)
        self.brain.bind_actor(state.id)
        decision=self.brain.russify(decision,self.config.get('state_models',{}).get(state.id) or self.config.get('model'))
        decision['execution_ready']=dict(day=w.day,signature=decision_signature(decision))
        return decision

    def work(self):
        try:
            w=self.world
            if not w.in_day:
                w.start_day(); self.store.save(w); self.messages.put(('world',self.store.last_snapshot))
            brain=self.brain
            if w.phase=='planning' and w.cursor<len(w.states):
                s=w.states[w.cursor]
                self.console.emit('progress',day=w.day,completed=w.cursor,total=len(w.states))
                self.console.emit('request_start',f'День {w.day} · {s.name} · подготовка модели и контекста')
                self.messages.put(('status',f'День {w.day}: решение {w.cursor+1}/{len(w.states)} · {s.name}'))
                decision=w.pending_decisions.get(s.id)
                if decision is None:
                    decision=(dict(thinking='Государство выбыло; история сохранена.',notes=s.notes,plan=s.plan,diplomacy=[],actions=[]) if s.eliminated else brain.think(s,w.context(s,self.config)))
                    w.pending_decisions[s.id]=decision; self.store.save(w)
                    self.messages.put(('world',self.store.last_snapshot))
                if not s.eliminated:
                    if not self.config.get('local_execution',False) and not self.config.get('unified_execution_review',False):
                        decision=brain.review_construction(s,w.context(s,self.config),decision)
                        w.pending_decisions[s.id]=decision; self.store.save(w)
                        decision=brain.review_economy(s,w.context(s,self.config),decision)
                        w.pending_decisions[s.id]=decision; self.store.save(w)
                    if not self.config.get('local_execution',False) and self.config.get('deep_strategy',False):
                        self.messages.put(('status','Разбор и досье · '+s.name))
                        decision=brain.review_strategy(s,w.context(s,self.config),decision)
                    elif not self.config.get('local_execution',False) and self.config.get('review_relations',False): decision=brain.review_relationships(s,w.context(s,self.config),decision)
                    decision=self.prepare_actor(w,s,decision)
                    w.pending_decisions[s.id]=decision
                w.cursor+=1
                if w.cursor==len(w.states): w.phase='resolution'
                self.store.save(w)
                self.console.emit('progress',day=w.day,completed=w.cursor,total=len(w.states))
            elif w.phase in ('resolution','planning','preparing'):
                from planet.learning import ready
                unfinished=[(sid,d) for sid,d in w.pending_decisions.items() if not w.state(sid).eliminated and not ready(d,w.day)]
                if unfinished:
                    w.phase='preparing';self.store.save(w)
                    self.messages.put(('world',self.store.last_snapshot))
                    self.messages.put(('status','Подготовка старых решений: проверка приказов, не общее исполнение'))
                    for sid,decision in unfinished:
                        decision=self.prepare_actor(w,w.state(sid),decision,legacy=True)
                        w.pending_decisions[sid]=decision;self.store.save(w)
                w.phase='resolution'
                self.messages.put(('activity','execution'))
                candidate=World.restore(w.data())
                candidate.resolve_round()
                self.store.save(candidate);self.world=w=candidate
            elif w.phase=='manager':
                candidate=World.restore(w.data())
                if w.day % max(1,int(self.config.get('manager_every',10))) == 0:
                    if self.config.get('local_chronicle',False):
                        from planet.local_chronicle import chapter_event
                        self.messages.put(('status','Локальное подведение итогов · без нейросети'))
                        candidate.manager(chapter_event(candidate))
                    else:
                        self.messages.put(('status','Менеджер создаёт новую главу…'))
                        candidate.manager(brain.manager(candidate))
                candidate.in_day=False; candidate.cursor=0; candidate.phase='idle'
                self.store.save(candidate); self.world=w=candidate
            self.messages.put(('world',self.store.last_snapshot))
        except AutomaticRetry as exc:
            if getattr(exc,'owner',None) in self.world.pending_decisions and isinstance(getattr(exc,'repaired_decision',None),dict):
                self.world.pending_decisions[exc.owner]=exc.repaired_decision;self.store.save(self.world)
            self.console.emit('status',str(exc))
            self.messages.put(('world',self.world.data()))
            self.messages.put(('retry',str(exc)))
        except (RuntimeError,ValueError,KeyError,TypeError) as exc:
            self.console.emit('status','Автовосстановление: '+str(exc))
            self.messages.put(('world',self.world.data()))
            self.messages.put(('retry','Автоматический повтор без пропуска дня: '+str(exc)))
        except Exception as exc:
            from planet.diagnostics import record
            record(ROOT/'logs',exc,'simulation')
            self.console.emit('error',str(exc))
            self.messages.put(('world',self.world.data()))
            self.messages.put(('error',str(exc)))
        finally:
            self.messages.put(('done',None))


def settings(config):
    from planet.dialogs import edit_settings
    return edit_settings(ROOT,config)


class App:
    def __init__(self,world,store,config):
        import pygame as pg
        self.pg=pg; pg.init(); pg.display.set_caption('Живая планета · v7.0.1 · лаборатория миров')
        self.screen=pg.display.set_mode((1440,900),pg.RESIZABLE)
        self.font=pg.font.SysFont('segoeui',17); self.small=pg.font.SysFont('segoeui',14)
        self.title=pg.font.SysFont('segoeui',30,bold=True); self.medium=pg.font.SysFont('segoeui',21,bold=True)
        self.world=World.restore(world.data()); self.runner=Runner(world,store,config); self.config=config
        self.selected=0; self.tab=0; self.scroll=0; self.running=False; self.target_day=None
        self.status=f'Завершено дней: {world.day-int(world.in_day)}. '+('Продолжим сохранённый общий ход.' if world.in_day else 'Мир готов.'); self.error=''; self.zoom=1.; self.pan=[0.,0.]
        self.drag=None; self.tile=None; self.buttons=[]; self.map_dirty=True; self.map_surface=None
        self.switch_requested=False; self.unit_markers=[]
        self.retry_after=0
        self.activity=None
        self.chronicle_tab=0;self.learning_scroll=0;self.learning_max_scroll=0
        from planet.pixel_art import PixelAtlas
        self.atlas=PixelAtlas(); self.forecasts={}; self.view_positions={}; self.strategy_cache={}; self.construction_cache={}; self.relation_windows={}; self.industry_windows={}
        self.focus_unit_id=None; self.preview_key=None; self.preview_route=None; self.map_notice=''
        from planet.text_layout import TextLayout
        self.text_layout=TextLayout()

    def text(self,text,x,y,color=TEXT,font=None):
        font=font or self.font
        clip=self.screen.get_clip()
        if y+font.get_linesize()<clip.top or y>clip.bottom: return
        # Direct labels occupy one screen line; never allocate a text surface
        # spanning an entire large model answer. Full prose uses wrapped().
        value=str(text).replace('\x00','�')[:4096]
        self.screen.blit(font.render(value,True,color),(x,y))

    def box(self,rect,color=PANEL,radius=14):
        self.pg.draw.rect(self.screen,color,rect,border_radius=radius)

    def button(self,label,rect,action,active=False):
        self.box(rect,ACCENT if active else (36,49,60),9)
        previous=self.screen.get_clip(); self.screen.set_clip(self.pg.Rect(rect).inflate(-12,-4).clip(previous))
        self.text(label,rect[0]+14,rect[1]+9,BG if active else TEXT,self.small)
        self.screen.set_clip(previous)
        self.buttons.append((self.pg.Rect(rect),action))

    def wrapped(self,text,x,y,width,font=None,color=TEXT):
        font=font or self.font; step=font.get_linesize()+3
        lines=self.text_layout.lines(str(text).replace('\x00','�'),max(1,width),font)
        clip=self.screen.get_clip()
        first=max(0,int((clip.top-y)//step)-1)
        last=min(len(lines),max(0,int((clip.bottom-y)//step)+2))
        for index in range(first,last): self.text(lines[index],x,y+index*step,color,font)
        return y+len(lines)*step

    def render_map(self):
        pg=self.pg; w=self.world; surface=pg.Surface((w.size*4,w.size*4))
        colors={s.id:s.color for s in w.states}
        for i,c in enumerate(w.cells):
            x,y=i%w.size,i//w.size; color=TERRAIN[c.terrain]
            if c.owner:
                owner=colors[c.owner]; color=tuple(int(a*.65+b*.35) for a,b in zip(color,owner))
            pg.draw.rect(surface,color,(x*4,y*4,4,4))
            if c.population: surface.set_at((x*4+1,y*4+1),(245,239,209))
            if c.building:
                pg.draw.rect(surface,(245,232,185),(x*4,y*4,3,3),1)
        self.map_surface=surface; self.map_dirty=False

    def draw_units(self):
        pg=self.pg; self.unit_markers=[]; occupied=[]
        colors={s.id:s.color for s in self.world.states}
        for unit in sorted(self.world.units,key=lambda u:u['id']):
            if unit.get('embarked_on'): continue
            x,y=unit['cell']; ax=self.origin[0]+(x+.5)*self.scale; ay=self.origin[1]+(y+.5)*self.scale
            if not self.map_rect.inflate(-16,-16).collidepoint(ax,ay): continue
            if self.scale>=22:
                size=max(1,int(self.scale)); px=int(self.origin[0]+x*self.scale); py=int(self.origin[1]+y*self.scale)
                self.screen.blit(self.atlas.sized(self.atlas.unit(unit['type'],colors[unit['owner']]),size),(px,py))
                hit=pg.Rect(px+size//2,py+size//4,max(12,size//2),max(16,size*3//4))
                pg.draw.rect(self.screen,(24,28,35),(px+size//2,py+size-3,max(10,size//2-2),3))
                pg.draw.rect(self.screen,colors[unit['owner']],(px+size//2,py+size-3,int(max(10,size//2-2)*min(1,unit['strength']/max(1,unit.get('max_strength',10)))),3))
                if self.scale>=34: self.text(str(unit['id']),px+size-12,py+2,TEXT,self.small)
                self.unit_markers.append((hit,unit)); continue
            rect=pg.Rect(int(ax)-10,int(ay)-11,42 if self.scale>=10 else 24,26)
            for _ in range(12):
                if not any(rect.colliderect(r.inflate(4,4)) for r in occupied): break
                rect.y-=29
            rect.clamp_ip(self.map_rect.inflate(-16,-16)); occupied.append(rect)
            center=(rect.x+11,rect.y+11)
            pg.draw.line(self.screen,(217,228,225),(ax,ay),center,1)
            self.box(rect,(13,21,28),5)
            color=colors[unit['owner']]; cx,cy=center
            if unit['type']=='scout': pg.draw.polygon(self.screen,color,[(cx,cy-8),(cx-8,cy+6),(cx+8,cy+6)])
            elif unit['type']=='builder': pg.draw.rect(self.screen,color,(cx-7,cy-7,14,14),2)
            else: pg.draw.polygon(self.screen,color,[(cx,cy-9),(cx-9,cy),(cx,cy+9),(cx+9,cy)])
            if self.scale>=10: self.text(str(unit['id']),rect.x+23,rect.y+1,TEXT,self.small)
            pg.draw.rect(self.screen,(57,66,73),(rect.x+3,rect.bottom-4,rect.width-6,2))
            pg.draw.rect(self.screen,color,(rect.x+3,rect.bottom-4,int((rect.width-6)*min(1,unit['strength']/max(1,unit.get('max_strength',10)))),2))
            self.unit_markers.append((rect,unit))

    def draw_movement(self):
        colors={s.id:s.color for s in self.world.states}
        for move in self.world.movement_log:
            if move['day']!=self.world.day or not move.get('arrived',True): continue
            points=[(self.origin[0]+(p[0]+.5)*self.scale,self.origin[1]+(p[1]+.5)*self.scale) for p in (move['source'],move['target'])]
            color=colors.get(move['owner'],ACCENT)
            self.pg.draw.line(self.screen,color,points[0],points[1],2)
            self.pg.draw.circle(self.screen,color,(int(points[1][0]),int(points[1][1])),max(2,min(5,int(self.scale/5))))

    def draw_route_preview(self):
        self.map_notice=''
        if self.focus_unit_id is None or self.scale<12: return
        mouse=self.pg.mouse.get_pos()
        if not self.map_rect.collidepoint(mouse): return
        x=int((mouse[0]-self.origin[0])//self.scale); y=int((mouse[1]-self.origin[1])//self.scale)
        if not(0<=x<self.world.size and 0<=y<self.world.size): return
        unit=next((u for u in self.world.units if u['id']==self.focus_unit_id),None)
        if not unit: return
        cell=self.world.cell([x,y]); state=self.world.state(unit['owner'])
        if not self.world.terrain_allowed(unit,[x,y]):
            self.map_notice='ЗАПРЕТ СРЕДЫ · суша для пехоты, вода для корабля · оплата 0'
            px=self.origin[0]+x*self.scale; py=self.origin[1]+y*self.scale
            self.pg.draw.line(self.screen,(235,126,109),(px+3,py+3),(px+self.scale-3,py+self.scale-3),2)
            self.pg.draw.line(self.screen,(235,126,109),(px+self.scale-3,py+3),(px+3,py+self.scale-3),2)
            return
        if abs(x-unit['cell'][0])+abs(y-unit['cell'][1])>24: return
        key=(unit['id'],x,y,id(self.world))
        if key!=self.preview_key:
            self.preview_key=key; self.preview_route=self.world.find_route(unit,[x,y])
        if self.preview_route is None: self.map_notice='ПРОХОД ЗАКРЫТ · вода, занятые клетки или границы союзника'; return
        points=[unit['cell']]+self.preview_route
        if len(points)>1:
            line=[(self.origin[0]+(p[0]+.5)*self.scale,self.origin[1]+(p[1]+.5)*self.scale) for p in points]
            self.pg.draw.lines(self.screen,(220,197,126),False,line,2)
        self.map_notice=f'Просмотр пути: {len(self.preview_route)} шагов · это просмотр, не приказ'

    def open_industry(self):
        sid=self.world.states[self.selected].id
        previous=self.industry_windows.get(sid)
        if previous is not None and previous.poll() is None:
            self.status='Расширенная экономика этой страны уже открыта'; return
        self.industry_windows[sid]=subprocess.Popen([sys.executable,'-m','planet.industry_window',str(self.runner.store.path.resolve()),sid,str(os.getpid())],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.status='Открыта расширенная экономика: '+self.world.state(sid).name

    def open_relations(self):
        sid=self.world.states[self.selected].id
        previous=self.relation_windows.get(sid)
        if previous is not None and previous.poll() is None:
            self.status='Окно отношений этого государства уже открыто'; return
        self.relation_windows[sid]=subprocess.Popen([sys.executable,'-m','planet.relations_window',str(self.runner.store.path.resolve()),sid,str(os.getpid())],
            cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.status='Открыто отдельное окно отношений: '+self.world.states[self.selected].name

    def draw(self):
        pg=self.pg; width,height=self.screen.get_size(); self.buttons=[]; self.screen.fill(BG)
        self.text('ЖИВАЯ ПЛАНЕТА',28,21,font=self.title)
        self.text('7.0.1  /  АВТОНОМНЫЕ ГОСУДАРСТВА · ЛОКАЛЬНЫЙ ИНТЕЛЛЕКТ',30,62,MUTED,self.small)
        self.text(f'ДЕНЬ {self.world.day:04d}',width-195,24,ACCENT,self.medium)
        phase={'idle':'Общий ход завершён','planning':f'Решения {self.world.cursor}/{len(self.world.states)}','resolution':'Общее исполнение','preparing':'Подготовка приказов','manager':'Итоги дня'}[self.world.phase]
        if self.activity=='diplomacy': phase='Стратегия и отношения'
        self.text(phase,width-225,56,MUTED,self.small)
        completed=len(self.world.pending_decisions) if self.world.in_day else len(self.world.states)
        self.box((width-225,81,195,5),(39,54,62),2)
        self.box((width-225,81,max(3,int(195*completed/max(1,len(self.world.states)))),5),ACCENT,2)
        self.button('Пауза' if self.running else 'Наблюдать',(28,99,126,38),'run',self.running)
        self.button('Один день',(164,99,116,38),'day')
        self.button('LM Studio · F2',(290,99,145,38),'settings')
        self.button('Хроника ↓',(445,99,117,38),'export')
        self.button('Миры',(572,99,80,38),'worlds')
        self.button('Справка · F1',(662,99,125,38),'help')
        self.text(('● РАБОТАЕТ' if self.runner.busy else 'ПАУЗА' if not self.running else '● НАБЛЮДЕНИЕ'),804,108,ACCENT if self.runner.busy else MUTED,self.small)
        side=430; map_width=width-side-66; map_height=height-385
        self.map_rect=pg.Rect(28,157,map_width,map_height)
        self.box(self.map_rect)
        if self.map_dirty: self.render_map()
        factor=min((map_width-32)/self.world.size,(map_height-32)/self.world.size)*self.zoom
        size=max(1,int(self.world.size*factor)); self.scale=factor
        ox=self.map_rect.centerx-size//2+self.pan[0]; oy=self.map_rect.centery-size//2+self.pan[1]
        self.origin=(ox,oy)
        self.screen.set_clip(self.map_rect.inflate(-8,-8))
        if factor>=12: self.atlas.draw_world(self.screen,self.world,self.map_rect,(ox,oy),factor)
        else: self.screen.blit(pg.transform.scale(self.map_surface,(size,size)),(ox,oy))
        self.draw_movement()
        self.draw_route_preview()
        self.draw_units()
        if self.tile:
            x,y=self.tile; pg.draw.rect(self.screen,(255,245,210),(ox+x*factor,oy+y*factor,max(3,factor),max(3,factor)),1)
        self.screen.set_clip(None)
        self.text(f'МИР / {self.world.seed} · {self.world.size}×{self.world.size}',44,167,(221,233,233),self.small)
        for i,(kind,label) in enumerate((('scout','Разведчик'),('builder','Строитель'),('army','Армия'))):
            cx=51+i*120; cy=201
            if kind=='scout': pg.draw.polygon(self.screen,ACCENT,[(cx,cy-6),(cx-6,cy+5),(cx+6,cy+5)])
            elif kind=='builder': pg.draw.rect(self.screen,ACCENT,(cx-6,cy-6,12,12),2)
            else: pg.draw.polygon(self.screen,ACCENT,[(cx,cy-7),(cx-7,cy),(cx,cy+7),(cx+7,cy)])
            self.text(label,cx+12,190,TEXT,self.small)
        self.text('Полоска = сила',414,190,TEXT,self.small)
        if self.map_notice:
            self.box((40,216,map_width-24,26),(17,24,31),4)
            self.text(self.map_notice[:115],48,220,(224,182,122),self.small)
        legend_y=self.map_rect.bottom+12
        for i,(terrain,color) in enumerate(TERRAIN.items()):
            x=34+i*(map_width//6)
            pg.draw.rect(self.screen,color,(x,legend_y+3,9,9),border_radius=2)
            self.text(LABELS[terrain],x+15,legend_y,MUTED,self.small)
        self.text('Клик по юниту — карточка · колесо — масштаб · перетаскивание — обзор · R — вся карта',32,legend_y+26,MUTED,self.small)
        sx=width-side-22; sy=157
        self.box((sx,sy,side,height-179))
        self.text('ГОСУДАРСТВА',sx+20,sy+17,MUTED,self.small)
        for i,s in enumerate(self.world.states):
            bw=(side-40)//len(self.world.states)
            label=s.name if len(self.world.states)<=4 else s.name[:3]+'…'
            self.button(label,(sx+18+i*bw,sy+44,bw-5,35),f'state:{i}',i==self.selected)
            if s.id in self.world.pending_decisions:
                pg.draw.circle(self.screen,BG if i==self.selected else ACCENT,(sx+18+i*bw+bw-13,sy+51),3)
        s=self.world.states[self.selected]
        self.text(s.name+(' · выбыло' if s.eliminated else ' · II' if self.world.era_for(s)==2 else ''),sx+20,sy+96,s.color,self.title)
        self.box((sx+230,sy+102,83,30),(34,52,60),7)
        self.text('ЭПОХА '+str(self.world.era_for(s)),sx+240,sy+109,ACCENT,self.small)
        self.button('Расширить',(sx+319,sy+102,91,30),'industry')
        if s.id not in self.view_positions: self.view_positions[s.id]=self.world.positions(s.id)
        own=self.view_positions[s.id]; population=sum(self.world.cell(p).population for p in own)
        self.text(f'{len(own)} клеток   ·   {population} жителей   ·   {len(s.tech)} технологий',sx+20,sy+136,MUTED,self.small)
        stats=self.world.day_stats.get(s.id,{})
        self.text(f'Сегодня: шагов {stats.get("steps",0)} · территория {stats.get("territory_delta",0):+d} · найм {stats.get("recruited",0)}',sx+20,sy+155,ACCENT,self.small)
        resource_labels={'food':'Еда','resource':'Сырьё','metal':'Металл','science':'Наука','matter':'Материя','money':'Деньги'}
        if s.id not in self.forecasts: self.forecasts[s.id]=self.world.economic_forecast(s)
        forecast=self.forecasts[s.id]; self.resource_rects=[]
        for i,(key,label) in enumerate(resource_labels.items()):
            x=sx+20+(i%3)*132; y=sy+177+(i//3)*64; item=forecast['resources'][key]
            self.box((x-4,y-3,128,61),(28,40,48),7)
            self.text(label,x,y,MUTED,self.small); self.text(f'{s.stocks[key]:,.0f}'.replace(',',' '),x,y+17,font=self.medium)
            value=item['net']; color=(235,126,109) if value<0 else (223,178,103) if item['production']<1 else ACCENT
            balance=f'≈ {value:+g}/день' if value else '0/д · нет добычи' if item['production']<1 else '≈ 0/день'
            self.text(balance,x,y+42,color,self.small)
            self.resource_rects.append((pg.Rect(x,y,128,62),key))
        for i,label in enumerate(('Решение','Память','Приказы','Диплом.','Юниты','Отнош.','Техно','Стратег.','Разбор','Стройка')):
            self.button(label,(sx+18+(i%5)*79,sy+314+(i//5)*38,75,32),'relations' if i==5 else f'tab:{i}',self.tab==i)
        content=pg.Rect(sx+20,sy+400,side-40,height-sy-430)
        self.screen.set_clip(content)
        y=content.y-self.scroll
        opponents=[other.name for other in self.world.states if other.id!=s.id and self.world.conflict_status(s.id,other.id)=='ВОЙНА']
        y=self.wrapped('ФАКТ · '+('Война: '+', '.join(opponents) if opponents else 'Активных войн нет')+f' · день {self.world.day}',content.x,y,content.width,self.small,(239,174,91))+12
        if self.tab==0:
            pending=self.world.pending_decisions.get(s.id,{})
            if pending: y=self.wrapped('РЕШЕНИЕ ГОТОВО · ждёт общего исполнения',content.x,y,content.width,self.small,ACCENT)+10
            y=self.wrapped('ОБЪЯСНЕНИЕ РЕШЕНИЯ',content.x,y,content.width,self.small,ACCENT)+10
            y=self.wrapped(pending.get('thinking',s.thinking),content.x,y,content.width)+22
            y=self.wrapped('ПЛАН НА 10 ДНЕЙ',content.x,y,content.width,self.small,ACCENT)+10
            y=self.wrapped(pending.get('plan',s.plan),content.x,y,content.width)
        elif self.tab==1:
            y=self.wrapped('ПОСТОЯННАЯ ПАМЯТЬ',content.x,y,content.width,self.small,ACCENT)+10
            y=self.wrapped(s.notes,content.x,y,content.width)+14
            y=self.wrapped(f'Сохранено версий памяти: {len(s.memory)}\nТехнологии: {", ".join(s.tech) or "пока нет"}\nСоюзы: {", ".join(s.allies) or "пока нет"}',content.x,y,content.width,self.small,MUTED)
        elif self.tab==2:
            for item in reversed([h for h in s.history if h['day']>self.world.day-10]):
                y=self.wrapped(f"День {item['day']} · {item['text']}",content.x,y,content.width,self.small)+12
        elif self.tab==3:
            y=self.wrapped('ПЕРЕПИСКА И ТОРГОВЛЯ',content.x,y,content.width,self.small,ACCENT)+10
            commerce=self.world.commerce_context(s)
            review=self.world.pending_decisions.get(s.id,{}).get('economic_review') or s.economic_review
            if review:
                modes=dict(execute='Реальные приказы',negotiate='Переговоры',deceive='Частный замысел: обман',decline='Отказ',none='Без операций')
                y=self.wrapped(modes.get(review.get('mode'),review.get('mode',''))+'\n'+review.get('reason',''),content.x,y,content.width,self.small,(239,174,91))+15
            y=self.wrapped('Письмо не равно поставке. Фактические переводы имеют квитанции. Подробности — «Расширить» → «Сделки».',content.x,y,content.width,self.small,MUTED)+15
            for receipt in reversed(commerce['receipts'][-6:]):
                sender=self.world.state(receipt['sender']).name; recipient=self.world.state(receipt['recipient']).name
                bundle=', '.join(f"{RESOURCE_NAMES.get(k,k)} {v:g}" for k,v in receipt['resources'].items())
                y=self.wrapped(f"Квитанция #{receipt['id']} · день {receipt['day']}\n{sender} → {recipient}: {bundle}",content.x,y,content.width,self.small,ACCENT)+12
            for deal in reversed(commerce['exchanges'][-6:]):
                y=self.wrapped(f"Обмен #{deal['id']} · {deal['mode']} · {deal['status']}\nОжидается {deal.get('owed',{})} · срок {deal.get('due_day','ещё не принят')}",content.x,y,content.width,self.small,(239,174,91))+12
            names={other.id:other.name for other in self.world.states}; names['all']='Все'
            offers=[o for o in self.world.trade_offers if s.id in (o['seller'],o['partner']) and o['status']=='open']
            for offer in reversed(offers):
                y=self.wrapped(f"Сделка #{offer['id']}: {names[offer['seller']]} → {names[offer['partner']]}, {offer['amount']} {offer['resource']} по {offer['price']} денег. До дня {offer['expires']}.",content.x,y,content.width,self.small,(239,174,91))+12
            messages=[m for m in self.world.messages if m['sender']==s.id or m['recipient'] in (s.id,'all')]
            if not messages: y=self.wrapped('Первая переписка появится после общего исполнения дня. Каждое государство обязано отправить сообщение.',content.x,y,content.width,color=MUTED)
            for msg in reversed(messages):
                y=self.wrapped(f"День {msg['day']} · {names[msg['sender']]} → {names[msg['recipient']]}",content.x,y,content.width,self.small,ACCENT)+4
                y=self.wrapped(msg['text'],content.x,y,content.width)+16
        elif self.tab==6:
            y=self.wrapped('ТЕХНОЛОГИИ · ЭПОХА '+str(self.world.era_for(s)),content.x,y,content.width,self.small,ACCENT)+12
            for tech in self.world.research_catalog(s):
                status='ИССЛЕДОВАНО' if tech['researched'] else 'ДОСТУПНО' if tech['available'] else 'Нужны: '+', '.join(tech['requires'])
                y=self.wrapped(tech['name']+' · '+tech['id'],content.x,y,content.width,self.small,ACCENT if tech['researched'] else TEXT)+4
                if tech.get('cost'):
                    y=self.wrapped(status+'\nЦена: '+', '.join(f'{RESOURCE_NAMES.get(k,k)} {v:g}' for k,v in tech['cost'].items())+'\n'+tech['effect'],content.x,y,content.width,self.small,MUTED)+18
                    continue
                y=self.wrapped(status+f"\nЦена: {tech['money']} денег · {tech['science']} науки · {tech['matter']} материи\n{tech['effect']}",content.x,y,content.width,self.small,MUTED)+18
        elif self.tab==7:
            if s.id not in self.strategy_cache: self.strategy_cache[s.id]=self.world.strategic_context(s)
            strategy=self.strategy_cache[s.id]
            y=self.wrapped('СООТНОШЕНИЕ СИЛ · общие показатели',content.x,y,content.width,self.small,ACCENT)+10
            for i,row in enumerate(strategy['ranking']):
                text=f"{i+1}. {row['name']} · {'выбыло' if row['eliminated'] else str(row['score'])+' очков'}\nЗемля {row['territory']} · жители {row['population']} · сила войск {row['military_strength']}"
                y=self.wrapped(text,content.x,y,content.width,self.small)+14
            y=self.wrapped('База = клетки + 3×жители + 2×эфф.сила + 5×технологии + экономика производства. Сюзерену +25% базы вассалов; вассалу −15% своей базы за зависимость. Ориентир, не автоматическая победа.',content.x,y,content.width,self.small,MUTED)+18
            for peer,targets in strategy['border_targets'].items():
                y=self.wrapped('Общая сухопутная граница: '+self.world.state(peer).name+f' · видимых целей {len(targets)}',content.x,y,content.width,self.small,ACCENT)+12
            for demand in strategy['surrender_demands']:
                y=self.wrapped('УЛЬТИМАТУМ: '+self.world.state(demand['sender']).name+' → '+self.world.state(demand['recipient']).name+'\n'+demand['reason'],content.x,y,content.width,self.small,(239,174,91))+14
            politics=self.world.political_context(s)
            for treaty in politics['treaties']:
                if treaty['status']=='active': y=self.wrapped(f"Вассал: {self.world.state(treaty['subject']).name}\nСюзерен: {self.world.state(treaty['lord']).name}\nДань {treaty['tribute_percent']}% · до дня {treaty['until_day']} · выплачено {treaty['paid_total']:g}",content.x,y,content.width,self.small,ACCENT)+16
            for offer in politics['offers']:
                y=self.wrapped(f"Вассальный договор #{offer['id']}: {self.world.state(offer['lord']).name} → {self.world.state(offer['subject']).name}; дань {offer['tribute_percent']}%, срок {offer['duration']} дней. Ожидает согласия.",content.x,y,content.width,self.small,(239,174,91))+14
            for pledge in reversed(politics['pledges'][-12:]):
                y=self.wrapped(f"Обещание #{pledge['id']} · {pledge['kind']} · {pledge['status']}\n{self.world.state(pledge['sender']).name} → {self.world.state(pledge['recipient']).name} · до дня {pledge['due_day']}",content.x,y,content.width,self.small,MUTED)+12
        elif self.tab==9:
            if s.id not in self.construction_cache: self.construction_cache[s.id]=self.world.construction_context(s)
            construction=self.construction_cache[s.id]
            y=self.wrapped('СТРОЙКА · реальные проекты и цены',content.x,y,content.width,self.small,ACCENT)+10
            review=self.world.pending_decisions.get(s.id,{}).get('construction_review') or s.construction_review
            if review: y=self.wrapped(str(review.get('reason','')),content.x,y,content.width,self.small,(239,174,91))+16
            actual=review.get('execution_result',{}) if review else {}
            if actual:
                label=f"Факт дня {actual['day']}: построено {actual['built']}"
                if actual.get('rejected'): label+=' · отказы: '+'; '.join(actual['rejected'])
                if actual.get('status')=='deferred': label+=' · стройка не исполнялась'
                y=self.wrapped(label,content.x,y,content.width,self.small,ACCENT)+12
            y=self.wrapped(f"Свободных мест: {construction['legal_site_count']} · успешных строек за5 дней: {construction['successful_builds_last_5_days']}",content.x,y,content.width,self.small,MUTED)+14
            for project in construction['projects']:
                cost=project['cost']; names=RESOURCE_NAMES
                gains=', '.join(f"{names.get(key,key)} {value:+g}" for key,value in project['daily_gain'].items() if value)
                y=self.wrapped(f"{project['name']} {project['level']} · {project['cell']}",content.x,y,content.width,self.small,ACCENT)+4
                y=self.wrapped('Цена: '+', '.join(f'{RESOURCE_NAMES.get(k,k)} {v:g}' for k,v in cost.items())+'\n'+('Резерв сохранится' if project['affordable_with_reserve'] else 'Нужны запасы сверх резерва')+'\n'+(gains or project['effect']),content.x,y,content.width,self.small)+16
        elif self.tab==8:
            pending=self.world.pending_decisions.get(s.id,{})
            assessment=(pending.get('strategic_assessment') if not pending.get('strategic_review_required') else None) or s.strategic_assessment
            from planet.view_safety import readable_assessment
            if assessment and not readable_assessment(assessment): assessment=None
            y=self.wrapped('ЧАСТНЫЙ СТРАТЕГИЧЕСКИЙ РАЗБОР',content.x,y,content.width,self.small,ACCENT)+10
            response=pending.get('military_response') or next((r['decision'].get('military_response') for r in reversed(self.world.decisions) if r['state']==s.id),None)
            if isinstance(response,dict):
                choices=dict(mobilize='Найм войск',maneuver='Боевые приказы',fortify='Укрепление',hold='Удержание',defer='Отсрочка')
                y=self.wrapped('ВОЕННЫЙ ОТВЕТ · '+choices.get(str(response.get('choice')),str(response.get('choice'))),content.x,y,content.width,self.small,ACCENT)+6
                y=self.wrapped(str(response.get('reason',''))+f"\nПересмотр: день {response.get('revisit_day')}",content.x,y,content.width,self.small)+14
            if pending.get('strategic_review_required'): y=self.wrapped('Основное решение сохранено. Разбор уточняется: '+str(pending['strategic_review_required']),content.x,y,content.width,self.small,(239,174,91))+14
            if not assessment: y=self.wrapped('Появится в первом новом решении версии 5.2. Ранее готовые решения сохраняются.',content.x,y,content.width,color=MUTED)
            else:
                modes=dict(development='Развитие',war='Война',economic_pressure='Экономическое давление',vassalage='Вассалитет',coalition='Коалиция',defence='Оборона',containment='Сдерживание',none='Нет соперников')
                y=self.wrapped(assessment['objective']+f"\nГоризонт: {assessment['horizon_days']} дней · план: {modes.get(assessment['chosen'],assessment['chosen'])} (не статус войны)",content.x,y,content.width)+16
                for option in assessment['alternatives']:
                    y=self.wrapped(modes.get(option['mode'],option['mode']),content.x,y,content.width,self.small,ACCENT)+4
                    y=self.wrapped('Выгода: '+option['gain']+'\nРиск: '+option['risk']+'\nОтвет противника: '+option['opponent_response'],content.x,y,content.width,self.small)+16
                plan=assessment['rival_plan']; limits=assessment['risk_limits']
                for label,key in [('РЫЧАГ','leverage'),('ПУБЛИЧНАЯ ПОЗИЦИЯ','public_position'),('ЧАСТНОЕ НАМЕРЕНИЕ','private_intent'),('УСЛОВИЕ ЭСКАЛАЦИИ','trigger'),('ЗАПАСНОЙ ВАРИАНТ','fallback')]:
                    y=self.wrapped(label,content.x,y,content.width,self.small,ACCENT)+4; y=self.wrapped(plan[key],content.x,y,content.width,self.small)+14
                y=self.wrapped(f"Предел риска: еда на {limits['min_food_days']} дней, деньги {limits['money_reserve']:g}\n{limits['stop_condition']}\nКритерий успеха: {assessment['success_metric']}",content.x,y,content.width,self.small,(239,174,91))
        else:
            y=self.wrapped('ЮНИТЫ · нажмите для приближения',content.x,y,content.width,self.small,ACCENT)+12
            units=[u for u in self.world.units if u['owner']==s.id]
            types=UNIT_LABELS
            for unit in units:
                rect=pg.Rect(content.x,int(y),content.width,110)
                self.box(rect,(34,46,56),7)
                self.text(f"#{unit['id']}  {types[unit['type']]}",content.x+10,y+6,s.color,self.small)
                supply=f" · снабжение {unit.get('supply_ratio',1)*100:.0f}%" if unit['type'] in MODERN_UNITS else ''
                self.text(f"Сила {unit['strength']:g} / эффективная {self.world.effective_strength(unit):g}"+supply,content.x+10,y+27,TEXT,self.small)
                self.text(f"На корабле #{unit['embarked_on']}" if unit.get('embarked_on') else f"Клетка {unit['cell']} · осталось {self.world.remaining_moves(unit)} шагов",content.x+10,y+46,MUTED,self.small)
                order=unit.get('order') or {}
                order_label={'explore':'Разведка границ','move':f'Маршрут к {order.get("target")}','hold':'Удерживать позицию'}.get(order.get('kind'),'Без приказа')
                if unit['type']=='ship':order_label+=f" · груз {sum(p.get('embarked_on')==unit['id'] for p in self.world.units)}/{self.world.ship_capacity(unit)}"
                self.text(order_label+(' · '+unit['blocked_reason'][:35] if unit.get('blocked_reason') else ''),content.x+10,y+65,ACCENT,self.small)
                hit=rect.clip(content)
                if hit.height>0: self.buttons.append((hit,f"focus:{unit['id']}"))
                buff=unit.get('tower_buff') or {}
                if buff and buff.get('expires_day',-1)>=self.world.day: self.text(f"Башня +{buff['percent']}% · дни {buff['starts_day']}–{buff['expires_day']}",content.x+10,y+82,(223,185,112),self.small)
                y+=121
            if not units: y=self.wrapped('Юнитов пока нет.',content.x,y,content.width,color=MUTED)
        self.max_scroll=max(0,y+self.scroll-content.bottom+10)
        self.screen.set_clip(None)
        cy=legend_y+60
        self.box((28,cy,map_width,height-cy-22))
        self.button('Хроника',(40,cy+7,120,28),'bottom:0',self.chronicle_tab==0)
        self.button('Обучение',(168,cy+7,132,28),'bottom:1',self.chronicle_tab==1)
        self.learning_rect=pg.Rect(40,cy+35,map_width-20,height-cy-61)
        recent=[e for e in self.world.events if e['kind']!='action'][-3:]
        y=cy+39
        self.screen.set_clip(pg.Rect(40,cy+35,map_width-20,height-cy-61))
        if self.chronicle_tab==0:
            for e in reversed(recent):y=self.wrapped(f"{e['day']:04d}  {e['text']}",45,y,map_width-34,self.small)+3
        else:
            record=self.world.learning_record(s.id);y-=self.learning_scroll
            y=self.wrapped(f"{s.name} · награда {record['score']:+.3f} · обратная связь, без изменения весов",45,y,map_width-34,self.small,ACCENT)+5
            y=self.wrapped(record['notes'] or 'Стратегия появится в следующем новом решении модели. Колесо здесь прокручивает заметки.',45,y,map_width-34,self.small)+8
            active_trial=record.get('active_experiment')
            if active_trial:y=self.wrapped('Текущая гипотеза: '+active_trial['hypothesis']+f" · {active_trial['metric']} {active_trial['direction']} {active_trial['target_change']} · срок {active_trial['due_day']}",45,y,map_width-34,self.small,ACCENT)+5
            for episode in reversed(record['episodes'][-3:]):y=self.wrapped(f"Опыт дня {episode['day']}: очки {episode['score_delta']:+.3f}, принятых приказов {episode['accepted']}, ошибок {episode.get('rejected_count',len(episode['errors']))}",45,y,map_width-34,self.small)+3
            for trial in reversed(record['experiments'][-3:]):
                y=self.wrapped('Эксперимент: '+trial['hypothesis']+' · '+('цель достигнута' if trial.get('achieved') else 'цель не достигнута' if trial['status']=='evaluated' else 'пересмотрен'),45,y,map_width-34,self.small)+4
            labels=dict(territory_neutral='Новые клетки',territory_captured='Захват',territory_lost='Потеря клеток',daily_leader='Лидер ресурса за день',daily_deficit='Дефицит ресурса за день',monthly_leader='Лидер ресурса (старая месячная награда)',monthly_deficit='Дефицит (старая месячная награда)',became_vassal='Подчинение',new_vassal='Новый вассал',vassal_lost='Потеря вассала',research='Исследование',rejected_orders='Отказы приказов')
            for event in reversed(record['events'][-40:]):y=self.wrapped(f"День {event['day']} · {event['delta']:+.3f} · {labels.get(event['reason'],event['reason'])} "+str(event.get('resource','')),45,y,map_width-34,self.small)+3
            self.learning_max_scroll=max(0,y+self.learning_scroll-self.learning_rect.bottom+10)
        self.screen.set_clip(None)
        if self.tile:
            c=self.world.cell(self.tile)
            unit=self.world.unit_at(self.tile)
            owner=next((s.name for s in self.world.states if s.id==c.owner),'Нейтральная')
            info=f'{self.tile} · {LABELS[c.terrain]} {c.level} · {owner} · {BUILDING_LABELS.get(c.building,"нет здания")} · жителей {c.population}'
            if self.world.wall_hitpoints(c)>0: info+=f' · прочность {self.world.wall_hitpoints(c):g}'
            if c.radiation: info+=f' · РАДИАЦИЯ {c.radiation}'
            if c.building in MODERN_BUILDINGS: info+=f' · целостность {c.integrity:g}% · мест {self.world.population_capacity(self.world.state(c.owner),c)}'
            if c.building=='tower': info+=f' · обучение +{25*c.building_level}% на3 дня'
            if unit: info+=f" · #{unit['id']} {UNIT_LABELS[unit['type']]} · сила {self.world.effective_strength(unit):g}"
            self.screen.set_clip(self.map_rect)
            self.box((40,self.map_rect.bottom-35,map_width-24,27),(17,25,32),4)
            self.text(info,45,self.map_rect.bottom-30,TEXT,self.small)
            self.screen.set_clip(None)
        if self.error:
            overlay=pg.Rect(38,190,map_width-20,150); self.box(overlay,(63,35,38))
            self.text('СИМУЛЯЦИЯ ПРИОСТАНОВЛЕНА',54,204,(255,189,163),self.small)
            self.screen.set_clip(overlay)
            self.wrapped(self.error,54,232,map_width-55,self.small)
            self.screen.set_clip(None)
        previous=self.screen.get_clip();self.screen.set_clip(None)
        self.box((28,height-29,max(100,width-56),23),(16,24,31),4)
        self.text(self.status[:max(25,(width-70)//7)],36,height-27,(239,174,91) if self.error else MUTED,self.small)
        self.screen.set_clip(previous)
        for rect,key in self.resource_rects:
            if rect.collidepoint(pg.mouse.get_pos()):
                item=forecast['resources'][key]; overlay=pg.Rect(max(28,sx-380),sy+167,364,154)
                self.box(overlay,(33,43,49))
                text=f"{resource_labels.get(key,key)} · оценка следующего дня\nДобыча: +{item['production']:g}\nСодержание: −{item['upkeep']:g}\nПлановые расходы: −{item['planned_cost']:g}\nБаланс: {item['net']:+g}"
                if item['runway_days'] is not None: text+=f" · запас ≈ {item['runway_days']} дн."
                self.wrapped(text,overlay.x+14,overlay.y+10,overlay.width-28,self.small); break
        pg.display.flip()

    def action(self,action):
        if action in ('run','day') and not (action=='run' and self.running):
            if not self.config.get('model') and not all(self.config.get('state_models',{}).get(s.id) for s in self.world.states if not s.eliminated):
                self.running=False;self.status='Выберите модель в «LM Studio · F2», затем запустите наблюдение.';return
        if action.startswith('bottom:'):
            self.chronicle_tab=int(action.split(':')[1]);self.learning_scroll=0;return
        if action=='run':
            self.running=not self.running; self.target_day=None
            if self.running: self.error=''
        elif action=='day':
            self.target_day=self.world.day if self.world.in_day else self.world.day+1
            self.running=True; self.error=''
        elif action=='settings':
            if self.runner.busy: self.status='Пауза вступит в силу после ответа модели.'; self.running=False; return
            self.running=False; old_size=self.screen.get_size(); changed=settings(self.config)
            self.screen=self.pg.display.set_mode(old_size,self.pg.RESIZABLE)
            self.pg.display.set_caption('Живая планета · v7.0.1 · лаборатория миров')
            if changed:
                enabled=self.config.get('external_console',True)
                if not enabled: self.runner.console.close()
                self.runner.console.enabled=enabled
            self.status='Настройки сохранены. Можно продолжить.' if changed else 'Настройки закрыты.'
        elif action=='help':
            from planet.configuration import open_help
            open_help(ROOT);self.status='Открыта полная справка: подключение, механики и решение проблем.'
        elif action=='export':
            path=self.runner.store.path.parent/'chronicle.txt'
            path.parent.mkdir(exist_ok=True)
            path.write_text('\n'.join(f"День {e['day']} · {e['text']}" for e in self.world.events),encoding='utf-8')
            self.status='Хроника сохранена в папку текущего мира'
        elif action=='worlds':
            self.running=False; self.switch_requested=True
            if self.runner.busy: self.status='Сохраняем текущий ответ перед выбором мира…'
        elif action=='industry': self.open_industry()
        elif action=='relations': self.open_relations()
        elif action.startswith('state:'): self.selected=int(action.split(':')[1]); self.scroll=0;self.learning_scroll=0
        elif action.startswith('tab:'): self.tab=int(action.split(':')[1]); self.scroll=0
        elif action.startswith('focus:'):
            unit=next((u for u in self.world.units if u['id']==int(action.split(':')[1])),None)
            if unit:
                self.selected=next(i for i,s in enumerate(self.world.states) if s.id==unit['owner'])
                self.focus_unit_id=unit['id']; self.tab=4; self.tile=list(unit['cell']); self.zoom=12
                self.scroll=next(i for i,u in enumerate(u for u in self.world.units if u['owner']==unit['owner']) if u['id']==unit['id'])*121
                factor=min((self.map_rect.width-32)/self.world.size,(self.map_rect.height-32)/self.world.size)*self.zoom
                self.pan=[(self.world.size/2-unit['cell'][0]-.5)*factor,(self.world.size/2-unit['cell'][1]-.5)*factor]

    def recover_ui(self,message):
        """Minimal independent screen: do not call the failed map/text renderer."""
        pg=self.pg;self.screen.set_clip(None)
        font=pg.font.Font(None,25);clock=pg.time.Clock()
        while True:
            for event in pg.event.get():
                if event.type==pg.QUIT:return False
                if event.type==pg.KEYDOWN:
                    if event.key==pg.K_ESCAPE:return False
                    if event.key in (pg.K_RETURN,pg.K_F5):return True
            self.screen.fill((18,24,30))
            lines=['Ошибка интерфейса. Симуляция приостановлена.',
                   'Последнее сохранение и готовые решения остаются в папке мира.',
                   'Enter / F5 — восстановить окно. Затем продолжите вручную.',
                   'Esc — выйти. Подробности: logs/crash.log',str(message)[:160]]
            for i,line in enumerate(lines):self.screen.blit(font.render(line.replace('\x00','?'),True,(235,225,210)),(25,35+i*36))
            pg.display.flip();clock.tick(30)

    def close(self):
        self.runner.console.close()
        for child in list(self.relation_windows.values())+list(self.industry_windows.values()):
            if child.poll() is None:child.terminate()
        self.pg.quit()

    def loop(self,screenshot=None):
        while True:
            try:return self._loop(screenshot)
            except Exception as exc:
                from planet.diagnostics import record
                record(ROOT/'logs',exc,'interface')
                self.running=False;self.target_day=None
                self.screen.set_clip(None)
                self.atlas.scaled.clear();self.atlas.scaled_bytes=0
                self.text_layout.clear()
                message=f'{type(exc).__name__}: {exc}'
                if screenshot: raise
            if not self.recover_ui(message):self.close();return False
            # Reset only presentation. Do not replay orders or replace worker state.
            self.tab=0;self.chronicle_tab=0;self.scroll=0;self.learning_scroll=0
            self.zoom=1;self.pan=[0.,0.];self.tile=None;self.drag=None
            self.map_dirty=True;self.forecasts={};self.view_positions={}
            self.strategy_cache={};self.construction_cache={};self.preview_key=None
            self.buttons=[];self.error='Интерфейс восстановлен. Продолжите вручную.'

    def _loop(self,screenshot=None):
        pg=self.pg; clock=pg.time.Clock(); opened=True
        self.draw()
        while opened:
            while not self.runner.messages.empty():
                kind,value=self.runner.messages.get()
                if kind=='world':
                    self.world=World.restore(value); self.map_dirty=True; self.forecasts={}; self.view_positions={}; self.strategy_cache={}; self.construction_cache={}; self.preview_key=None; self.activity=None
                    self.status=f'Общий день {self.world.day} · '+(f'решений {len(self.world.pending_decisions)}/{len(self.world.states)}' if self.world.phase=='planning' else 'решения собраны' if self.world.phase=='resolution' else 'действия применены' if self.world.in_day else 'завершён')
                    if self.target_day and self.world.day>=self.target_day and not self.world.in_day: self.running=False; self.target_day=None
                elif kind=='status': self.status=value
                elif kind=='activity': self.activity=value
                elif kind=='retry': self.status=value; self.retry_after=time.monotonic()+5; self.error=''
                elif kind=='error': self.error=value; self.status='Ошибка LM Studio / решения'; self.running=False
                elif kind=='done': self.runner.busy=False
            for event in pg.event.get():
                if event.type==pg.QUIT: opened=False
                elif event.type==pg.VIDEORESIZE:
                    self.screen=pg.display.set_mode((max(1120,event.w),max(760,event.h)),pg.RESIZABLE)
                elif event.type==pg.KEYDOWN:
                    if event.key==pg.K_F1:self.action('help')
                    elif event.key==pg.K_SPACE: self.action('run')
                    elif event.key==pg.K_n: self.action('day')
                    elif event.key==pg.K_F2: self.action('settings')
                    elif event.key==pg.K_r: self.zoom=1; self.pan=[0.,0.]
                elif event.type==pg.MOUSEWHEEL:
                    if self.chronicle_tab==1 and getattr(self,'learning_rect',self.map_rect).collidepoint(pg.mouse.get_pos()):self.learning_scroll=max(0,min(self.learning_max_scroll,self.learning_scroll-event.y*42))
                    elif self.map_rect.collidepoint(pg.mouse.get_pos()): self.zoom=max(1,min(64,self.zoom*(1.2**event.y)))
                    else: self.scroll=max(0,min(getattr(self,'max_scroll',0),self.scroll-event.y*42))
                elif event.type==pg.MOUSEBUTTONDOWN and event.button==1:
                    for rect,action in self.buttons:
                        if rect.collidepoint(event.pos): self.action(action); break
                    else:
                        if self.map_rect.collidepoint(event.pos):
                            unit=next((u for rect,u in reversed(self.unit_markers) if rect.collidepoint(event.pos)),None)
                            if unit:
                                self.action(f"focus:{unit['id']}"); continue
                            self.drag=event.pos
                            x=int((event.pos[0]-self.origin[0])/self.scale); y=int((event.pos[1]-self.origin[1])/self.scale)
                            self.tile=[x,y] if 0<=x<self.world.size and 0<=y<self.world.size else None
                elif event.type==pg.MOUSEBUTTONUP: self.drag=None
                elif event.type==pg.MOUSEMOTION and self.drag:
                    self.pan[0]+=event.pos[0]-self.drag[0]; self.pan[1]+=event.pos[1]-self.drag[1]; self.drag=event.pos
            if self.switch_requested and not self.runner.busy: break
            if self.running and not self.runner.busy and time.monotonic()>=self.retry_after: self.runner.tick()
            self.draw()
            if screenshot: pg.image.save(self.screen,screenshot); break
            clock.tick(30)
        self.close()
        return self.switch_requested


def main():
    parser=argparse.ArgumentParser(description='Живая планета · LM Studio')
    parser.add_argument('--screenshot',help='Отрисовать один кадр и выйти')
    parser.add_argument('--check',action='store_true',help='Проверить подключение и список моделей')
    args=parser.parse_args()
    from planet.configuration import load_config
    config=load_config(ROOT)
    from planet.runtime_config import upgrade_config
    if upgrade_config(config):(ROOT/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    config.setdefault('review_relations',True)
    config.setdefault('deep_strategy',True)
    config.setdefault('structured_reviews',True)
    config.setdefault('structured_primary',True)
    config.setdefault('strict_state_isolation',True)
    config.setdefault('decision_compiler',True)
    config.setdefault('calibrate_context',True)
    config.setdefault('detect_repetition',True)
    config.setdefault('context_window',196608)
    if args.check:
        print('\n'.join(Brain(config).models())); return
    if args.screenshot:
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            App(World(),Store(Path(temp)/'preview.sqlite3'),config).loop(args.screenshot)
        return
    from planet.launcher import choose_world
    while True:
        selected=choose_world(ROOT,config)
        if selected is None: break
        world,store=selected; config['states']=len(world.states)
        try: switch=App(world,store,config).loop()
        finally: store.session_lock.close()
        if not switch: break


if __name__=='__main__':
    from planet.diagnostics import install
    install(ROOT/'logs')
    main()
