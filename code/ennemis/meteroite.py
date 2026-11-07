import math
import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import (ASTEROIDE_CHANCE, ASTEROIDE_IMAGE, ASTEROIDE_TAILLE, ASTEROIDE_VITESSE,
                      METEORITE_DELAI, METEORITE_IMAGE, METEORITE_MARGE, METEORITE_MAX,
                      METEORITE_TAILLE, METEORITE_VITESSE, SHARD_CHANCE, SHARD_IMAGE, SHARD_TAILLE,
                      SHARD_VITESSE, URANIUM_CHANCE, URANIUM_IMAGE, URANIUM_TAILLE, URANIUM_VITESSE)


class Meteorite:
    """Une météorite (ou un astéroïde de soufre) : elle traverse la vue en ligne droite
    en tournant sur elle-même. Les robots peuvent la ramasser. Position en pixels monde."""

    def __init__(self, image, x, y, vx, vy, type="meteorite", grosseur=0):
        self.image = image
        self.type = type  # "meteorite", "soufre", "shard" ou "uranium" (butin différent)
        self.grosseur = grosseur    # 0 (le plus petit) à 1 (le plus gros) : plus il est gros, plus le butin est grand
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.angle = random.uniform(0, 360)
        self.rotation = random.uniform(-90, 90)  # degrés par seconde
        self.age = 0
        self._pas_rotation = None
        self._image_tournee = image

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle += self.rotation * dt
        self.age += dt

    def draw(self, surface, camera_offset):
        # on ne refait la rotation que si l'angle a changé d'au moins 1 degré (invisible,
        # mais évite de tourner l'image plusieurs fois pour rien quand elle tourne lentement)
        pas = round(self.angle)
        if pas != self._pas_rotation:
            self._pas_rotation = pas
            self._image_tournee = pygame.transform.rotate(self.image, pas)
        image = self._image_tournee
        rect = image.get_rect(center=(self.x - camera_offset[0], self.y - camera_offset[1]))
        surface.blit(image, rect)


class Meteorites:
    """Fait apparaître des météorites au bord de la vue de la caméra, à intervalle
    aléatoire, et les retire quand elles sont sorties."""

    def __init__(self):
        self.image = pygame.image.load(METEORITE_IMAGE).convert_alpha()
        self.image_asteroide = pygame.image.load(ASTEROIDE_IMAGE).convert_alpha()
        self.image_shard = pygame.image.load(SHARD_IMAGE).convert_alpha()
        self.image_uranium = pygame.image.load(URANIUM_IMAGE).convert_alpha()
        self.liste = []
        self.chrono = random.uniform(*METEORITE_DELAI)

    def _creer(self, camera):
        largeur, hauteur = camera.screen_width, camera.screen_height

        # point d'apparition : juste en dehors d'un des 4 bords de la vue
        bord = random.choice(("haut", "bas", "gauche", "droite"))
        if bord == "haut":
            x, y = camera.x + random.uniform(0, largeur), camera.y - METEORITE_MARGE
        elif bord == "bas":
            x, y = camera.x + random.uniform(0, largeur), camera.y + hauteur + METEORITE_MARGE
        elif bord == "gauche":
            x, y = camera.x - METEORITE_MARGE, camera.y + random.uniform(0, hauteur)
        else:
            x, y = camera.x + largeur + METEORITE_MARGE, camera.y + random.uniform(0, hauteur)

        # direction : vers un point au hasard dans la vue
        cible_x = camera.x + random.uniform(0.2, 0.8) * largeur
        cible_y = camera.y + random.uniform(0.2, 0.8) * hauteur
        angle = math.atan2(cible_y - y, cible_x - x)
        tirage = random.random()
        if tirage < SHARD_CHANCE:
            type = "shard"
        elif tirage < SHARD_CHANCE + ASTEROIDE_CHANCE:
            type = "soufre"
        elif tirage < SHARD_CHANCE + ASTEROIDE_CHANCE + URANIUM_CHANCE:
            type = "uranium"
        else:
            type = "meteorite"
        source, (vmin, vmax), (mini, maxi) = {
            "shard": (self.image_shard, SHARD_VITESSE, SHARD_TAILLE),
            "uranium": (self.image_uranium, URANIUM_VITESSE, URANIUM_TAILLE),
            "soufre": (self.image_asteroide, ASTEROIDE_VITESSE, ASTEROIDE_TAILLE),
            "meteorite": (self.image, METEORITE_VITESSE, METEORITE_TAILLE),
        }[type]
        vitesse = random.uniform(vmin, vmax)

        facteur = random.uniform(mini, maxi)
        grosseur = (facteur - mini) / (maxi - mini)
        largeur_image = int(source.get_width() * facteur)
        hauteur_image = int(source.get_height() * facteur)
        image = pygame.transform.smoothscale(source, (largeur_image, hauteur_image))
        self.liste.append(Meteorite(image, x, y, math.cos(angle) * vitesse,
                                    math.sin(angle) * vitesse, type, grosseur))

    def update(self, dt, joueurs):
        if not joueurs:
            return  # personne sur cette carte
        self.chrono -= dt
        if self.chrono <= 0 and len(self.liste) < METEORITE_MAX:
            self._creer(random.choice(joueurs).camera)  # elle traverse la vue d'un des joueurs
            self.chrono = random.uniform(*METEORITE_DELAI)

        zones = []
        for joueur in joueurs:
            camera = joueur.camera
            zone = pygame.Rect(camera.x, camera.y, camera.screen_width, camera.screen_height)
            zones.append(zone.inflate(2 * (METEORITE_MARGE + 100), 2 * (METEORITE_MARGE + 100)))
        for meteorite in self.liste:
            meteorite.update(dt)
        # on retire celles qui sont (ou sont restées) loin de la vue de tous les joueurs
        self.liste = [m for m in self.liste if any(z.collidepoint(m.x, m.y) for z in zones)]

    def draw(self, surface, camera_offset):
        for meteorite in self.liste:
            meteorite.draw(surface, camera_offset)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
