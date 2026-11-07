import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import OXYGENE
from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Oxygénateur : une seule tuile (gid 28 du tileset), seulement sur la base. Un clic
# ==== dessus ouvre son inventaire (voir coffres.py) : on y met de l'oxygène (la case
# ==== n'accepte que ça), il le rend au héros tant que sa jauge n'est pas pleine.
# ==== Les plantes ne produisent plus d'oxygène : c'est lui seul qui en fournit.
# =============================================
ICONE = RACINE / "image" / "image" / "oxygenator.png"  # image dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
COFFRE = True                     # un clic dessus ouvre son inventaire
TITRE = "Oxygénateur"             # titre de son inventaire
NB_CASES = 1
ACCEPTE = (OXYGENE,)              # seuls objets qu'on peut y ranger
OXYGENE_PAR_SEC = 3               # oxygène rendu au héros par seconde (il en consomme 1)
UNITES_PAR_OBJET = 100            # oxygène (jauge du héros) que contient un objet Oxygène

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 28),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
