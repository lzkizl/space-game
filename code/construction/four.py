import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import GLACE, HYDROGENE, OXYGENE
from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Four : une seule tuile (gid 27 du tileset), seulement sur la base. Un clic dessus
# ==== ouvre son inventaire (voir coffres.py) : on met le minerai dans les cases d'entrée,
# ==== il le cuit tout seul (RECETTES) et range le résultat dans les cases de sortie.
# =============================================
ICONE = RACINE / "image" / "image" / "four.png"  # image dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
COFFRE = True                     # un clic dessus ouvre son inventaire
TITRE = "Four"                    # titre de son inventaire
NB_CASES = 3                      # case 0 : entrée ; cases 1 et 2 : sortie
CASES_ENTREE = (0,)
CASES_SORTIE = (1, 2)
DELAI = 5                         # secondes pour cuire un exemplaire (barre de progression)

# entrée -> [(résultat, quantité obtenue par exemplaire cuit), ...]
RECETTES = {
    GLACE: [(OXYGENE, 1), (HYDROGENE, 1)],
}

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 27),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
