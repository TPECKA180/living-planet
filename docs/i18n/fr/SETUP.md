Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# Installation et premier lancement

[Présentation traduite](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## Prérequis

Installez Python 3.12 et LM Studio et téléchargez un modèle texte instruct/chat capable de respecter des instructions JSON structurées. Les scripts Windows installent pygame 2.6.1 dans un environnement virtuel local.

## Installation sous Windows

1. Téléchargez le dépôt avec **Code → Download ZIP**, puis extrayez-le dans un dossier où l’écriture est autorisée. Ne l’exécutez pas depuis le ZIP.
2. Installez Python 3.12 depuis [python.org](https://www.python.org/downloads/) et vérifiez que `py -3.12` fonctionne.
3. Lancez `install.bat` une fois pour créer `.venv` et installer la dépendance.
4. Lancez `run.bat`, ouvrez les paramètres **LM Studio** dans le jeu ou appuyez sur `F2`.
5. Dans LM Studio, ouvrez **Developer** et lancez le serveur ; entrez `http://localhost:1234/v1` dans le jeu.
6. Actualisez la liste, sélectionnez un modèle, enregistrez, créez un monde de 2 à 6 pays et testez une journée avant l’observation continue.

## Démarrage manuel / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Modèles et serveurs externes

Un serveur compatible doit proposer `/models` et `/chat/completions`. Sans API native LM Studio, désactivez l’isolation stricte et la gestion de la fenêtre de contexte côté serveur. Un serveur distant peut recevoir les données du jeu.

**Aucun poids de modèle, sauvegarde ou clé API n’est fourni. La version publique v8.0.0 ne charge pas de modèle directement depuis `models`. Si un jeton Bearer est requis, saisissez-le dans le champ masqué de clé API et ne publiez pas `config.json`. Adaptez le contexte au modèle et au matériel.**

## Aide supplémentaire

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
