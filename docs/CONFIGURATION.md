# Все параметры конфигурации

Рабочий `config.json` создаётся на первом запуске и игнорируется Git. Значения ниже — чистые настройки 8.5.1 со встроенным llama.cpp и локальными GGUF-моделями.

| Ключ | Тип | По умолчанию |
| --- | --- | --- |
| host | str | "http://127.0.0.1:32124/v1" |
| model | str | "" |
| manager_model | str | "" |
| state_models | dict | {} |
| api_key | str | "" |
| timeout | int | 600 |
| temperature | float | 0.7 |
| context_window | int | 262144 |
| max_tokens | int | 196608 |
| input_tokens | int | 12000 |
| context_retry_attempts | int | 8 |
| decision_repair_attempts | int | 3 |
| context_map_cells | int | 4096 |
| context_history | int | 200 |
| context_events | int | 150 |
| context_memories | int | 40 |
| context_messages | int | 200 |
| manage_model_context | bool | false |
| strict_state_isolation | bool | false |
| external_console | bool | true |
| stream | bool | true |
| deep_strategy | bool | true |
| review_relations | bool | true |
| structured_reviews | bool | true |
| structured_primary | bool | true |
| decision_compiler | bool | true |
| calibrate_context | bool | true |
| detect_repetition | bool | true |
| unified_execution_review | bool | true |
| reflective_learning | bool | true |
| local_execution | bool | true |
| local_chronicle | bool | true |
| runtime_patch | str | "8.5.1" |
| gpu_layers | int | 99 |
| local_port | int | 32124 |
| response_max_bytes | int | 33554432 |
| saves_directory | str | "saves" |
| manager_every | int | 10 |
| seed | int | 42 |
| states | int | 4 |
| database | str | "data/planet.sqlite3" |

## Связь лимитов

`context_window` — окно локального движка; `input_tokens` — целевой бюджет фактов; `max_tokens` — верхний предел генерации. Уменьшите окно, если модель не помещается в видеопамять или память компьютера. `gpu_layers=0` использует CPU; большее значение переносит больше слоёв на GPU. `local_port` — внутренний loopback-порт, к которому игра подключается автоматически.

## Режимы

Модель выбирается по имени файла `.gguf` в папке `models`; сетевой адрес и ключ не используются. Запросы выполняются локально и последовательно, в контекст передаются данные активного государства. `external_console` открывает отдельное окно потока только в Windows. `response_max_bytes` ограничивает размер ответа, а не окно контекста. Другие лимиты истории задают объём фактов в запросе, но не срок хранения сохранения.

[Подробно о лимитах и памяти](LIMITS.md).
