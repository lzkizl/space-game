import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import MUNITION as MUNITION_SIMPLE
from systeme.settings import (CALQUE_BASE, CALQUE_PLANTES, RACINE, TOURELLE_CADENCE, TOURELLE_DEGATS,
                              TOURELLE_PORTEE, TOURELLE_ROTATION, TOURELLE_STOCK_MAX, TOURELLE_TIRS_PAR_MUNITION,
                              TOURELLE_VITESSE_BALLE)

# =============================================
# ==== Tourelle : une seule tuile, seulement sur la base. Elle s'oriente vers l'alien
# ==== le plus proche et lui tire dessus (voir tourelles.py)
# =============================================
ICONE = RACINE / "image" / "image" / "base_tourelle.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
CONSOMMATION = 100                # watts consommés par tourelle (sans énergie elle ne tire pas)
TOURELLE = True                   # une tourelle apparaît dessus quand on la pose (voir tourelles.py)
TITRE = "Tourelle"                # titre de son panneau (ses munitions)

# le haut qui tourne (la tuile, elle, est le socle)
IMAGE_HAUT = RACINE / "image" / "image" / "haut_tourelle.png"
ROTATION_IMAGE = 0                # degrés à tourner l'image pour que le canon pointe vers la droite
TAILLE_IMAGE_HAUT = 133           # côté de l'image du haut à l'écran (pixels monde) : le corps fait ~1 case
PIVOT_HAUT = (265 / 640, 325 / 640)  # centre du corps dans l'image (canon à droite) : elle tourne autour
PORTEE_CANON = 73                 # distance du centre au bout du canon : là où sortent les tirs

# tir
MUNITION = MUNITION_SIMPLE        # ce qu'on charge dedans
PORTEE = TOURELLE_PORTEE
CADENCE = TOURELLE_CADENCE
ROTATION = TOURELLE_ROTATION
VITESSE_TIR = TOURELLE_VITESSE_BALLE
DEGATS = TOURELLE_DEGATS
TIRS_PAR_MUNITION = TOURELLE_TIRS_PAR_MUNITION
STOCK_MAX = TOURELLE_STOCK_MAX
TIR = "balle"                     # "balle" (un rond qui file) ou "rayon" (instantané, traverse tout : voir tourelles.py)
COULEUR_TIR = (255, 230, 90)

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 22),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
