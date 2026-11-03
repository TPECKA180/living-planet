"""One directory per world, SQLite authority plus inspectable atomic exports."""
import json
import os
import re
import sqlite3
import uuid
import hashlib
import shutil
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .engine import Store, World


def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')


class WorldLock:
    """Release automatically on process exit; a stale lock file is harmless."""
    def __init__(self,folder):
        self.file=open(Path(folder)/'session.lock','a+b')
        self.file.seek(0,2)
        if not self.file.tell(): self.file.write(b'0'); self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close(); raise RuntimeError('Этот мир уже открыт в другом окне. Закройте его или выберите другой мир.') from exc

    def close(self):
        if self.file.closed: return
        self.file.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
        self.file.close()


def atomic_text(path,text,cache=None):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    key=str(path)
    if cache is not None and path.name!='world.json':
        cached=cache.get(key)
        if cached and cached[0]==text:
            try:
                stat=path.stat()
                if (stat.st_mtime_ns,stat.st_size)==cached[1:]: return
            except FileNotFoundError: pass
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(text,encoding='utf-8'); temp.replace(path)
    if cache is not None and path.name!='world.json':
        stat=path.stat(); cache[key]=(text,stat.st_mtime_ns,stat.st_size)


def write_json(path,value,cache=None):
    text=json.dumps(value,ensure_ascii=False,separators=(',',':')) if Path(path).name=='world.json' else json.dumps(value,ensure_ascii=False,indent=2)
    atomic_text(path,text,cache)


def write_lines(path,items,cache=None):
    atomic_text(path,''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in items),cache)


def backup_connection(source,folder,snapshot_text):
    digest=hashlib.sha256(snapshot_text.encode('utf-8')).hexdigest()[:12]
    folder=Path(folder)/'backups'; folder.mkdir(exist_ok=True)
    path=folder/f'before-v7.5.5-{digest}.sqlite3'
    if not path.exists():
        temporary=path.with_suffix('.sqlite3.tmp')
        with closing(sqlite3.connect(temporary)) as destination: source.backup(destination)
        temporary.replace(path)
    write_json(Path(folder).parent/'migration.json',dict(from_version=json.loads(snapshot_text).get('version',1),to_version=6,to_patch='7.5.5',
               time=now(),backup=str(path.name),day=json.loads(snapshot_text)['day'],characters_preserved=True,
               note='Новые правила применяются к следующим действиям. Ресурсы, карта, характеры и готовые решения не сбрасываются.'))
    return path


def export_world(folder,world,snapshot,settings,cache=None):
    with world.analysis_scope(): _export_world(folder,world,snapshot,settings,cache)


def _export_world(folder,world,snapshot,settings,cache=None):
    folder=Path(folder)
    manifest_path=folder/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else dict(name=folder.name,created_at=now())
    manifest.update(version=6,patch='7.5.5',map_mode=getattr(world,'map_mode','normal'),seed=world.seed,updated_at=now(),day=world.day,completed_days=world.day-int(world.in_day),phase=world.phase,cursor=world.cursor,size=world.size,states=len(world.states))
    write_json(folder/'world.json',snapshot,cache=cache)
    write_lines(folder/'chronicle.jsonl',world.events,cache=cache)
    write_lines(folder/'messages.jsonl',world.messages,cache=cache)
    write_lines(folder/'decisions.jsonl',world.decisions,cache=cache)
    write_json(folder/'trade_offers.json',world.trade_offers,cache=cache)
    write_lines(folder/'movement.jsonl',world.movement_log,cache=cache)
    write_json(folder/'day_stats.json',dict(day=world.day,stats=world.day_stats,previous=world.last_day_stats),cache=cache)
    write_json(folder/'relations.json',{s.id:s.relations for s in world.states},cache=cache)
    write_json(folder/'economy.json',{s.id:world.economic_forecast(s) for s in world.states},cache=cache)
    write_json(folder/'wars.json',world.wars,cache=cache)
    write_json(folder/'history_book.json',world.history_book,cache=cache)
    write_json(folder/'learning.json',getattr(world,'learning',{}),cache=cache)
    write_json(folder/'strategy.json',{s.id:world.strategic_context(s) for s in world.states},cache=cache)
    write_json(folder/'surrender_demands.json',world.surrender_demands,cache=cache)
    write_json(folder/'vassalage.json',dict(offers=world.vassal_offers,treaties=world.vassal_treaties),cache=cache)
    write_json(folder/'pledges.json',world.pledges,cache=cache)
    write_json(folder/'supply_pacts.json',world.supply_pacts,cache=cache)
    write_json(folder/'exchanges.json',world.exchanges,cache=cache)
    write_lines(folder/'settlements.jsonl',world.settlements,cache=cache)
    # Do not copy authentication credentials into world exports.
    write_json(folder/'settings.json',{k:v for k,v in settings.items() if k not in ('api_key',)},cache=cache)
    for state in snapshot['states']:
        dest=folder/'states'/state['id']
        write_json(dest/'state.json',state,cache=cache)
        write_lines(dest/'actions.jsonl',state['history'],cache=cache)
        write_lines(dest/'memory.jsonl',state['memory'],cache=cache)
        write_json(dest/'relations.json',state['relations'],cache=cache)
        write_json(dest/'learning.json',world.learning_record(state['id']),cache=cache)
        write_lines(dest/'experience.jsonl',world.learning_record(state['id'])['episodes'],cache=cache)
        write_lines(dest/'experiments.jsonl',world.learning_record(state['id'])['experiments'],cache=cache)
    write_json(manifest_path,manifest,cache=cache)


