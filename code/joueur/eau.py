import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import COULEUR_JAUGE_EAU, EAU_CONSO_HERO, EAU_MAX, EAU_POS
from interface.ui import dessiner_jauge


class Eau:
    """Réserve d'eau du héros : elle baisse en continu (EAU_CONSO_HERO par seconde)
    et remonte quand il boit une bouteille d'eau."""

    def __init__(self):
        self.value = EAU_MAX
        self.police = pygame.font.Font(None, 36)

    def update(self, dt):
        self.value = max(0, self.value - EAU_CONSO_HERO * dt)

    def boire(self, quantite):
        self.value = min(EAU_MAX, self.value + quantite)

    @property
    def vide(self):
        return self.value <= 0

    def draw(self, screen):
        dessiner_jauge(screen, self.police, EAU_POS, "Eau", self.value, EAU_MAX,
                       COULEUR_JAUGE_EAU)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
