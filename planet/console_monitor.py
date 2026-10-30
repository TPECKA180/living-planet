"""Launched with CREATE_NEW_CONSOLE. Reads model output; never runs its text."""
import ctypes
import json
import os
from pathlib import Path
import re
import sys
import time


def clean(text):
    text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',str(text))
    return ''.join(c for c in text if c in '\n\t' or ord(c)>=32 and ord(c)!=127)


def parent_alive(pid):
    if os.name=='nt':
        kernel=ctypes.windll.kernel32
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x00100000,False,pid)
        if not handle: return False
        try: return kernel.WaitForSingleObject(handle,0)==258
        finally: kernel.CloseHandle(handle)
    try: os.kill(pid,0); return True
    except OSError: return False


def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    if os.name=='nt': ctypes.windll.kernel32.SetConsoleTitleW('Живая планета | прямая трансляция LM Studio')
    path=Path(sys.argv[1]); pid=int(sys.argv[2]); offset=int(sys.argv[3])
    print('ЖИВАЯ ПЛАНЕТА · LM STUDIO · ПОТОК ГЕНЕРАЦИИ\n')
    print('Здесь выводятся полученные от сервера reasoning и ответ.\n'
          'Если модель не передаёт reasoning, будет показан только её ответ.\n'
          'Полоса показывает готовность государств общего дня, а не выдуманный процент генерации.\n',flush=True)
    stream=None; waiting=False; started=time.monotonic(); channel=None; last_tick=0
    try:
        while parent_alive(pid):
            if stream is None:
                if not path.exists(): time.sleep(.05); continue
                stream=path.open(encoding='utf-8'); stream.seek(offset)
            position=stream.tell(); line=stream.readline()
            if not line or not line.endswith('\n'):
                stream.seek(position)
                if waiting and time.monotonic()-last_tick>.4:
                    elapsed=int(time.monotonic()-started); glyph='|/-\\'[elapsed%4]
                    print(f'\r[{glyph}] Ожидание фрагментов модели · {elapsed:3d} с ',end='',flush=True); last_tick=time.monotonic()
                time.sleep(.05); continue
            try: item=json.loads(line)
            except ValueError: continue
            kind=item['kind']; text=clean(item.get('text',''))
            if waiting: print('\r'+' '*78+'\r',end='',flush=True)
            if kind=='close': print('\n'+text); return
            if kind in ('reasoning','content'):
                if kind!=channel:
                    print('\n\n'+('REASONING МОДЕЛИ' if kind=='reasoning' else 'ОТВЕТ МОДЕЛИ')+'\n',flush=True); channel=kind
                print(text,end='',flush=True); waiting=False
            elif kind=='progress':
                total=max(1,item.get('total',1)); done=item.get('completed',0); bars=int(30*done/total)
                print(f'\nДЕНЬ {item.get("day",0)} · {clean(item.get("stage","решения"))}  [{"#"*bars}{"-"*(30-bars)}] {done}/{total} государств\n',flush=True)
            else:
                print('\n'+text,flush=True)
                if kind=='request_start':
                    started=time.monotonic(); waiting=True; channel=None
                elif kind in ('request_end','error'): waiting=False
    finally:
        if stream is not None: stream.close()


if __name__=='__main__': main()
