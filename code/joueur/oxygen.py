import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import (COULEUR_JAUGE_OXYGENE, OXYGENE_CONSO_HERO, OXYGENE_MAX, OXYGENE_PERTE,
                      OXYGENE_POS)
from interface.ui import dessiner_jauge


class Oxygen:
    """Réserve d'oxygène du héros : il en consomme OXYGENE_CONSO_HERO par seconde,
    en perd au contact d'une tuile solide, et les oxygénateurs lui en rendent."""

    def __init__(self):
        self.value = OXYGENE_MAX
        self.police = pygame.font.Font(None, 36)

    def update(self, dt, game_map, hero, energie):
        self.value -= OXYGENE_CONSO_HERO * dt

        if game_map.collides(hero.hitbox(hero.x, hero.y).inflate(2, 2)):
            self.value -= OXYGENE_PERTE

        self.value = min(self.value, OXYGENE_MAX)

    def recevoir(self, quantite):
        """Oxygène rendu par un oxygénateur."""
        self.value = min(self.value + quantite, OXYGENE_MAX)

    @property
    def vide(self):
        return self.value <= 0

    def draw(self, screen):
        dessiner_jauge(screen, self.police, OXYGENE_POS, "Oxygène", self.value, OXYGENE_MAX,
                       COULEUR_JAUGE_OXYGENE)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
