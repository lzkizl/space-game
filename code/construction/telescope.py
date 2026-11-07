import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Télescope NASA : un seul objet dans l'inventaire, mais une fois posé il prend un bloc
# ==== de 2x2 tuiles (gids 32, 33, 41, 42 du tileset). Il se pose dans le vide de l'espace,
# ==== pas sur la base. Il découvre la grande carte (M) là où il regarde (voir structures/telescopes.py) ;
# ==== un boîtier (PC) avec processeur, RAM et clé USB satellite le pilote (voir coffres.py).
# =============================================
ICONE = RACINE / "image" / "image" / "telescope_nasa.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = None                    # pas besoin de base dessous...
LIBRE = CALQUE_BASE               # ...au contraire : il faut du vide sur le calque base
TELESCOPE = True                  # repère cette construction (son panneau, sa fréquence : voir telescopes.py)
ESPACE_SEULEMENT = True           # ne se pose pas sur une planète (il découvre la carte de l'espace)

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 32),   # haut gauche
    (1, 0, 33),   # haut droite
    (0, 1, 41),   # bas gauche
    (1, 1, 42),   # bas droite
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
