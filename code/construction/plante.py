import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Plante : une seule tuile, seulement sur la base
# =============================================
ICONE = RACINE / "image" / "image" / "plante.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où les tuiles sont posées
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
CONSOMMATION = 50                 # watts consommés par plante posée

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 14),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
