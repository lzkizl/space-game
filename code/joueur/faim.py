import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import COULEUR_JAUGE_FAIM, FAIM_CONSO_HERO, FAIM_MAX, FAIM_POS
from interface.ui import dessiner_jauge


class Faim:
    """Jauge de nourriture du héros : elle baisse en continu (FAIM_CONSO_HERO par
    seconde) et remonte quand il mange (une baie, par exemple). Vide, c'est perdu."""

    def __init__(self):
        self.value = FAIM_MAX
        self.police = pygame.font.Font(None, 36)

    def update(self, dt):
        self.value = max(0, self.value - FAIM_CONSO_HERO * dt)

    def manger(self, quantite):
        self.value = min(FAIM_MAX, self.value + quantite)

    @property
    def vide(self):
        return self.value <= 0

    def draw(self, screen):
        dessiner_jauge(screen, self.police, FAIM_POS, "Faim", self.value, FAIM_MAX,
                       COULEUR_JAUGE_FAIM)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
