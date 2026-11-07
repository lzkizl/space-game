import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structures.building import CONSTRUCTIONS, nombre_pose
from systeme.settings import COULEUR_ALERTE, COULEUR_TEXTE, ENERGIE_POS


class Energy:
    """Bilan d'énergie (en W), stable : la production et la consommation valent la
    somme des constructions posées. Un fichier de construction/ définit PUISSANCE
    (production, ex : 100 W par panneau) et/ou CONSOMMATION (ex : 50 W par plante)."""

    def __init__(self):
        self.production = 0
        self.consommation = 0
        self.police = pygame.font.Font(None, 36)

    def update(self, game_map, coffres=None):
        """`coffres` : les conteneurs du monde. Une construction qui brûle du carburant (DUREE_BARRE,
        ex : réacteur nucléaire) ne produit que si elle est alimentée."""
        self.production = 0
        for objet in CONSTRUCTIONS:
            if not hasattr(objet, "PUISSANCE"):
                continue
            if hasattr(objet, "DUREE_BARRE"):
                actifs = 0 if coffres is None else sum(
                    1 for c in coffres.coffres.values() if c.construction is objet and c.alimente)
                self.production += actifs * objet.PUISSANCE
            else:
                self.production += nombre_pose(game_map, objet) * objet.PUISSANCE
        self.consommation = sum(
            nombre_pose(game_map, objet) * objet.CONSOMMATION
            for objet in CONSTRUCTIONS if hasattr(objet, "CONSOMMATION")
        )

    @property
    def suffisante(self):
        """True si la production couvre la consommation (tout est alimenté)."""
        return self.production >= self.consommation

    def draw(self, screen):
        couleur = COULEUR_TEXTE if self.suffisante else COULEUR_ALERTE
        texte = self.police.render(
            f"Énergie: {self.production} W / {self.consommation} W", True, couleur)
        screen.blit(texte, ENERGIE_POS)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
