import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import CLE_USB, CLE_USB_REACTEUR, CLE_USB_SATELLITE, PROCESSEUR, RAM
from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, RACINE

# =============================================
# ==== Boîtier : une seule tuile (gid 26 du tileset), seulement sur la base. Un clic dessus
# ==== ouvre son inventaire (voir coffres.py) : 3 cases, une pour 1 processeur, une pour
# ==== 1 RAM et une pour 1 clé USB (rien d'autre n'entre, un seul exemplaire par case).
# ==== Posé juste à côté d'une antenne avec une clé USB dedans, il traduit les bits en lettres
# ==== dans la radio (voir building.decodeur_a_cote et radio_menu.py).
# ==== Avec un processeur, une RAM et une clé USB satellite, il pilote le télescope réglé sur sa
# ==== fréquence : son panneau montre l'angle du télescope et le fait tourner.
# ==== Avec un processeur, une RAM et une clé USB réacteurs, il pilote les réacteurs de sa
# ==== plateforme : marche / arrêt et direction, depuis son panneau (voir coffres.PanneauCoffre
# ==== et structures/propulsion.py).
# =============================================
ICONE = RACINE / "image" / "image" / "pc_case.png"  # image affichée dans l'inventaire
CALQUE = CALQUE_PLANTES           # calque Tiled où la tuile est posée (sur_fonda)
SUPPORT = CALQUE_BASE             # calque où il doit déjà y avoir une tuile
COFFRE = True                     # un clic dessus ouvre son inventaire
TITRE = "Boîtier"                 # titre de son inventaire
NB_CASES = 3                      # case 0 : processeur ; case 1 : RAM ; case 2 : clé USB
CASE_OBJET = {PROCESSEUR: 0, RAM: 1, CLE_USB: 2, CLE_USB_REACTEUR: 2, CLE_USB_SATELLITE: 2}   # objet -> sa case
PILE_MAX = 1                      # un seul exemplaire par case
CASE_CLE_USB = 2                  # la clé USB : décode les signaux de l'antenne voisine, ou pilote les réacteurs
PILOTAGE = True                   # son panneau peut avoir les commandes des réacteurs (voir pilote_reacteurs)


def pilote_reacteurs(contenu):
    """True si le boîtier (son Coffre) peut piloter les réacteurs : processeur, RAM et clé USB réacteurs."""
    return contenu.objets == [PROCESSEUR, RAM, CLE_USB_REACTEUR]


def pilote_satellite(contenu):
    """True si le boîtier (son Coffre) peut piloter un télescope : processeur, RAM et clé USB satellite."""
    return contenu.objets == [PROCESSEUR, RAM, CLE_USB_SATELLITE]

# (décalage x, décalage y, numéro de tuile)
TUILES = [
    (0, 0, 26),
]


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
