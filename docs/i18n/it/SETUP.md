Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# Installazione e primo avvio

[Panoramica tradotta](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## Requisiti

Installa Python 3.12 e LM Studio e scarica un modello testuale instruct/chat capace di seguire istruzioni JSON strutturate. Gli script Windows installano pygame 2.6.1 in un ambiente virtuale locale.

## Configurazione Windows

1. Scarica il repository con **Code → Download ZIP** ed estrailo in una cartella scrivibile. Non avviare il programma direttamente dal ZIP.
2. Installa Python 3.12 da [python.org](https://www.python.org/downloads/) e verifica che `py -3.12` funzioni.
3. Esegui `install.bat` una volta per creare `.venv` e installare la dipendenza.
4. Avvia `run.bat`, apri le impostazioni **LM Studio** nel gioco o premi `F2` quando sei nel mondo.
5. In LM Studio apri **Developer** e avvia il server; nel gioco inserisci `http://localhost:1234/v1`.
6. Aggiorna l'elenco, scegli un modello, salva le impostazioni, crea un mondo con 2–6 stati ed esegui un giorno prima dell'osservazione continua.

## Avvio manuale / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Modelli e server esterni

Un server compatibile deve supportare `/models` e `/chat/completions`. Se non dispone delle API native LM Studio, disabilita l'isolamento rigoroso e il controllo della finestra di contesto lato server. Un server remoto può ricevere i dati di gioco.

**Non sono inclusi pesi dei modelli, salvataggi o chiavi API. La versione pubblica v8.0.0 non carica modelli direttamente dalla cartella `models`. Se serve un token Bearer, inseriscilo nel campo nascosto per la chiave API e non pubblicare `config.json`. Regola il contesto in base a modello e memoria.**

## Altra documentazione

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
