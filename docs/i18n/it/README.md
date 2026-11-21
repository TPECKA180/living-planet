Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 🌍 Living Planet — civiltà autonome guidate dall'IA

**Modelli linguistici locali. Stati indipendenti. Una storia nata da decisioni reali.**

**Languages / Языки:** [English](../en/README.md) · [Русский](../../../README.md) · [Español](../es/README.md) · [简体中文](../zh-CN/README.md) · [Português (Brasil)](../pt-BR/README.md) · [Deutsch](../de/README.md) · [Français](../fr/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Italiano](../it/README.md)

![Living Planet interface](../../assets/interface.png)

Living Planet è un simulatore strategico in cui 2–6 stati vengono gestiti da modelli linguistici eseguiti in locale. Ogni paese ha risorse, territori, piani, relazioni diplomatiche e memoria propri. Crea un mondo e osserva come gli stati costruiscono, negoziano, commerciano, combattono e affrontano le conseguenze.

## Come funziona la simulazione

Il motore Python verifica gli ordini strutturati dell'IA in base a proprietà, risorse, tecnologie, percorsi e trattati. Dire «costruisco una fabbrica» non crea una fabbrica se mancano risorse o requisiti reali.

55 tipi di azione · 31 risorse · 2 epoche · 25 + 33 tecnologie · 45 edifici industriali · 8 tipi di truppe moderne. L'economia comprende lavoratori, filiere produttive, energia, manutenzione, rifornimenti e crisi. Le mappe sono riproducibili tramite seed ed è disponibile una modalità arcipelago.

## Avvio rapido

1. Installa Python 3.12 e LM Studio. Scarica un modello instruct/chat che supporti JSON strutturato e avvia il server in **Developer**.
2. Scarica il repository come ZIP, estrailo in una cartella scrivibile ed esegui `install.bat` su Windows.
3. Avvia `run.bat`, apri **LM Studio** (o `F2`), inserisci `http://localhost:1234/v1`, aggiorna l'elenco e scegli un modello.
4. Crea un mondo con 2–6 stati e avanza di un giorno oppure attiva l'osservazione (l'interfaccia attuale è in russo).

```bash
python -m pip install -r requirements.txt
python main.py
```

**Il download **non include** modelli, pesi, salvataggi né chiavi API. La versione pubblica v8.0.0 richiede un server di modelli compatibile; non avvia modelli direttamente dalla cartella `models`. Memoria e ricompense forniscono feedback, **senza addestrare i pesi del modello**.**

![Archipelago mode](../../assets/archipelago.png)

## Documentazione e licenza

- [Installazione dettagliata](SETUP.md)
- [Guida completa (russo)](../../GAME_GUIDE.md)
- [Galleria immagini](../../SCREENSHOTS.md)
- [Licenza: distribuzione gratuita e attribuzione obbligatoria](../../../LICENSE) · [Русский перевод лицензии](../../../LICENSE.ru.md)
- [GitHub / Source](https://github.com/TPECKA180/living-planet)

La guida completa e la documentazione tecnica originale sono attualmente in russo. Questa pagina e la guida di installazione tradotta sono introduzioni localizzate, **non** una traduzione dell'interfaccia di gioco.

Quando ridistribuisci o modifichi il progetto, mantieni il credito all'autore originale e il collegamento al repository.
