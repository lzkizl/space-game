import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Tourelle plasma : une tourelle (même fonctionnement, voir tourelles.py) à portée infinie :
# ==== elle vise l'ennemi le plus proche, où qu'il soit, et garde un laser plasma braqué sur lui
# ==== qui lui retire 1 HP toutes les 0,25 s. Pas de munitions : elle ne marche qu'à l'énergie.
# ==== Une seule tuile (gid 36 du tileset : le socle), seulement sur la base.
# =============================================
ICONE = RACINE / "image" / "image" / "tourelle_plasma_icone.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
CONSOMMATION = 400                # watts consommés (sans énergie le laser s'éteint)
TOURELLE = True                   # une tourelle apparaît dessus quand on la pose (voir tourelles.py)
TITRE = "Tourelle plasma"

# le haut qui tourne (la tuile, elle, est le socle)
IMAGE_HAUT = RACINE / "image" / "image" / "tourelle_plasma.png"
ROTATION_IMAGE = -90              # le canon de l'image pointe vers le haut : un quart de tour vers la droite
TAILLE_IMAGE_HAUT = 330           # côté de l'image du haut à l'écran (pixels monde)
PIVOT_HAUT = (272 / 512, 256 / 512)  # centre du corps dans l'image tournée (canon à droite)
PORTEE_CANON = 155                # distance du centre au bout du canon : là d'où part le laser

# tir
MUNITION = None                   # rien à charger : elle ne consomme que de l'énergie
PORTEE = float("inf")             # portée infinie
CADENCE = 0.25                    # secondes entre deux pertes de HP de la cible
ROTATION = 360                    # degrés par seconde
VITESSE_TIR = 0                   # (laser : instantané)
DEGATS = 1                        # HP retirés à chaque fois
TIRS_PAR_MUNITION = 1             # (pas de munitions)
STOCK_MAX = 0
TIR = "laser"                     # un laser continu braqué sur la cible (voir tourelles.py)
COULEUR_TIR = (60, 255, 220)

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 36),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
