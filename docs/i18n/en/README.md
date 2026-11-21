Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 🌍 Living Planet — autonomous AI civilizations

**Local language models. Independent nations. A history shaped by actual decisions.**

**Languages / Языки:** [English](../en/README.md) · [Русский](../../../README.md) · [Español](../es/README.md) · [简体中文](../zh-CN/README.md) · [Português (Brasil)](../pt-BR/README.md) · [Deutsch](../de/README.md) · [Français](../fr/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Italiano](../it/README.md)

![Living Planet interface](../../assets/interface.png)

Living Planet is an independent grand-strategy simulation in which 2–6 nations are directed by locally hosted language models. Each country has its own resources, territory, plans, diplomatic relations and memory. You create a world and observe how nations build, negotiate, trade, fight and sometimes fail.

## How the simulation works

The Python game engine validates the model's structured orders against actual ownership, resources, technologies, routes and treaties. A promise to build a factory does not produce one unless it can really be built and paid for.

55 action types · 31 resources · 2 eras · 25 + 33 technologies · 45 industrial-era buildings · 8 modern troop types. The economy includes labor, production chains, energy, upkeep, supply and crises. Maps have reproducible seeds, close-up pixel details and an archipelago mode.

## Quick start

1. Install Python 3.12 and LM Studio. Download an instruction/chat model capable of returning structured JSON and start the LM Studio server in **Developer**.
2. Download the repository as a ZIP, extract it to a writable folder and run `install.bat` (Windows).
3. Run `run.bat`; open **LM Studio** (or `F2`), enter `http://localhost:1234/v1`, refresh the list and select a model.
4. Create a world with 2–6 nations, then use **One day** or **Observe** to start the simulation.

```bash
python -m pip install -r requirements.txt
python main.py
```

**The download does **not** include an LLM, weights, save files or API keys. The published v8.0.0 uses a compatible model server; it does not launch models directly from the `models` folder. Results depend on your model and hardware. Rewards and memory currently provide feedback **without fine-tuning model weights**.**

![Archipelago mode](../../assets/archipelago.png)

## Documentation and licensing

- [Detailed installation](SETUP.md)
- [Original player guide (Russian)](../../GAME_GUIDE.md)
- [Screenshot gallery](../../SCREENSHOTS.md)
- [License: always free with original-author attribution](../../../LICENSE) · [Русский перевод лицензии](../../../LICENSE.ru.md)
- [GitHub / Source](https://github.com/TPECKA180/living-planet)

The original full game guide and technical reference are currently in Russian. This page and the localized installation guide are introductory translations, **not** a translation of the in-game UI.

Keep the original creator credit and link when redistributing or modifying this project.
