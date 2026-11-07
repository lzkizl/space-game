import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme import son
from systeme.settings import COULEUR_JAUGE_VIE, VIE_MAX, VIE_POS
from interface.ui import dessiner_jauge


class Vie:
    """Points de vie (HP) du héros : les aliens les font baisser au contact, un kit médical
    les remonte. À 0, le héros est mort."""

    def __init__(self):
        self.value = VIE_MAX
        self.police = pygame.font.Font(None, 36)

    def subir(self, degats):
        if degats > 0 and self.value > 0:
            son.degat()
        self.value = max(0, self.value - degats)

    def soigner(self, points):
        self.value = min(VIE_MAX, self.value + points)

    @property
    def vide(self):
        return self.value <= 0

    def draw(self, screen):
        dessiner_jauge(screen, self.police, VIE_POS, "Vie", self.value, VIE_MAX,
                       COULEUR_JAUGE_VIE, alerte=0.3)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
