# Все параметры конфигурации

Рабочий `config.json` создаётся на первом запуске и игнорируется Git. Значения ниже — чистые настройки 7.5.0; они не взяты с компьютера автора.

| Ключ | Тип | По умолчанию |
| --- | --- | --- |
| host | str | "http://localhost:1234/v1" |
| model | str | "" |
| manager_model | str | "" |
| state_models | dict | {} |
| api_key | str | "" |
| timeout | int | 600 |
| temperature | float | 0.7 |
| context_window | int | 131072 |
| max_tokens | int | 16384 |
| input_tokens | int | 56000 |
| context_retry_attempts | int | 8 |
| decision_repair_attempts | int | 3 |
| context_map_cells | int | 4096 |
| context_history | int | 200 |
| context_events | int | 150 |
| context_memories | int | 40 |
| context_messages | int | 200 |
| manage_model_context | bool | true |
| strict_state_isolation | bool | true |
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
| runtime_patch | str | "7.5.0" |
| response_max_bytes | int | 33554432 |
| saves_directory | str | "saves" |
| manager_every | int | 10 |
| seed | int | 42 |
| states | int | 4 |
| database | str | "data/planet.sqlite3" |

## Связь лимитов

`context_window` — общее запрошенное окно; `input_tokens` — желаемый бюджет фактов; `max_tokens` — верхний предел ответа. Вместе с системными инструкциями и техническим запасом они должны поместиться в подтверждённое окно модели. Игра может уменьшить резерв ответа или использовать больше целевого входа, чтобы сохранить текущие данные. Это не обещание выделить неподдерживаемую память.

## Режимы

`strict_state_isolation=true` требует нативного LM Studio API: выгрузка и загрузка чистого экземпляра между владельцами. `manage_model_context` управляет загрузкой вне строгого режима. Для стороннего OpenAI-совместимого сервера без этих методов оба параметра выключают; такой режим не обеспечивает серверную проверку выгрузки. `local_execution` и `local_chronicle` оставляют подготовку приказов и главы локальными. Отключение возвращает дополнительные запросы. `external_console` открывает отдельную консоль только в Windows. `response_max_bytes` ограничивает принимаемый ответ, а не контекст. Остальные архивные лимиты задают максимум истории, передаваемой в запрос, а не срок хранения сохранения.
