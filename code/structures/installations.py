import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from joueur.energy import Energy
from monde.plantes import Plantes
from structures.coffres import Coffres
from structures.robot import Robots
from structures.tourelles import Tourelles

# =============================================
# ==== Installations : ce qui est construit sur une carte (conteneurs, plantes, robots, tourelles) et son
# ==== énergie. L'espace a les siennes ; chaque planète où l'on construit a les siennes, à part : ses cases
# ==== ne sont pas celles de l'espace, et ses panneaux solaires n'alimentent que ce qui est posé sur elle.
# =============================================


class Installations:
    def __init__(self, carte, coffres=None, plantes=None, robots=None, tourelles=None, energie=None):
        """Sans les objets donnés (ceux de l'espace, déjà créés), elles sont créées vides."""
        self.carte = carte
        self.coffres = Coffres() if coffres is None else coffres
        self.plantes = Plantes() if plantes is None else plantes
        self.robots = Robots() if robots is None else robots
        self.tourelles = Tourelles() if tourelles is None else tourelles
        self.energie = Energy() if energie is None else energie


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
