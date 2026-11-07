import json
import runpy
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent


def lancer():
    """Lance le fichier indiqué dans start.json (le jeu), quel que soit le
    fichier sur lequel on a cliqué « Exécuter »."""
    config = json.loads((DOSSIER / "start.json").read_text(encoding="utf-8"))
    runpy.run_path(str(DOSSIER / config["fichier_principal"]), run_name="__main__")
