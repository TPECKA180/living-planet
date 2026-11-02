"""Persistent traceback without serializing model prompts or local variables."""
from datetime import datetime
from pathlib import Path
import faulthandler
import re
import sys
import threading
import traceback

_native_stream=None

def record(folder,exc,stage='application'):
    path=Path(folder)/'crash.log'
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        text=''.join(traceback.format_exception(type(exc),exc,exc.__traceback__))
        text=re.sub(r'(?i)Bearer\s+\S+','Bearer [hidden]',text)
        text=re.sub(r'sk-[A-Za-z0-9_-]+','[hidden key]',text)
        if path.exists() and path.stat().st_size>2*1024*1024:
            path.replace(path.with_suffix('.previous.log'))
        with path.open('a',encoding='utf-8') as stream:
            stream.write(f'\n{datetime.now().isoformat(timespec="seconds")} · {stage}\n{text}')
    except OSError:
        pass
    return path

def install(folder):
    global _native_stream
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    _native_stream=(folder/'native-crash.log').open('a',encoding='utf-8')
    faulthandler.enable(file=_native_stream,all_threads=True)
    previous=sys.excepthook
    def hook(kind,value,tb):
        path=record(folder,value)
        print(f'Журнал ошибки: {path}',file=sys.stderr)
        previous(kind,value,tb)
    sys.excepthook=hook
    previous_thread=threading.excepthook
    def thread_hook(args):
        record(folder,args.exc_value,'thread '+args.thread.name)
        previous_thread(args)
    threading.excepthook=thread_hook
