import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, RACINE

# =============================================
# ==== Base : bloc 2x2, posable partout
# =============================================
ICONE = RACINE / "image" / "image" / "base.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_BASE             # calque Tiled où les tuiles sont posées
SUPPORT = None                   # calque où il doit déjà y avoir une tuile (None = aucun)
LIBRE = CALQUE_BASE              # calque où les cases visées doivent être vides (pas de base sur une base)

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 3),   # haut gauche
    (1, 0, 4),   # haut droite
    (0, 1, 12),  # bas gauche
    (1, 1, 13),  # bas droite
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
