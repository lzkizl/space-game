import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme import preferences

# =============================================
# ==== Langue de l'IA (choisie dans les paramètres, gardée dans parametres.json)
# =============================================
LANGUES = {"fr": "Français", "en": "English"}
DEFAUT = "fr"

_langue = None


def actuelle():
    """Code de la langue choisie ("fr" ou "en")."""
    global _langue
    if _langue is None:
        code = preferences.lire("langue", DEFAUT)
        _langue = code if code in LANGUES else DEFAUT
    return _langue


def choisir(code):
    """Change la langue et la garde pour la prochaine fois."""
    global _langue
    if code not in LANGUES:
        return
    _langue = code
    preferences.ecrire("langue", code)
