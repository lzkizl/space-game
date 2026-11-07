import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_EPAVES, RACINE, TILESET_EPAVES

# =============================================
# ==== Navette échouée : dessinée dans la carte (calque CALQUE, tuiles de 5 x 5 cases), ou tirée
# ==== de la graine dans le monde généré (voir monde/generation.py), pas constructible. Un clic
# ==== dessus ouvre son butin (processeur, RAM ; très rarement des shards ou une clé USB), géré par
# ==== coffres.py (voir remplir_epave). Ce n'est pas dans
# ==== CONSTRUCTIONS : on ne peut ni la poser ni la fabriquer.
# =============================================
ICONE = RACINE / "image" / "image" / "vaisseau_cassé.png"
CALQUE = CALQUE_EPAVES            # calque Tiled où les navettes sont dessinées
TILESET = TILESET_EPAVES          # seules ses tuiles sont des navettes (pas les astéroïdes du même calque)
COFFRE = True                     # un clic dessus ouvre son inventaire
EPAVE = True                      # repère cette construction (créée par Coffres.scan, jamais posée)
TITRE = "Navette échouée"         # titre de son inventaire
NB_CASES = 5                      # taille de son inventaire

TUILES = []                       # rien à poser


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
