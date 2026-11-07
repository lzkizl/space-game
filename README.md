# 🚀 Space Game

Jeu spatial en 2D avec cartes, tilesets, musique et effets sonores, jouable en ligne via un serveur.

<!-- À compléter : ajoute une capture d'écran du jeu ici, par exemple :
![Aperçu du jeu](image/capture.png) -->

## Fonctionnalités

- Exploration de cartes construites à partir de tilesets
- Musique et effets sonores avec réglage séparé des volumes
- Mode multijoueur : connexion à un serveur par adresse
- Interface disponible en français (langue réglable)
- Affichage en plein écran ou en fenêtre
- Tests automatisés

<!-- À compléter : ajoute ou retire des lignes pour coller à ton jeu (vaisseaux, ennemis, niveaux, etc.) -->

## Structure du projet

| Dossier / fichier | Contenu |
|---|---|
| `code/` | Code source du jeu |
| `map/` | Cartes / niveaux |
| `tilset/` | Tilesets utilisés pour construire les cartes |
| `image/` | Images et sprites |
| `son/` | Musiques et effets sonores |
| `tests/` | Tests |
| `parametres.json` | Réglages du joueur (voir ci-dessous) |

## Installation

```bash
git clone https://github.com/llzkizll/space-game.git
cd space-game
```

<!-- À compléter selon ton langage, par exemple pour Python :
pip install -r requirements.txt -->

## Lancer le jeu

```bash
# À compléter : la commande qui démarre le jeu, par exemple
# python code/main.py
```

## Paramètres

Les réglages sont enregistrés dans `parametres.json` :

| Clé | Description |
|---|---|
| `langue` | Langue de l'interface (`fr`) |
| `volume_musique` | Volume de la musique (entre `0.0` et `1.0`) |
| `volume_sons` | Volume des effets sonores (entre `0.0` et `1.0`) |
| `pseudo` | Nom affiché en jeu |
| `derniere_adresse` | Dernière adresse de serveur utilisée |
| `fenetre` | Mode d'affichage (`plein` pour le plein écran) |

## Multijoueur

Pour rejoindre une partie, entre l'adresse du serveur (au format `hote:port`) dans le jeu.

<!-- À compléter : explique comment héberger un serveur si c'est possible -->

## Tests

```bash
# À compléter, par exemple : pytest tests/
```

## Contrôles

<!-- À compléter : liste des touches (déplacement, tir, pause, etc.) -->

## Licence

<!-- À compléter : choisis une licence (par exemple MIT) ou retire cette section -->
