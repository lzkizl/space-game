import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Panneau : une seule tuile, seulement sur la base
# =============================================
ICONE = RACINE / "image" / "image" / "panneau.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où les tuiles sont posées (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
PUISSANCE = 100                   # watts produits par panneau posé

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 5),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
