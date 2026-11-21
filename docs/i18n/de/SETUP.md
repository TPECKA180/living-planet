Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# Installation und erster Start

[Lokalisierte Projektübersicht](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## Voraussetzungen

Installiere Python 3.12 und LM Studio und lade ein Instruct-/Chat-Textmodell, das strukturierte JSON-Anweisungen befolgen kann. Die Windows-Skripte installieren pygame 2.6.1 in einer lokalen virtuellen Umgebung.

## Einrichtung unter Windows

1. Lade das Repository über **Code → Download ZIP** herunter und entpacke es in einen beschreibbaren Ordner. Starte es nicht direkt aus der ZIP-Datei.
2. Installiere Python 3.12 von [python.org](https://www.python.org/downloads/) und prüfe, ob `py -3.12` funktioniert.
3. Führe `install.bat` einmal aus, um `.venv` anzulegen und die Abhängigkeit zu installieren.
4. Starte `run.bat` und öffne die Einstellungen für **LM Studio** im Spiel oder drücke `F2`.
5. Öffne in LM Studio **Developer**, starte den Server und gib im Spiel `http://localhost:1234/v1` ein.
6. Aktualisiere die Modellliste, wähle ein Modell, speichere die Einstellungen, erstelle eine Welt mit 2–6 Staaten und teste einen Tag vor der Dauerbeobachtung.

## Manueller Start / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Modelle und externe Server

Kompatible Server müssen `/models` und `/chat/completions` bereitstellen. Ohne die native LM-Studio-API sollten strikte Isolation und serverseitige Kontextfenster-Steuerung deaktiviert werden. Ein Remote-Server kann Spieldaten empfangen.

**Modellgewichte, Spielstände und API-Schlüssel sind nicht enthalten. Die öffentliche Version v8.0.0 lädt keine Modelle direkt aus `models`. Bei Bearer-Authentifizierung den Schlüssel in das verborgene API-Schlüsselfeld eintragen und `config.json` nicht veröffentlichen. Die Kontextgröße muss zu Modell und Hardware passen.**

## Weitere Hilfe

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
