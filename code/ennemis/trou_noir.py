import math
import random

import pygame

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import (TROU_NOIR_IMAGE, TROU_NOIR_TAILLE, TROU_NOIR_VITESSE,
                      TROU_NOIR_RAYON_AVALEUR, TROU_NOIR_RAYON_GRAVITE,
                      TROU_NOIR_FORCE_GRAVITE, TROU_NOIR_DEGATS,
                      TROU_NOIR_ZONE_DANGER, TROU_NOIR_DELAI, TROU_NOIR_MARGE)

_HALO_COULEURS = [
    (255, 160, 20, 180),   # orange vif (proche)
    (255, 100, 0, 100),    # orange sombre
    (180, 50, 180, 50),    # violet
    (60, 20, 120, 20),     # indigo lointain
]
_NB_HALOS = len(_HALO_COULEURS)


def _creer_image(taille):
    """Surface SRCALPHA du trou noir : disque noir + halos concentriques + éclats de lumière déformée."""
    n = taille
    img = pygame.Surface((n, n), pygame.SRCALPHA)
    c = n // 2
    rayon = c - 4

    # halos
    for i, (r, g, b, a) in enumerate(_HALO_COULEURS):
        r_halo = rayon + 6 + i * 14
        epaisseur = max(2, 10 - i * 2)
        pygame.draw.circle(img, (r, g, b, a), (c, c), r_halo, epaisseur)

    # disque noir opaque (l'horizon des événements)
    pygame.draw.circle(img, (0, 0, 0, 255), (c, c), rayon)

    # lueur interne bleue-blanche (accrétion)
    for r_int in range(rayon, rayon - 8, -1):
        k = (rayon - r_int) / 8
        alpha = round(140 * k)
        pygame.draw.circle(img, (160, 100, 255, alpha), (c, c), r_int, 1)

    # éclats de lumière déformée (4 arcs lumineux)
    for i in range(4):
        angle = i * math.pi / 2
        for da in (-0.25, 0.25):
            ax = c + round(math.cos(angle + da) * (rayon + 4))
            ay = c + round(math.sin(angle + da) * (rayon + 4))
            bx = c + round(math.cos(angle + da) * (rayon + 20))
            by = c + round(math.sin(angle + da) * (rayon + 20))
            pygame.draw.line(img, (255, 180, 60, 120), (ax, ay), (bx, by), 2)

    return img


class TrouNoir:
    """Un trou noir : il dérive lentement dans l'espace, attire le héros et les météorites,
    et avale tout ce qui entre dans son horizon des événements."""

    def __init__(self, x, y, vx, vy, image):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.image = image
        self.angle = 0.0          # rotation lente du halo
        self._image_tournee = image
        self._pas_rotation = None

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle = (self.angle + 6 * dt) % 360   # le halo tourne doucement

    def attirer(self, dt, joueurs):
        """Applique la gravité sur chaque joueur à portée : les attire, leur fait des dégâts s'ils
        sont trop proches (un trou noir n'a pas de cible préférée : il tire sur tout le monde)."""
        for joueur in joueurs:
            hero = joueur.hero
            dx = self.x - hero.x
            dy = self.y - hero.y
            dist = math.hypot(dx, dy) or 1.0
            if dist > TROU_NOIR_RAYON_GRAVITE:
                continue
            force = TROU_NOIR_FORCE_GRAVITE * (TROU_NOIR_RAYON_GRAVITE / max(dist, 50)) ** 1.5
            hero.x += (dx / dist) * force * dt
            hero.y += (dy / dist) * force * dt
            if dist < TROU_NOIR_ZONE_DANGER:
                intensite = 1.0 - dist / TROU_NOIR_ZONE_DANGER
                joueur.vie.subir(TROU_NOIR_DEGATS * intensite * dt)

    def avale_meteorites(self, meteorites):
        """Retire les météorites entrées dans l'horizon des événements."""
        survivantes = []
        for m in meteorites:
            dist = math.hypot(m.x - self.x, m.y - self.y)
            if dist > TROU_NOIR_RAYON_AVALEUR:
                survivantes.append(m)
        meteorites[:] = survivantes

    def draw(self, surface, camera_offset):
        pas = round(self.angle)
        if pas != self._pas_rotation:
            self._pas_rotation = pas
            self._image_tournee = pygame.transform.rotate(self.image, pas)
        img = self._image_tournee
        rect = img.get_rect(center=(self.x - camera_offset[0], self.y - camera_offset[1]))
        surface.blit(img, rect)


class TrousNoirs:
    """Gère l'apparition et la vie du trou noir africain dans l'espace."""

    def __init__(self):
        self._image_source = None
        self.liste = []
        self.chrono = random.uniform(*TROU_NOIR_DELAI)

    def image(self):
        """L'image d'un trou noir, construite une seule fois (elle sert à tous)."""
        if self._image_source is None:
            src = pygame.image.load(str(TROU_NOIR_IMAGE)).convert_alpha()
            self._image_source = pygame.transform.smoothscale(src, (TROU_NOIR_TAILLE, TROU_NOIR_TAILLE))
        return self._image_source

    def _creer(self, camera):
        largeur, hauteur = camera.screen_width, camera.screen_height
        bord = random.choice(("haut", "bas", "gauche", "droite"))
        if bord == "haut":
            x, y = camera.x + random.uniform(0, largeur), camera.y - TROU_NOIR_MARGE
        elif bord == "bas":
            x, y = camera.x + random.uniform(0, largeur), camera.y + hauteur + TROU_NOIR_MARGE
        elif bord == "gauche":
            x, y = camera.x - TROU_NOIR_MARGE, camera.y + random.uniform(0, hauteur)
        else:
            x, y = camera.x + largeur + TROU_NOIR_MARGE, camera.y + random.uniform(0, hauteur)
        # direction : traverse l'espace en diagonale (pas forcément vers le héros)
        angle = math.atan2(
            camera.y + hauteur / 2 - y + random.uniform(-hauteur * 0.4, hauteur * 0.4),
            camera.x + largeur / 2 - x + random.uniform(-largeur * 0.4, largeur * 0.4),
        )
        v = TROU_NOIR_VITESSE
        self.liste.append(TrouNoir(x, y, math.cos(angle) * v, math.sin(angle) * v, self.image()))

    def update(self, dt, joueurs, meteorites):
        if not joueurs:
            return  # personne sur cette carte
        self.chrono -= dt
        if self.chrono <= 0 and not self.liste:
            self._creer(random.choice(joueurs).camera)  # il dérive depuis le bord de la vue d'un joueur
            self.chrono = random.uniform(*TROU_NOIR_DELAI)

        # il reste tant qu'il est près d'au moins un joueur (sinon il serait oublié dès qu'on
        # s'éloigne, alors qu'un autre joueur le voit peut-être encore)
        zones = []
        for joueur in joueurs:
            camera = joueur.camera
            zone = pygame.Rect(camera.x, camera.y, camera.screen_width, camera.screen_height)
            zones.append(zone.inflate(2 * (TROU_NOIR_MARGE + 200), 2 * (TROU_NOIR_MARGE + 200)))

        for tn in self.liste:
            tn.update(dt)
            tn.attirer(dt, joueurs)
            tn.avale_meteorites(meteorites.liste)

        self.liste = [tn for tn in self.liste if any(z.collidepoint(tn.x, tn.y) for z in zones)]

    def draw(self, surface, camera_offset):
        for tn in self.liste:
            tn.draw(surface, camera_offset)
