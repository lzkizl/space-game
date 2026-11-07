import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Table de craft : une seule tuile, seulement sur la base.
# ==== Un clic dessus ouvre le menu de fabrication (voir craft.py)
# =============================================
ICONE = RACINE / "image" / "image" / "table_craft.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
TABLE_CRAFT = True                # un clic sur cette tuile ouvre la table de craft

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 19),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
