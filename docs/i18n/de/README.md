Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 🌍 Living Planet — autonome KI-Zivilisationen

**Lokale Sprachmodelle. Unabhängige Staaten. Eine Geschichte aus echten Entscheidungen.**

**Languages / Языки:** [English](../en/README.md) · [Русский](../../../README.md) · [Español](../es/README.md) · [简体中文](../zh-CN/README.md) · [Português (Brasil)](../pt-BR/README.md) · [Deutsch](../de/README.md) · [Français](../fr/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Italiano](../it/README.md)

![Living Planet interface](../../assets/interface.png)

Living Planet ist eine Strategiesimulation, in der 2–6 Staaten von lokal ausgeführten Sprachmodellen gesteuert werden. Jedes Land besitzt eigene Ressourcen, Gebiete, Pläne, diplomatische Beziehungen und ein Gedächtnis. Erstelle eine Welt und beobachte, wie Staaten bauen, verhandeln, handeln, Krieg führen und mit Folgen umgehen.

## So funktioniert die Simulation

Die Python-Spielengine prüft strukturierte KI-Befehle anhand von Besitzverhältnissen, Ressourcen, Technologien, Routen und Verträgen. Die Aussage „Ich baue eine Fabrik“ erschafft keine Fabrik, wenn Voraussetzungen oder Mittel fehlen.

55 Aktionstypen · 31 Ressourcen · 2 Epochen · 25 + 33 Technologien · 45 Industriegebäude · 8 moderne Truppentypen. Die Wirtschaft umfasst Arbeitskräfte, Produktionsketten, Energie, Unterhalt, Versorgung und Krisen. Karten sind über Seeds reproduzierbar; es gibt einen Archipel-Modus.

## Schnellstart

1. Installiere Python 3.12 und LM Studio. Lade ein Instruct-/Chat-Modell, das strukturiertes JSON ausgeben kann, und starte in **Developer** den Server.
2. Lade das Repository als ZIP herunter, entpacke es in einen beschreibbaren Ordner und starte unter Windows `install.bat`.
3. Starte `run.bat`, öffne **LM Studio** (oder `F2`), trage `http://localhost:1234/v1` ein, aktualisiere die Liste und wähle ein Modell.
4. Erstelle eine Welt mit 2–6 Staaten und starte einen einzelnen Tag oder die Beobachtung (die derzeitige Oberfläche ist russisch).

```bash
python -m pip install -r requirements.txt
python main.py
```

**Der Download enthält **kein** Sprachmodell, keine Modellgewichte, Spielstände oder API-Schlüssel. Die veröffentlichte Version v8.0.0 benötigt einen kompatiblen Modellserver und startet Modelle nicht direkt aus dem Ordner `models`. Gedächtnis und Belohnungen liefern Feedback, **trainieren jedoch nicht die Modellgewichte**.**

![Archipelago mode](../../assets/archipelago.png)

## Dokumentation und Lizenz

- [Installationsanleitung](SETUP.md)
- [Vollständiges Handbuch (Russisch)](../../GAME_GUIDE.md)
- [Screenshot-Galerie](../../SCREENSHOTS.md)
- [Lizenz: dauerhaft kostenlos und mit Urheberangabe](../../../LICENSE) · [Русский перевод лицензии](../../../LICENSE.ru.md)
- [GitHub / Source](https://github.com/TPECKA180/living-planet)

Das vollständige Handbuch und die technische Referenz liegen derzeit auf Russisch vor. Diese Seite und die übersetzte Installationsanleitung sind lokalisierte Einführungen, **keine Übersetzung der Spieloberfläche**.

Bei Weitergabe oder Änderungen müssen ursprünglicher Autor und Repository-Link erhalten bleiben.
