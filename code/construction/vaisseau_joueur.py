import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import HYDROGENE, OXYGENE
from systeme.settings import RACINE

# =============================================
# ==== Vaisseau du joueur : pas de tuile, c'est un engin posé dans le monde (voir
# ==== structures/vaisseaux_joueur.py). Clic gauche dessus : on monte et on vole au-dessus
# ==== du vide (ZQSD) ; E : descendre ; F ou clic droit : son inventaire (le carburant).
# ==== Il roule à l'hydrogène ET à l'oxygène (un objet de chaque dans ses 2 cases).
# ==== L'outil de déconstruction le remet dans l'inventaire (une fois son carburant repris).
# =============================================
ICONE = RACINE / "image" / "image" / "vaisseau_joueur.png"  # image dans l'inventaire et dans le monde
VAISSEAU_JOUEUR = True            # repère cette construction (posée par un clic, pas de tuile)
TITRE = "Vaisseau"                # titre de son inventaire
NB_CASES = 2                      # case 0 : hydrogène ; case 1 : oxygène
CASE_OBJET = {HYDROGENE: 0, OXYGENE: 1}   # objet accepté -> sa case (rien d'autre n'entre)
VITESSE = 700                     # pixels monde par seconde
UNITES_PAR_OBJET = 100            # carburant que donne un objet
CONSO_PAR_SEC = 5                 # carburant (de chaque sorte) brûlé par seconde de vol
TAILLE = 128                      # taille à l'écran (pixels monde)
PORTEE = 450                      # distance max du héros pour poser / monter dedans


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
