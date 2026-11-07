import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import RACINE

# =============================================
# ==== Foreuse : pas de tuile, c'est une machine posée sur un gisement de minerai d'une planète (voir
# ==== structures/foreuses.py), comme dans Factorio : seulement sur un gisement (fer, cuivre sur la Terre,
# ==== carbure de tungstène sur Mars...). Clic gauche avec la foreuse sélectionnée : on la pose sur le
# ==== gisement visé ; clic dessus : son inventaire (ce qu'elle a extrait, on ne peut rien y ranger). Elle
# ==== extrait toute seule, même quand on n'est pas sur la planète : un morceau toutes les DELAI secondes,
# ==== jusqu'à ce que le gisement soit vide (ou son inventaire plein).
# ==== L'outil de déconstruction la remet dans l'inventaire (avec ce qu'elle contient).
# =============================================
ICONE = RACINE / "image" / "image" / "Foreuse_1.png"  # image dans l'inventaire et sur la planète
FOREUSE = True                    # repère cette construction (posée par un clic, pas de tuile)
TITRE = "Foreuse"                 # titre de son inventaire
NB_CASES = 6
CASES_SORTIE = range(NB_CASES)    # elle range ce qu'elle extrait dans toutes ses cases...
ACCEPTE = ()                      # ... et on ne peut rien y mettre (on ne fait que prendre)
PLANETES = ("terre.tmx", "mars.tmx")  # cartes où elle se pose (celles qui ont des gisements)
HAUTEUR = 230                     # hauteur de l'image sur la planète (pixels monde)
PIED = 0.84                       # hauteur des pieds dans l'image (part de sa hauteur, depuis le haut)
SOCLE = (150, 40)                 # rectangle au sol (largeur, hauteur) qui bloque le héros
PORTEE = 450                      # distance max du héros pour la poser
DELAI = 8                         # secondes pour extraire un morceau de minerai


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
