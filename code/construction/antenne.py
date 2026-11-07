import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Antenne radio : 1 tuile de large sur 3 de haut (gid 23 en haut, 25 au milieu, 24 en
# ==== bas), seulement sur la base. Elle sert à communiquer avec les autres vaisseaux
# ==== (voir code/ia/)
# =============================================
ICONE = RACINE / "image" / "image" / "antenne_icone.png"  # antenne.png recadrée, pour l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
ANTENNE = True                    # repère cette construction (la radio compte les antennes posées)

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 23),   # haut (tête de l'antenne)
    (0, 1, 25),   # milieu (le mât)
    (0, 2, 24),   # bas (le boîtier)
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
