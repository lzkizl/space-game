import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# mêmes réglages de vol que le vaisseau (lus par structures/vaisseaux_joueur.py)
from construction.vaisseau_joueur import CONSO_PAR_SEC, PORTEE, TAILLE, UNITES_PAR_OBJET, VITESSE  # noqa: F401
from systeme.ressources import HYDROGENE, OXYGENE, SHARD
from systeme.settings import RACINE

# =============================================
# ==== Vaisseau téléporteur : un vaisseau du joueur (voir vaisseau_joueur.py) amélioré avec du
# ==== tungstène et des shards. Il vole pareil (hydrogène ET oxygène), et en plus, quand on le
# ==== pilote, F ouvre une petite carte : un clic sur une case découverte l'y téléporte, avec le
# ==== héros dedans. Chaque saut brûle des shards rangés dans sa 3e case (bouton « Carburant » de la
# ==== petite carte, ou clic droit sur le vaisseau).
# =============================================
ICONE = RACINE / "image" / "image" / "teleporter_robot.png"  # image dans l'inventaire et dans le monde
VAISSEAU_JOUEUR = True            # repère cette construction (posée par un clic, pas de tuile)
TELEPORTEUR = True                # peut se téléporter (voir VaisseauxJoueur.teleporter)
TITRE = "Vaisseau téléporteur"    # titre de son inventaire
NB_CASES = 3                      # case 0 : hydrogène ; case 1 : oxygène ; case 2 : shards
CASE_OBJET = {HYDROGENE: 0, OXYGENE: 1, SHARD: 2}   # objet accepté -> sa case (rien d'autre n'entre)
CASE_SHARD = 2
SHARDS_PAR_SAUT = 1               # shards brûlés par téléportation


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
