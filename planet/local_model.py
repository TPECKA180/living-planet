"""Manage the private llama.cpp server shipped beside the game."""
from pathlib import Path
import os
import queue
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request


def parse_runtime_rate(line):
    """Extract live llama.cpp prompt-read or generated-token rate from its log."""
    if 'prompt processing' in line:
        match=re.search(r'n_tokens\s*=\s*(\d+).*?([\d.]+)\s*tokens per second',line)
        if match:return 'read',float(match.group(2))
    if 'prompt eval time' in line:
        match=re.search(r'([\d.]+)\s*tokens per second\s*\)',line)
        if match:return 'read',float(match.group(1))
    if 'n_gen' in line:
        match=re.search(r'\btg\s*=\s*([\d.]+)\s*t/s',line)
        if match:return 'generate',float(match.group(1))
    return None


class LocalModelRuntime:
    def __init__(self, app_root):
        self.root = Path(app_root).resolve()
        self.process = None
        self._log = None
        self.metrics = queue.SimpleQueue()
        self._monitor_stop = threading.Event()
        self._monitor_thread = None

    def models(self):
        folder = self.root / 'models'
        if not folder.is_dir():
            return []
        return sorted(path.name for path in folder.iterdir()
                      if path.is_file() and path.suffix.lower() == '.gguf')

    def ready(self):
        if not self.process or self.process.poll() is not None:
            return False
        port = getattr(self, '_port', 32124)
        try:
            request = urllib.request.Request(f'http://127.0.0.1:{port}/health')
            with urllib.request.urlopen(request, timeout=.5) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def start(self, config):
        self.stop()
        name = str(config.get('model', '')).strip()
        if not name:
            return 'Положите модель GGUF в папку models и выберите её в настройках.'
        model = (self.root / 'models' / name).resolve()
        if model.parent != (self.root / 'models').resolve() or not model.is_file() or model.suffix.lower() != '.gguf':
            return 'Выбранная модель не найдена в папке models.'
        server = self.root / 'runtime' / 'llama-server.exe'
        if not server.is_file():
            return 'Не найден встроенный runtime: runtime/llama-server.exe.'
        port = int(config.get('local_port', 32124))
        context = max(16384, int(config.get('context_window', 262144)))
        gpu_layers = max(0, int(config.get('gpu_layers', 99)))
        log_dir = self.root / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        temp = self.root / 'runtime' / 'tmp'
        temp.mkdir(parents=True, exist_ok=True)
        self._log = (log_dir / 'local-model.log').open('a', encoding='utf-8', errors='replace')
        self._log.write(f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")}] Starting {name}\n')
        self._log.flush()
        log_offset=self._log.tell()
        env = os.environ.copy()
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
        command = [str(server), '--model', str(model), '--host', '127.0.0.1',
                   '--port', str(port), '--ctx-size', str(context),
                   '--n-gpu-layers', str(gpu_layers), '--parallel', '1',
                   '--reasoning-budget', str(max(-1, int(config.get('reasoning_budget', 1024))))]
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            self.process = subprocess.Popen(command, cwd=self.root, env=env,
                                             stdin=subprocess.DEVNULL,
                                             stdout=self._log, stderr=subprocess.STDOUT,
                                             creationflags=flags)
        except OSError as exc:
            self._close_log()
            return f'Не удалось запустить встроенный llama.cpp: {exc}'
        self._port = port
        self._monitor_stop.clear()
        self._monitor_thread=threading.Thread(target=self._watch_log,args=(log_dir/'local-model.log',log_offset),daemon=True)
        self._monitor_thread.start()
        config['host'] = f'http://127.0.0.1:{port}/v1'
        config['api_key'] = ''
        return 'Загружается локальная модель…'

    def stop(self):
        self._monitor_stop.set()
        process = self.process
        self.process = None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if self._monitor_thread and self._monitor_thread is not threading.current_thread():
            self._monitor_thread.join(timeout=1)
        self._monitor_thread=None
        self._close_log()

    def _watch_log(self, path, offset):
        try:
            with path.open('r',encoding='utf-8',errors='replace') as stream:
                stream.seek(offset)
                while not self._monitor_stop.is_set():
                    line=stream.readline()
                    if not line:
                        if self.process is not None and self.process.poll() is not None:break
                        time.sleep(.05)
                        continue
                    metric=parse_runtime_rate(line)
                    if metric:self.metrics.put(metric)
        except OSError:
            return

    def _close_log(self):
        if self._log:
            self._log.close()
            self._log = None
