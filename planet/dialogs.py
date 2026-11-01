"""Pygame-only menus: no dependency on Windows' Tcl/Tk installation."""
import copy
import json
import queue
import threading
from pathlib import Path

BG=(13,20,27); PANEL=(22,31,40); TEXT=(223,233,237); MUTED=(137,158,169); ACCENT=(92,207,178)


class Dialog:
    def __init__(self,title,size=(1120,820)):
        import pygame as pg
        self.pg=pg; pg.init(); pg.display.set_caption(title)
        self.screen=pg.display.set_mode(size)
        self.font=pg.font.SysFont('segoeui',17); self.small=pg.font.SysFont('segoeui',14)
        self.title_font=pg.font.SysFont('segoeui',28,bold=True)
        self.fields={}; self.active=None; self.buttons=[]; self.notice=''; self.select_all=False
        self.cursor=0

    def label(self,text,x,y,color=TEXT,font=None):
        self.screen.blit((font or self.font).render(str(text),True,color),(x,y))

    def panel(self,rect,color=PANEL): self.pg.draw.rect(self.screen,color,rect,border_radius=10)

    def field(self,key,label,value,rect,secret=False):
        self.fields[key]=dict(label=label,value=str(value),rect=self.pg.Rect(rect),secret=secret)

    def button(self,label,rect,action,accent=False):
        self.panel(rect,ACCENT if accent else (36,49,60)); self.label(label,rect[0]+12,rect[1]+9,BG if accent else TEXT,self.small)
        self.buttons.append((self.pg.Rect(rect),action))

    def draw_fields(self):
        pg=self.pg
        for key,f in self.fields.items():
            r=f['rect']; self.label(f['label'],r.x,r.y-23,MUTED,self.small)
            self.panel(r,(31,47,55) if key==self.active else (27,38,48))
            clip=r.inflate(-14,-6); self.screen.set_clip(clip)
            value='•'*len(f['value']) if f.get('secret') else f['value']; caret=self.cursor if key==self.active else len(value)
            offset=max(0,self.font.size(value[:caret])[0]-clip.width+8)
            if key==self.active and self.select_all:
                pg.draw.rect(self.screen,(51,101,102),(r.x+8-offset,r.y+6,self.font.size(value)[0],24))
            self.label(value,r.x+8-offset,r.y+7)
            if key==self.active and (pg.time.get_ticks()//500)%2==0:
                x=r.x+8+self.font.size(value[:self.cursor])[0]-offset
                pg.draw.line(self.screen,ACCENT,(x,r.y+7),(x,r.bottom-7),1)
            self.screen.set_clip(None)

    def focus(self,key):
        self.active=key; self.cursor=len(self.fields[key]['value']); self.select_all=False

    def insert(self,text):
        if self.active is None: return
        f=self.fields[self.active]
        if self.select_all: f['value']=''; self.cursor=0; self.select_all=False
        text=text.replace('\n',' ').replace('\r','')
        f['value']=(f['value'][:self.cursor]+text+f['value'][self.cursor:])[:2048]
        self.cursor=min(len(f['value']),self.cursor+len(text))

    def clipboard(self):
        if __import__('os').name=='nt':
            import ctypes
            user=ctypes.windll.user32; kernel=ctypes.windll.kernel32
            user.GetClipboardData.restype=ctypes.c_void_p
            kernel.GlobalLock.argtypes=[ctypes.c_void_p]; kernel.GlobalLock.restype=ctypes.c_void_p
            kernel.GlobalUnlock.argtypes=[ctypes.c_void_p]
            if user.OpenClipboard(None):
                try:
                    handle=user.GetClipboardData(13)
                    if handle:
                        pointer=kernel.GlobalLock(handle)
                        if pointer:
                            try: return ctypes.wstring_at(pointer)
                            finally: kernel.GlobalUnlock(handle)
                finally: user.CloseClipboard()
        return ''

    def events(self):
        pg=self.pg; actions=[]
        for event in pg.event.get():
            if event.type==pg.QUIT: actions.append('cancel')
            elif event.type==pg.MOUSEBUTTONDOWN and event.button==1:
                hit=next((key for key,f in self.fields.items() if f['rect'].collidepoint(event.pos)),None)
                if hit is not None: self.focus(hit)
                else:
                    action=next((a for rect,a in self.buttons if rect.collidepoint(event.pos)),None)
                    if action: actions.append(action)
            elif event.type==pg.TEXTINPUT: self.insert(event.text)
            elif event.type==pg.KEYDOWN:
                if event.key==pg.K_ESCAPE: actions.append('cancel'); continue
                if event.key==pg.K_TAB:
                    keys=list(self.fields)
                    if keys: self.focus(keys[(keys.index(self.active)+1)%len(keys)] if self.active in keys else keys[0])
                    continue
                if self.active is None: continue
                f=self.fields[self.active]; control=event.mod & pg.KMOD_CTRL
                if control and event.key==pg.K_a: self.select_all=True
                elif control and event.key==pg.K_v: self.insert(self.clipboard())
                elif event.key in (pg.K_BACKSPACE,pg.K_DELETE):
                    if self.select_all: f['value']=''; self.cursor=0; self.select_all=False
                    elif event.key==pg.K_BACKSPACE and self.cursor:
                        f['value']=f['value'][:self.cursor-1]+f['value'][self.cursor:]; self.cursor-=1
                    elif event.key==pg.K_DELETE: f['value']=f['value'][:self.cursor]+f['value'][self.cursor+1:]
                elif event.key==pg.K_LEFT: self.cursor=max(0,self.cursor-1); self.select_all=False
                elif event.key==pg.K_RIGHT: self.cursor=min(len(f['value']),self.cursor+1); self.select_all=False
                elif event.key==pg.K_HOME: self.cursor=0; self.select_all=False
                elif event.key==pg.K_END: self.cursor=len(f['value']); self.select_all=False
        return actions

    def notice_lines(self,y=740):
        words=self.notice.split(); line=''
        for word in words:
            if self.small.size(line+' '+word)[0]>self.screen.get_width()-80 and line:
                self.label(line,34,y,(239,174,91),self.small); y+=20; line=''
            line=(line+' '+word).strip()
        self.label(line,34,y,(239,174,91),self.small)


def edit_settings(app_root,config,screenshot=None):
    from .brain import Brain
    dialog=Dialog('Живая планета · модели и контекст',(1120,880)); pg=dialog.pg
    fields=[('host','Адрес сервера /v1',config.get('host','http://localhost:1234/v1')),
            ('model','Общая модель',config.get('model','')),
            ('manager_model','Модель менеджера (пусто = общая)',config.get('manager_model',''))]
    fields += [(f'state_{i+1}',f'Государство {i+1} · модель (пусто = общая)',config.get('state_models',{}).get(f'state_{i+1}','')) for i in range(config.get('states',4))]
    for i,(key,label,value) in enumerate(fields): dialog.field(key,label,value,(34,103+i*61,620,35))
    dialog.field('api_key','API-ключ · только если сервер требует авторизацию',config.get('api_key',''),(34,103+len(fields)*61,620,35),secret=True)
    number_fields=[('context_window','Окно, токены',262144),('max_tokens','Ответ, токены',196608),
                   ('input_tokens','Вход: данные, токены',56000),('context_map_cells','Клеток в промте',4096)]
    for i,(key,label,default) in enumerate(number_fields):
        dialog.field(key,label,config.get(key,default),(698+(i%2)*190,438+(i//2)*68,172,35))
    strict=config.get('strict_state_isolation',True)
    managed=config.get('manage_model_context',True); console=config.get('external_console',True)
    models=[]; result_queue=queue.Queue(); fetching=False
    dialog.notice='Клик по полю модели, затем по модели из списка. Ctrl+A / Ctrl+V поддерживаются.'
    clock=pg.time.Clock()
    def fetch():
        try: result_queue.put(('models',Brain(dict(config,host=dialog.fields['host']['value'].strip(),api_key=dialog.fields['api_key']['value'].strip(),timeout=10)).models()))
        except Exception as exc: result_queue.put(('error',str(exc)))
    while True:
        for action in dialog.events():
            if action=='cancel': return False
            if action=='fetch' and not fetching:
                fetching=True; dialog.notice='Запрашиваем модели…'; threading.Thread(target=fetch,daemon=True).start()
            elif action.startswith('model:'):
                key=dialog.active if dialog.active in ('model','manager_model') or (dialog.active or '').startswith('state_') else 'model'
                dialog.fields[key]['value']=models[int(action.split(':')[1])]; dialog.focus(key)
            elif action=='manage': managed=not managed
            elif action=='strict': strict=not strict
            elif action=='console': console=not console
            elif action=='save':
                try:
                    value={key:dialog.fields[key]['value'].strip() for key,_,_ in fields}
                    if not value['host'].startswith(('http://','https://')) or not value['model']: raise ValueError('Укажите HTTP-адрес и модель')
                    nums={key:int(dialog.fields[key]['value']) for key,_,_ in number_fields}
                    if not 16384<=nums['context_window']<=1048576: raise ValueError('Окно: от 16384 до 1048576 токенов')
                    if not 1024<=nums['max_tokens']<nums['context_window']: raise ValueError('Ответ: от1024 до размера общего окна минус1; реальный резерв учитывает вход и сервер')
                    if not 50<=nums['context_map_cells']<=20000: raise ValueError('Карта: 50–20000 клеток')
                    if not 1024<=nums['input_tokens']<=1048576: raise ValueError('Входные данные: от1024 до1048576 токенов; фактический предел зависит от общего окна')
                    updated=copy.deepcopy(config); updated.update(nums)
                    updated['api_key']=dialog.fields['api_key']['value'].strip()
                    updated.update(host=value['host'].rstrip('/'),model=value['model'],manager_model=value['manager_model'],manage_model_context=managed or strict,external_console=console,strict_state_isolation=strict)
                    updated['state_models']={key:v for key,v in value.items() if key.startswith('state_') and v}
                    (Path(app_root)/'config.json').write_text(json.dumps(updated,ensure_ascii=False,indent=2),encoding='utf-8')
                    config.clear(); config.update(updated); return True
                except Exception as exc: dialog.notice=str(exc)
        while not result_queue.empty():
            kind,payload=result_queue.get(); fetching=False
            if kind=='models': models=payload; dialog.notice=f'Подключение установлено. Моделей: {len(models)}'
            else: dialog.notice=payload
        dialog.screen.fill(BG); dialog.buttons=[]
        dialog.label('МОДЕЛИ И КОНТЕКСТ',34,22,font=dialog.title_font)
        dialog.label('Один общий день · последовательные запросы · индивидуальная память',34,59,MUTED,dialog.small)
        dialog.draw_fields()
        dialog.panel((682,78,408,310))
        dialog.label('МОДЕЛИ LM STUDIO',698,94,ACCENT,dialog.small)
        dialog.button('Обновить список',(698,122,180,35),'fetch')
        for i,model in enumerate(models[:7]):
            dialog.button(model,(698,168+i*29,373,27),f'model:{i}')
        dialog.button(('ВКЛ' if managed else 'ВЫКЛ')+' · окно на сервере',(698,582,370,38),'manage',managed)
        dialog.button(('ВКЛ' if console else 'ВЫКЛ')+' · отдельная консоль',(698,625,370,38),'console',console)
        dialog.button(('ВКЛ' if strict else 'ВЫКЛ')+' · строгая изоляция стран',(698,668,370,38),'strict',strict)
        dialog.label('Общее окно: вход + правила + ответ',698,716,MUTED,dialog.small)
        dialog.label('В консоли показан реальный резерв ответа.',698,738,MUTED,dialog.small)
        dialog.notice_lines(760)
        dialog.button('Назад',(34,826,125,36),'cancel')
        dialog.button('Сохранить',(900,826,190,36),'save',True)
        pg.display.flip()
        if screenshot: pg.image.save(dialog.screen,screenshot); return False
        clock.tick(30)

