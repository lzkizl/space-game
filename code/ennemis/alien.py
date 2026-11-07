import math
import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from joueur.joueur import plus_proche
from systeme.settings import (ALIEN_DEGATS, ALIEN_DELAI, ALIEN_HP, ALIEN_IMAGE, ALIEN_MARGE, ALIEN_MAX,
                      ALIEN_TAILLE, ALIEN_TROUPE, ALIEN_VITESSE)


class Alien:
    """Un alien : il fonce sur le héros le plus proche et, dès qu'il le touche, lui fait perdre
    de la vie. Position en pixels monde."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.hp = ALIEN_HP

    def subir(self, degats):
        self.hp -= degats

    @property
    def mort(self):
        return self.hp <= 0

    def update(self, dt, joueurs):
        proie = plus_proche(joueurs, self.x, self.y)
        if proie is None:
            return  # plus personne à poursuivre sur cette carte
        hero = proie.hero
        cible = hero.hitbox(hero.x, hero.y)
        if pygame.Rect(self.x - ALIEN_TAILLE[0] // 2, self.y - ALIEN_TAILLE[1] // 2,
                       *ALIEN_TAILLE).colliderect(cible):
            proie.vie.subir(ALIEN_DEGATS * dt)  # au contact : il reste collé au héros et le mord
            return
        angle = math.atan2(cible.centery - self.y, cible.centerx - self.x)
        self.x += math.cos(angle) * ALIEN_VITESSE * dt
        self.y += math.sin(angle) * ALIEN_VITESSE * dt

    def draw(self, surface, image, camera_offset):
        rect = image.get_rect(center=(self.x - camera_offset[0], self.y - camera_offset[1]))
        surface.blit(image, rect)


class Aliens:
    """Fait apparaître des troupes d'aliens juste hors de la vue d'un joueur : taille de la troupe
    (ALIEN_TROUPE) et temps avant la suivante (ALIEN_DELAI) tirés au hasard à chaque attaque.
    En multijoueur, chaque troupe vise la vue d'un des joueurs présents, tiré au sort."""

    def __init__(self, premiere_attaque=None):
        image = pygame.image.load(ALIEN_IMAGE).convert_alpha()
        self.image = pygame.transform.smoothscale(image, ALIEN_TAILLE)
        self.liste = []
        # premiere_attaque : secondes avant la première attaque (réglage du monde) ; None = aléatoire
        self.chrono = random.uniform(*ALIEN_DELAI) if premiere_attaque is None else premiere_attaque

    def _creer(self, camera):
        largeur, hauteur = camera.screen_width, camera.screen_height
        bord = random.choice(("haut", "bas", "gauche", "droite"))
        if bord == "haut":
            x, y = camera.x + random.uniform(0, largeur), camera.y - ALIEN_MARGE
        elif bord == "bas":
            x, y = camera.x + random.uniform(0, largeur), camera.y + hauteur + ALIEN_MARGE
        elif bord == "gauche":
            x, y = camera.x - ALIEN_MARGE, camera.y + random.uniform(0, hauteur)
        else:
            x, y = camera.x + largeur + ALIEN_MARGE, camera.y + random.uniform(0, hauteur)
        for _ in range(random.randint(*ALIEN_TROUPE)):  # la troupe arrive groupée, au même endroit
            self.liste.append(Alien(x + random.uniform(-60, 60), y + random.uniform(-60, 60)))

    def update(self, dt, joueurs):
        if not joueurs:
            return  # personne sur cette carte : ni apparition, ni poursuite
        self.chrono -= dt
        if self.chrono <= 0 and len(self.liste) < ALIEN_MAX:
            self._creer(random.choice(joueurs).camera)  # la troupe surgit à côté d'un des joueurs
            self.chrono = random.uniform(*ALIEN_DELAI)
        for alien in self.liste:
            alien.update(dt, joueurs)

    def draw(self, surface, camera_offset):
        for alien in self.liste:
            alien.draw(surface, self.image, camera_offset)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
