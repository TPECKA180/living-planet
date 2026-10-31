"""Append-only generation events and a separate, explicitly requested console."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


class ConsoleFeed:
    def __init__(self,folder,enabled=True):
        self.path=Path(folder)/'llm_stream.jsonl'; self.enabled=enabled
        self.process=None; self.lock=threading.Lock(); self.stream=None; self.last_flush=0

    def open(self):
        if not self.enabled or os.name!='nt': return
        if self.process is not None and self.process.poll() is None: return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        offset=self.path.stat().st_size if self.path.exists() else 0
        executable=Path(sys.executable)
        if executable.name.lower()=='pythonw.exe': executable=executable.with_name('python.exe')
        self.process=subprocess.Popen([str(executable),'-u',str(Path(__file__).with_name('console_monitor.py')),
            str(self.path.resolve()),str(os.getpid()),str(offset)],creationflags=subprocess.CREATE_NEW_CONSOLE)

    def emit(self,kind,text='',**data):
        if not self.enabled: return
        # Logging/console failures must not interrupt a simulation decision.
        try:
            with self.lock:
                if kind in ('progress','request_start'):
                    try: self.open()
                    except OSError: self.process=None
                if self.stream is None or self.stream.closed:
                    self.path.parent.mkdir(parents=True,exist_ok=True)
                    self.stream=self.path.open('a',encoding='utf-8',buffering=65536)
                self.stream.write(json.dumps(dict(time=time.time(),kind=kind,text=text,**data),ensure_ascii=False)+'\n')
                now=time.monotonic()
                if kind not in ('reasoning','content') or now-self.last_flush>=.08:
                    self.stream.flush(); self.last_flush=now
        except (OSError,ValueError): pass

    def close(self):
        self.emit('close','Окно генерации закрывается.')
        with self.lock:
            if self.stream is not None:
                try: self.stream.close()
                except OSError: pass
                self.stream=None
