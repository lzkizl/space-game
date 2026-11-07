import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Table de recherche : une seule tuile (gid 35 du tileset), seulement sur la base.
# ==== Pour l'instant elle se pose et se reprend (outil de déconstruction), sans rien faire d'autre.
# =============================================
ICONE = RACINE / "image" / "image" / "table_recherche.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 35),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
