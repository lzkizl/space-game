import math
import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from joueur.joueur import plus_proche
from structures.building import base_proche, bloc_base
from systeme.settings import (CALQUE_BASE, VAISSEAU_BALLE_DEGATS, VAISSEAU_BALLE_VITESSE, VAISSEAU_CADENCE,
                      VAISSEAU_CHANCE_BASE, VAISSEAU_COUPS_BASE, VAISSEAU_DELAI, VAISSEAU_DISTANCE,
                      VAISSEAU_HP, VAISSEAU_MARGE, VAISSEAU_MAX, VAISSEAU_IMAGE,
                      VAISSEAU_PORTEE_BASE, VAISSEAU_TAILLE, VAISSEAU_VITESSE, VIDE_GIDS)

COULEUR_BALLE = (255, 80, 80)
RAYON_BALLE = 7
RAYON_TOUCHE_BALLE = 30   # distance du centre du héros à laquelle un tir l'atteint
PORTEE_BALLE = 1500       # distance max d'un tir, en pixels monde


class Tir:
    """Un tir de vaisseau : file droit. Il fait mal au héros s'il le touche ; un tir visant une
    fondation (`bloc` = (origine, cases)) ne touche que celle-ci, à l'endroit où il arrive."""

    def __init__(self, x, y, angle, bloc=None, distance=PORTEE_BALLE):
        self.x, self.y = x, y
        self.vx = math.cos(angle) * VAISSEAU_BALLE_VITESSE
        self.vy = math.sin(angle) * VAISSEAU_BALLE_VITESSE
        self.reste = distance
        self.bloc = bloc


