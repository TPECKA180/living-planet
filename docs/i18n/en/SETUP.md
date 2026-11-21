Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# Installation and first launch

[Localized project overview](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## Requirements

Install Python 3.12 and LM Studio, then download a text instruct/chat model that can follow structured JSON instructions. The Windows scripts install pygame 2.6.1 in a local virtual environment.

## Windows setup

1. Download the repository using **Code → Download ZIP** and extract it to a writable folder. Do not run it inside the ZIP.
2. Install Python 3.12 from [python.org](https://www.python.org/downloads/). Make sure the Windows `py -3.12` launcher works.
3. Run `install.bat` once. It creates `.venv` and installs the Python dependency.
4. Run `run.bat`. Open the **LM Studio** settings or press `F2` in the world.
5. In LM Studio, open **Developer**, start the local server, then use `http://localhost:1234/v1` in the game.
6. Refresh the list, select a model, save settings, create a 2–6-country world and execute one day before enabling continuous observation.

## Manual / Linux launch

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Models and external servers

A compatible server must support `/models` and `/chat/completions`. For a server other than LM Studio, native model load/unload checks may not work; disable strict isolation and server context-window control when using an OpenAI-compatible server without the LM Studio native API. A remote endpoint can receive game data, unlike local-only operation.

**Neither model weights nor saves or API keys are included. The published v8.0.0 does not load an LLM directly from `models`. If the server uses a Bearer token, enter it in the game's hidden API-key field and never share `config.json` publicly. Context limits must fit the actual model and memory.**

## Further help

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
