Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# Instalación y primer inicio

[Presentación traducida](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## Requisitos

Instala Python 3.12 y LM Studio y descarga un modelo de texto instruct/chat capaz de seguir instrucciones JSON estructuradas. Los scripts de Windows instalan pygame 2.6.1 en un entorno virtual local.

## Configuración en Windows

1. Descarga el repositorio mediante **Code → Download ZIP** y descomprímelo en una carpeta con permisos de escritura. No lo ejecutes desde el ZIP.
2. Instala Python 3.12 desde [python.org](https://www.python.org/downloads/) y comprueba que funciona `py -3.12`.
3. Ejecuta `install.bat` una vez para crear `.venv` e instalar la dependencia.
4. Ejecuta `run.bat`. Abre los ajustes de **LM Studio** en el juego o pulsa `F2`.
5. En LM Studio, abre **Developer** y activa el servidor; introduce `http://localhost:1234/v1` en el juego.
6. Actualiza la lista, elige un modelo, guarda los ajustes, crea un mundo de 2–6 países y simula un día antes de activar la observación continua.

## Inicio manual / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Modelos y servidores externos

Un servidor compatible debe ofrecer `/models` y `/chat/completions`. Con servidores que no tengan la API nativa de LM Studio, desactiva el aislamiento estricto y el control del contexto del servidor. Un servidor remoto puede recibir los datos del juego.

**El proyecto no incluye pesos de modelos, partidas guardadas ni claves API. La versión v8.0.0 no ejecuta directamente modelos desde `models`. Si el servidor requiere un token Bearer, introdúcelo en el campo oculto de clave API y no publiques `config.json`. Ajusta el contexto al hardware y al modelo reales.**

## Ayuda adicional

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
