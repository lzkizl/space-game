import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Coffre : une seule tuile (gid 20 du tileset), posée sur la base.
# ==== Son inventaire est géré par coffres.py
# =============================================
ICONE = RACINE / "image" / "image" / "coffre.png"  # image dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
COFFRE = True                     # un clic dessus ouvre son inventaire
TITRE = "Coffre"                  # titre de son inventaire
NB_CASES = 25                     # taille de son inventaire : 5 x 5

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 20),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
