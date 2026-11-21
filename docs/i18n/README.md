Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# Documentation languages / Языки документации

This directory contains localized **project introductions and first-run instructions**, not translations of the full game guide or the game interface. The original Russian documents remain the reference until each section is reviewed and translated. All technical identifiers, version constraints, license obligations and links to the original creator must be preserved.

| Language | Overview | Setup |
| --- | --- | --- |
| English | [README](en/README.md) | [SETUP](en/SETUP.md) |
| Русский | [README](../../README.md) | [SETUP](../SETUP.md) |
| Español | [README](es/README.md) | [SETUP](es/SETUP.md) |
| 简体中文 | [README](zh-CN/README.md) | [SETUP](zh-CN/SETUP.md) |
| Português (Brasil) | [README](pt-BR/README.md) | [SETUP](pt-BR/SETUP.md) |
| Deutsch | [README](de/README.md) | [SETUP](de/SETUP.md) |
| Français | [README](fr/README.md) | [SETUP](fr/SETUP.md) |
| 日本語 | [README](ja/README.md) | [SETUP](ja/SETUP.md) |
| 한국어 | [README](ko/README.md) | [SETUP](ko/SETUP.md) |
| Italiano | [README](it/README.md) | [SETUP](it/SETUP.md) |

## Translation boundaries

- The currently published v8.0.0 requires Python 3.12, pygame, a compatible LLM server (LM Studio by default) and a separately downloaded model.
- No model weights, saved worlds, API keys or paid services are bundled. Model memory/rewards are not model-weight fine-tuning.
- The in-game Russian interface, complete game guide (`docs/GAME_GUIDE.md`), action catalog and technical documents are **not yet translated**.
- Keep the mandatory original-creator first sentence unchanged in all localized READMEs. Consult [the authoritative English license](../../LICENSE) and [Russian translation](../../LICENSE.ru.md).
- Translations are human-readable community documentation; technical command names, file paths, API URLs and JSON keys must never be translated.
- When features change, update the Russian source and English introduction first, then reconcile localized texts against the actual release.
