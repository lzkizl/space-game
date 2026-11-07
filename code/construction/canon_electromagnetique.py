import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import BALLE_PERFORMANTE
from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Canon électromagnétique : une tourelle (même fonctionnement, voir tourelles.py) qui tire
# ==== moins souvent mais plus loin et beaucoup plus fort : un rayon bleu instantané qui traverse
# ==== tous les ennemis sur sa ligne. Il ne charge que des balles performantes (10 tirs chacune).
# ==== Une seule tuile (gid 34 du tileset : le socle), seulement sur la base.
# =============================================
ICONE = RACINE / "image" / "image" / "socle_canon_electromagnetique.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
CONSOMMATION = 250                # watts consommés (sans énergie il ne tire pas)
TOURELLE = True                   # une tourelle apparaît dessus quand on la pose (voir tourelles.py)
TITRE = "Canon électromagnétique"  # titre de son panneau (ses munitions)

# le haut qui tourne (la tuile, elle, est le socle)
IMAGE_HAUT = RACINE / "image" / "image" / "tourelle_electromagnetique.png"
ROTATION_IMAGE = -90              # le canon de l'image pointe vers le haut : un quart de tour vers la droite
TAILLE_IMAGE_HAUT = 200           # côté de l'image du haut à l'écran (pixels monde)
PIVOT_HAUT = (217 / 600, 300 / 600)  # centre du corps carré dans l'image tournée (canon à droite)
PORTEE_CANON = 120                # distance du centre au bout du canon : là d'où part le rayon (suit la taille)

# tir
MUNITION = BALLE_PERFORMANTE      # ce qu'on charge dedans
PORTEE = 2000                     # pixels monde (et longueur du rayon)
CADENCE = 2.0                     # secondes entre deux tirs
ROTATION = 120                    # degrés par seconde (plus lourd : tourne moins vite)
VITESSE_TIR = 0                   # (rayon : instantané)
DEGATS = 15                       # HP retirés à chaque ennemi touché (un alien en a 5, un vaisseau 25)
TIRS_PAR_MUNITION = 10            # tirs que donne une balle performante chargée dedans
STOCK_MAX = 200                   # tirs qu'il peut garder en réserve (20 balles)
TIR = "rayon"
COULEUR_TIR = (90, 200, 255)

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 34),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