class Vaisseau:
    """Un vaisseau ennemi : il vole jusqu'au héros, tourne autour de lui à distance et lui
    tire dessus. Les tourelles peuvent le détruire (même interface que Alien : x, y, subir, mort)."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = VAISSEAU_HP
        self.angle = 0.0                       # radians (0 = droite) : il regarde le héros
        self.sens = random.choice((-1, 1))     # il tourne autour du héros dans ce sens
        self.chrono = random.uniform(0.5, VAISSEAU_CADENCE)
        self.base_visee = None                 # (origine, cases, centre) de la fondation qu'il vise, sinon le héros

    def subir(self, degats):
        self.hp -= degats

    @property
    def mort(self):
        return self.hp <= 0

    def _choisir_objectif(self, game_map):
        """Après chaque tir : une fondation proche (au hasard) ou le héros."""
        self.base_visee = None
        if random.random() >= VAISSEAU_CHANCE_BASE:
            return
        case = base_proche(game_map, self.x, self.y, VAISSEAU_PORTEE_BASE)
        if case is not None:
            cases, origine = bloc_base(game_map, *case)
            centre = (sum(x + 0.5 for x, _ in cases) / len(cases) * game_map.tilewidth,
                      sum(y + 0.5 for _, y in cases) / len(cases) * game_map.tileheight)
            self.base_visee = (origine, cases, centre)

    def update(self, dt, joueurs, tirs, game_map):
        proie = plus_proche(joueurs, self.x, self.y)
        if proie is None:
            return  # plus personne sur cette carte
        hero = proie.hero
        cible = hero.hitbox(hero.x, hero.y).center
        dx, dy = cible[0] - self.x, cible[1] - self.y
        distance = math.hypot(dx, dy) or 1.0
        if self.base_visee is not None and game_map.get_layer_gid(
                CALQUE_BASE, *self.base_visee[1][0]) in VIDE_GIDS:
            self.base_visee = None             # la fondation visée n'existe plus
        ux, uy = dx / distance, dy / distance                  # vers le héros
        radial = max(-1.0, min(1.0, (distance - VAISSEAU_DISTANCE) / VAISSEAU_DISTANCE))
        # approche (ou recule) pour garder sa distance, tout en tournant autour du héros
        vx = ux * radial - uy * self.sens * 0.6
        vy = uy * radial + ux * self.sens * 0.6
        norme = math.hypot(vx, vy) or 1.0
        self.x += vx / norme * VAISSEAU_VITESSE * dt
        self.y += vy / norme * VAISSEAU_VITESSE * dt

        objectif = self.base_visee[2] if self.base_visee is not None else cible
        voulu = math.atan2(objectif[1] - self.y, objectif[0] - self.x)
        ecart = (voulu - self.angle + math.pi) % (2 * math.pi) - math.pi
        pas = 4 * dt
        self.angle += max(-pas, min(pas, ecart))

        self.chrono -= dt
        portee = VAISSEAU_PORTEE_BASE if self.base_visee is not None else VAISSEAU_DISTANCE * 2
        if (self.chrono <= 0 and abs(ecart) < math.radians(15)
                and math.hypot(objectif[0] - self.x, objectif[1] - self.y) < portee):
            self.chrono = VAISSEAU_CADENCE
            bout = (self.x + math.cos(self.angle) * VAISSEAU_TAILLE * 0.5,
                    self.y + math.sin(self.angle) * VAISSEAU_TAILLE * 0.5)
            if self.base_visee is not None:
                origine, cases, centre = self.base_visee
                angle = math.atan2(centre[1] - bout[1], centre[0] - bout[0])
                tirs.append(Tir(*bout, angle, (origine, cases), math.hypot(centre[0] - bout[0], centre[1] - bout[1])))
            else:
                tirs.append(Tir(*bout, self.angle))
            self._choisir_objectif(game_map)


def _image():
    """image/image/vaisseau.png (le nez pointe vers le haut), rognée puis réduite : sa plus
    grande dimension fait VAISSEAU_TAILLE pixels."""
    image = pygame.image.load(VAISSEAU_IMAGE).convert_alpha()
    image = image.subsurface(image.get_bounding_rect()).copy()
    echelle = VAISSEAU_TAILLE / max(image.get_size())
    return pygame.transform.smoothscale(
        image, (round(image.get_width() * echelle), round(image.get_height() * echelle)))


def _touche(joueurs, tir):
    """Le joueur atteint par cette balle, ou None (en solo il n'y a qu'un candidat)."""
    for joueur in joueurs:
        hero = joueur.hero
        cible = hero.hitbox(hero.x, hero.y).center
        if math.hypot(cible[0] - tir.x, cible[1] - tir.y) <= RAYON_TOUCHE_BALLE:
            return joueur
    return None


class Vaisseaux:
    """Fait apparaître, rarement, un vaisseau ennemi hors de la vue d'un joueur (délai tiré au
    hasard). En multijoueur il surgit près de l'un d'eux et poursuit le plus proche."""

    def __init__(self, premiere_attaque=None):
        self.image = _image()
        self.liste = []
        self.tirs = []
        self.coups = {}   # origine d'une fondation -> nombre de tirs reçus
        # premiere_attaque : secondes avant le premier vaisseau (réglage du monde) ; None = aléatoire
        self.chrono = random.uniform(*VAISSEAU_DELAI) if premiere_attaque is None else premiere_attaque

    def vider(self):
        self.liste.clear()
        self.tirs.clear()

    def _creer(self, camera):
        largeur, hauteur = camera.screen_width, camera.screen_height
        bord = random.choice(("haut", "bas", "gauche", "droite"))
        if bord == "haut":
            x, y = camera.x + random.uniform(0, largeur), camera.y - VAISSEAU_MARGE
        elif bord == "bas":
            x, y = camera.x + random.uniform(0, largeur), camera.y + hauteur + VAISSEAU_MARGE
        elif bord == "gauche":
            x, y = camera.x - VAISSEAU_MARGE, camera.y + random.uniform(0, hauteur)
        else:
            x, y = camera.x + largeur + VAISSEAU_MARGE, camera.y + random.uniform(0, hauteur)
        self.liste.append(Vaisseau(x, y))

    def update(self, dt, joueurs, game_map):
        """Renvoie la liste des fondations détruites ce coup-ci (chacune : la liste de ses cases)."""
        if not joueurs:
            return []  # personne sur cette carte : ni apparition, ni attaque
        self.chrono -= dt
        if self.chrono <= 0 and len(self.liste) < VAISSEAU_MAX:
            self._creer(random.choice(joueurs).camera)  # il surgit à côté d'un des joueurs
            self.chrono = random.uniform(*VAISSEAU_DELAI)
        for vaisseau in self.liste:
            vaisseau.update(dt, joueurs, self.tirs, game_map)

        detruites = []
        restants = []
        for tir in self.tirs:
            tir.x += tir.vx * dt
            tir.y += tir.vy * dt
            tir.reste -= VAISSEAU_BALLE_VITESSE * dt
            if tir.bloc is not None:
                if tir.reste > 0:
                    restants.append(tir)
                    continue
                origine, cases = tir.bloc          # le tir arrive sur la fondation
                if game_map.get_layer_gid(CALQUE_BASE, *cases[0]) in VIDE_GIDS:
                    continue                       # déjà détruite par un autre tir
                self.coups[origine] = self.coups.get(origine, 0) + 1
                if self.coups[origine] >= VAISSEAU_COUPS_BASE:
                    del self.coups[origine]
                    detruites.append(cases)
            elif (touche := _touche(joueurs, tir)) is not None:
                touche.vie.subir(VAISSEAU_BALLE_DEGATS)  # la balle atteint un joueur, quel qu'il soit
            elif tir.reste > 0:
                restants.append(tir)
        self.tirs = restants
        return detruites

    def draw(self, surface, camera_offset):
        for vaisseau in self.liste:
            image = pygame.transform.rotate(self.image, -math.degrees(vaisseau.angle + math.pi / 2))
            centre = (vaisseau.x - camera_offset[0], vaisseau.y - camera_offset[1])
            surface.blit(image, image.get_rect(center=centre))
        for tir in self.tirs:
            pygame.draw.circle(surface, COULEUR_BALLE,
                               (round(tir.x - camera_offset[0]), round(tir.y - camera_offset[1])), RAYON_BALLE)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
