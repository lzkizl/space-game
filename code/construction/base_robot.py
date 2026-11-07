import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Base du robot : une seule tuile, seulement sur la base
# =============================================
ICONE = RACINE / "image" / "image" / "base_robot.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
CONSOMMATION = 250                # watts consommés par robot (2,5 panneaux solaires)
ROBOT = True                     # un robot apparaît dessus quand on la pose (voir robot.py)

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 11),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
