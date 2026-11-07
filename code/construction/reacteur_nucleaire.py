import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import BARRE_NUCLEAIRE
from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Réacteur nucléaire : un bloc de 2x2 tuiles (gids 30, 31, 39, 40 du tileset), seulement sur la base.
# ==== Un clic dessus ouvre son inventaire (voir coffres.py) : on y met des barres nucléaires
# ==== (la case n'accepte que ça). Tant qu'une barre brûle, il produit beaucoup d'énergie
# ==== (autant que 30 panneaux solaires) ; sans barre, il ne produit rien.
# ==== (À ne pas confondre avec le réacteur de reacteur.py, qui pousse les bases.)
# =============================================
ICONE = RACINE / "image" / "image" / "Réacteur_nuclear.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
COFFRE = True                     # un clic dessus ouvre son inventaire
TITRE = "Réacteur nucléaire"      # titre de son inventaire
NB_CASES = 1
ACCEPTE = (BARRE_NUCLEAIRE,)      # seuls objets qu'on peut y ranger
PUISSANCE = 3000                  # watts produits tant qu'une barre brûle (voir joueur/energy.py)
DUREE_BARRE = 300                 # secondes que dure une barre nucléaire

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 30),   # haut gauche (porte le conteneur, voir coffres.py)
    (1, 0, 31),   # haut droite
    (0, 1, 39),   # bas gauche
    (1, 1, 40),   # bas droite
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
