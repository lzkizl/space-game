import json

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import RACINE

# =============================================
# ==== Choix du joueur gardés d'une partie à l'autre (langue, musique, volumes...)
# ==== dans parametres.json, à la racine du projet
# =============================================
FICHIER = RACINE / "parametres.json"


def _tout():
    try:
        donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return donnees if isinstance(donnees, dict) else {}


def lire(cle, defaut):
    return _tout().get(cle, defaut)


def ecrire(cle, valeur):
    donnees = _tout()
    donnees[cle] = valeur
    try:
        FICHIER.write_text(json.dumps(donnees, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass   # pas grave : le choix reste valable jusqu'à la fermeture du jeu
