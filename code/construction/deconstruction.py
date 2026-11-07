import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import RACINE

# =============================================
# ==== Outil de déconstruction : un clic enlève la structure visée
# =============================================
ICONE = RACINE / "image" / "image" / "decontruction.png"  # image affichée dans l'inventaire
OUTIL = True  # outil : il n'a pas de tuiles à poser (voir building.py)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
