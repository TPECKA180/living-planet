"""Portable public defaults; local configuration is created on first launch."""
import copy
import json
from pathlib import Path

DEFAULTS=dict(host='http://localhost:1234/v1',model='',manager_model='',state_models={},
    api_key='',timeout=600,temperature=.7,context_window=262144,max_tokens=196608,input_tokens=56000,
    context_retry_attempts=8,decision_repair_attempts=3,context_map_cells=4096,context_history=200,
    context_events=150,context_memories=40,context_messages=200,manage_model_context=True,
    strict_state_isolation=True,external_console=True,stream=True,deep_strategy=True,
    review_relations=True,structured_reviews=True,structured_primary=True,decision_compiler=True,
    calibrate_context=True,detect_repetition=True,unified_execution_review=True,
    reflective_learning=True,local_execution=True,local_chronicle=True,runtime_patch='7.5.5',
    response_max_bytes=33554432,saves_directory='saves',manager_every=10,seed=42,states=4,
    database='data/planet.sqlite3')

def load_config(root):
    path=Path(root)/'config.json'
    if not path.exists():
        config=copy.deepcopy(DEFAULTS)
        path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
        return config
    try:
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value,dict):raise ValueError('config.json должен содержать JSON-объект')
    except (ValueError,UnicodeError) as exc:
        raise ValueError('Не удалось прочитать config.json. Исправьте JSON или переименуйте файл, чтобы создать чистые настройки. Сохранения находятся отдельно в saves.') from exc
    config=copy.deepcopy(DEFAULTS);config.update(value)
    return config

def open_help(root):
    import webbrowser
    path=Path(root)/'docs'/'index.html'
    if not path.is_file():raise FileNotFoundError('Нет docs/index.html. Откройте README.md или скачайте полную сборку.')
    return webbrowser.open(path.resolve().as_uri())
