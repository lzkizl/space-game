import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import HYDROGENE, OXYGENE
from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Réacteur : une seule tuile (gid 21 du tileset), dans le vide juste sous le
# ==== bord bas d'une base. Comme le coffre (voir coffre.py et coffres.py) mais avec
# ==== 2 cases : de l'oxygène et de l'hydrogène. Avec les deux dedans, il pousse toute la
# ==== base vers le haut (voir structures/propulsion.py)
# =============================================
ICONE = RACINE / "image" / "image" / "reacteur.png"  # image dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque de la base (voir SOUS_FONDATION)
SOUS_FONDATION = True             # pas sur la base : dans le vide, juste sous son bord bas
COFFRE = True                     # un clic dessus ouvre son inventaire
TITRE = "Réacteur"                # titre de son inventaire
NB_CASES = 2                      # case 0 : oxygène ; case 1 : hydrogène
CASE_OBJET = {OXYGENE: 0, HYDROGENE: 1}   # objet accepté -> sa case (rien d'autre n'entre)
UNITES_PAR_OBJET = 100            # poussée que donne une paire (1 oxygène + 1 hydrogène)
COUT_PAS = 5                      # poussée dépensée par tuile de déplacement de la base
DELAI_PAS = 0.4                   # secondes entre deux tuiles (voir structures/propulsion.py)

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 21),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
