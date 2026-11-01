import json
import secrets
from pathlib import Path

from .dialogs import ACCENT, BG, MUTED, Dialog
from .saves import WorldLibrary, WorldLock


def choose_world(app_root,config,screenshot=None):
    app_root=Path(app_root)
    dialog=Dialog('Живая планета · v7.5.1 · выбрать мир',(1120,820)); pg=dialog.pg
    path=Path(config.get('saves_directory','saves'))
    if not path.is_absolute(): path=app_root/path
    dialog.field('directory','Папка всех миров · можно вставить путь Ctrl+V',str(path.resolve()),(34,108,850,36))
    dialog.field('name','Название нового мира','Новая планета',(730,238,350,36))
    dialog.field('count','Число государств (2–6)',config.get('states',4),(730,308,350,36))
    dialog.field('seed','Зерно генерации',secrets.randbelow(2**31),(730,378,350,36))
    legacy_path=app_root/config.get('database','data/planet.sqlite3')
    dialog.field('import','Путь к старому SQLite-сохранению',str(legacy_path.resolve()),(34,642,850,36))
    entries=[]; selected=0; scroll=0;map_mode='normal'
    library=WorldLibrary(path,config)
    def refresh():
        nonlocal entries,selected,scroll
        entries=library.entries(); selected=0; scroll=0
        if legacy_path.is_file() and str(legacy_path.resolve()) not in {entry.get('import_source') for entry in entries}:
            entries.append(dict(name='Старый мир из первой версии',day='?',states='?',legacy=str(legacy_path)))
    refresh()
    dialog.notice='Выберите сохранение или создайте новый мир. Старые миры сохраняются независимо.'
    clock=pg.time.Clock()
    def finish(chosen):
        world,store=chosen; lock=WorldLock(store.path.parent)
        try:
            config['saves_directory']=str(library.root); config['states']=len(world.states)
            (app_root/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception: lock.close(); raise
        store.session_lock=lock; pg.quit(); return chosen
    while True:
        for action in dialog.events():
            if action=='cancel': pg.quit(); return None
            try:
                if action=='directory':
                    library=WorldLibrary(dialog.fields['directory']['value'].strip(),config); refresh()
                    dialog.notice=f'Выбрана папка: {library.root}'
                elif action.startswith('select:'): selected=int(action.split(':')[1])
                elif action=='up': scroll=max(0,scroll-1)
                elif action=='down': scroll=min(max(0,len(entries)-6),scroll+1)
                elif action=='load':
                    if not entries: raise ValueError('Нет сохранений. Создайте новый мир.')
                    entry=entries[selected]
                    chosen=library.import_legacy(entry['legacy']) if 'legacy' in entry else library.load(entry['folder'])
                    return finish(chosen)
                elif action=='new':
                    chosen=library.create(dialog.fields['name']['value'],int(dialog.fields['count']['value']),int(dialog.fields['seed']['value']),map_mode=map_mode)
                    return finish(chosen)
                elif action.startswith('mode:'):
                    map_mode=action.split(':',1)[1]
                    dialog.notice='Архипелаг: шесть крупных островов, отдельные стартовые острова; для войны через море нужны корабли.' if map_mode=='archipelago' else 'Обычный мир: непрерывные области суши и моря, берега зависят от seed.'
                elif action=='import':
                    library.import_legacy(dialog.fields['import']['value'].strip()); refresh()
                    dialog.notice='Сохранение импортировано копией. Выберите его и нажмите «Загрузить».'
                elif action=='settings':
                    from .dialogs import edit_settings
                    edit_settings(app_root,config)
                    dialog.screen=pg.display.set_mode((1120,820))
                    dialog.notice='Подключение сохранено. Создайте мир или продолжите свою историю.'
                elif action=='help':
                    from .configuration import open_help
                    open_help(app_root)
            except Exception as exc: dialog.notice=str(exc)
        dialog.screen.fill(BG); dialog.buttons=[]
        dialog.label('ЖИВАЯ ПЛАНЕТА',34,23,font=dialog.title_font)
        dialog.label('Выберите историю, которую хотите продолжить',34,61,MUTED,dialog.small)
        dialog.button('LM Studio',(730,25,150,35),'settings')
        dialog.button('Справка',(900,25,180,35),'help')
        dialog.draw_fields()
        dialog.button('Применить папку',(904,108,176,36),'directory')
        dialog.panel((34,180,654,366))
        dialog.label('СОХРАНЁННЫЕ МИРЫ',50,196,ACCENT,dialog.small)
        for row,entry in enumerate(entries[scroll:scroll+6]):
            index=scroll+row; y=228+row*49
            day=entry.get('day',0)
            completed=entry.get('completed_days',day-int(entry.get('phase','idle')!='idle') if isinstance(day,int) else '?')
            stage=f"решения {entry.get('cursor',0)}/{entry.get('states',4)}" if entry.get('phase')=='planning' else 'готов'
            label=f"{entry['name'][:23]} · {completed} дней · ход {day}, {stage}"
            dialog.button(label,(50,y,620,41),f'select:{index}',index==selected)
        if not entries: dialog.label('Миров пока нет. Создайте первый справа.',50,254,MUTED)
        dialog.label('НОВЫЙ МИР',730,190,ACCENT,dialog.small)
        dialog.button('Обычный',(730,430,165,36),'mode:normal',map_mode=='normal')
        dialog.button('Архипелаг',(909,430,171,36),'mode:archipelago',map_mode=='archipelago')
        dialog.button('Создать новый мир',(730,480,350,42),'new',True)
        dialog.button('Загрузить выбранный',(34,560,230,38),'load',True)
        dialog.button('Выше',(470,560,100,38),'up')
        dialog.button('Ниже',(580,560,108,38),'down')
        dialog.button('Импортировать',(904,642,176,36),'import')
        dialog.notice_lines(707)
        dialog.label('В каждой папке: мир, все решения, действия, переписка, сделки и история характера.',34,777,MUTED,dialog.small)
        pg.display.flip()
        if screenshot: pg.image.save(dialog.screen,screenshot); pg.quit(); return None
        clock.tick(30)