class WorldLibrary:
    def __init__(self,root,config=None):
        self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
        self.config=config or {}

    def entries(self):
        found=[]
        for file in self.root.glob('*/manifest.json'):
            try:
                data=json.loads(file.read_text(encoding='utf-8'))
                if (file.parent/'world.sqlite3').is_file(): found.append(dict(data,folder=str(file.parent)))
            except (OSError,ValueError): continue
        return sorted(found,key=lambda d:(int(d.get('completed_days',max(0,int(d.get('day',0))-(d.get('phase','idle')!='idle')))),int(d.get('day',0)),d.get('updated_at','')),reverse=True)

    def create(self,name,count=4,seed=42,world=None,import_source=None,map_mode='normal'):
        if not name.strip(): raise ValueError('Введите название мира')
        if type(count) is not int or not 2<=count<=6: raise ValueError('Государств должно быть от 2 до 6')
        slug=re.sub(r'[^\w-]+','_',name.strip(),flags=re.UNICODE).strip('_')[:55] or 'world'
        folder=self.root/(slug+'_'+uuid.uuid4().hex[:8]); folder.mkdir()
        manifest=dict(name=name.strip(),created_at=now(),version=6)
        if import_source: manifest['import_source']=str(Path(import_source).resolve())
        write_json(folder/'manifest.json',manifest)
        state=world or World(count=count,seed=seed,map_mode=map_mode)
        store=Store(folder/'world.sqlite3',export=True,settings=self.config); store.save(state)
        return state,store

    def load(self,folder):
        folder=Path(folder).resolve()
        if not (folder/'world.sqlite3').is_file(): raise ValueError('В папке нет world.sqlite3')
        store=Store(folder/'world.sqlite3',export=True,settings=self.config)
        world=store.load()
        if world is None: raise ValueError('Сохранение пустое')
        return world,store

    def import_legacy(self,path,name='Мир из предыдущей версии'):
        path=Path(path).resolve()
        if not path.is_file(): raise ValueError('Файл сохранения не найден')
        # Source is read-only; importing never changes the original save.
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as source, closing(sqlite3.connect(':memory:')) as captured:
            source.backup(captured)
            row=captured.execute('SELECT data FROM snapshot WHERE id=1').fetchone()
            if row is None: raise ValueError('В файле нет мира')
            old=json.loads(row[0]); world=World.restore(old)
            chosen=self.create(name,count=len(world.states),seed=world.seed,world=world,import_source=path)
            backup_connection(captured,chosen[1].path.parent,row[0])
            # Keep the rollback chain and original raw generation history.
            dest=chosen[1].path.parent
            for previous in (path.parent/'backups').glob('*.sqlite3'):
                target=dest/'backups'/previous.name
                if not target.exists(): shutil.copy2(previous,target)
            old_migration=path.parent/'migration.json'
            if old_migration.exists(): shutil.copy2(old_migration,dest/'migration_previous.json')
            stream=path.parent/'llm_stream.jsonl'
            if stream.is_file():
                with stream.open('rb') as src,(dest/'llm_stream.jsonl').open('wb') as output:
                    for line in src:
                        if line.endswith(b'\n'): output.write(line)
            return chosen

