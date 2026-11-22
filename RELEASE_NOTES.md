<p align="center">
  <img src="https://raw.githubusercontent.com/TPECKA180/living-planet/v8.5.1/docs/assets/living-planet-logo.png" alt="Living Planet — пиксельная эмблема в стиле тёмного фэнтези" width="620">
</p>

# Living Planet 8.5.1 · возвращение потока модели

**Консоль наблюдения снова включена по умолчанию. Следите за генерацией и ответом государства в отдельном окне, пока игра продолжает работать.**

> Reasoning отображается, только если его действительно передаёт выбранная модель. Living Planet не пытается извлечь скрытую внутреннюю цепочку рассуждений.

## Скачать

- **[SETUPGAME.exe — установить игру](https://github.com/TPECKA180/living-planet/releases/download/v8.5.1/SETUPGAME.exe)** · мастер установки, выбор папки и ярлык Living Planet.
- **[LivingPlanet-8.5.1-Portable.zip — переносимая версия](https://github.com/TPECKA180/living-planet/releases/download/v8.5.1/LivingPlanet-8.5.1-Portable.zip)** · распакуйте архив и запустите `LivingPlanet/LivingPlanet.exe`.

Публичные пакеты содержат игру, пиксельную иконку и встроенный Windows runtime llama.cpp. Веса GGUF в загрузку не входят: поместите свою модель в `models` рядом с игрой и выберите её в **Модели · F2**. LM Studio, Python, API-ключ и сетевой сервер не нужны. Сведения о сторонних компонентах — в [уведомлениях](https://github.com/TPECKA180/living-planet/blob/v8.5.1/docs/THIRD_PARTY_NOTICES.md).

## Что исправлено в 8.5.1

- Консоль потока модели снова включена по умолчанию и открывается во время наблюдения.
- В консоль поступают состояние генерации, reasoning при его наличии и обычный ответ модели.
- Настройки 8.5.0 автоматически включают консоль при первом запуске 8.5.1. Размер контекста, выбранная модель и личные параметры сохраняются.
- Консоль можно выключить или включить обратно в окне **Модели · F2**.
- В окне генерации прямо поясняется, что скрытая цепочка рассуждений не извлекается.

## Быстрый старт

1. Установите игру через `SETUPGAME.exe` либо распакуйте переносимый архив.
2. Положите совместимый файл `.gguf` в папку `models` рядом с `LivingPlanet.exe`.
3. Откройте **Модели · F2**, выберите модель и сохраните настройки.
4. Создайте мир и нажмите **Наблюдать** или **Один день**. Консоль покажет поток модели отдельно от игрового окна.

В старых конфигурациях параметр консоли обновляется один раз. Если модель не отправляет reasoning, консоль всё равно показывает прогресс и её обычный ответ.

## Галерея Living Planet

<p align="center">
  <img src="https://raw.githubusercontent.com/TPECKA180/living-planet/v8.5.1/docs/assets/interface.png" alt="Основной экран: карта, государства, ресурсы и летопись" width="48%">
  <img src="https://raw.githubusercontent.com/TPECKA180/living-planet/v8.5.1/docs/assets/models.png" alt="Настройки встроенной локальной модели" width="48%">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/TPECKA180/living-planet/v8.5.1/docs/assets/archipelago.png" alt="Пиксельная карта архипелага" width="48%">
  <img src="https://raw.githubusercontent.com/TPECKA180/living-planet/v8.5.1/docs/assets/industry.png" alt="Экономика и производственные цепочки государства" width="48%">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/TPECKA180/living-planet/v8.5.1/docs/assets/relations.png" alt="Дипломатическое досье государства" width="48%">
  <img src="https://raw.githubusercontent.com/TPECKA180/living-planet/v8.5.1/docs/assets/history.png" alt="Летопись демонстрационного мира" width="48%">
</p>

Все снимки показывают подготовленные демонстрационные миры. Личные сохранения и модельные запросы в публичную галерею не входят. Полная [галерея из 11 экранов](https://github.com/TPECKA180/living-planet/blob/v8.5.1/docs/SCREENSHOTS.md) и [руководство по установке](https://github.com/TPECKA180/living-planet/blob/v8.5.1/docs/SETUP.md) доступны в репозитории.
