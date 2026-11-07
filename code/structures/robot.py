import math
import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import base_robot
from systeme.ressources import BUTIN_ASTEROIDE, BUTIN_METEORITE, BUTIN_SHARD, BUTIN_URANIUM, RESSOURCES
from systeme.settings import (ROBOT_DISTANCE_MAX, ROBOT_DISTANCE_PRISE, ROBOT_IMAGE,
                      ROBOT_RAYON_DETECTION, ROBOT_VITESSE, ROBOT_VITESSE_ROTATION)

GID_BASE_ROBOT = base_robot.TUILES[0][2]

# Multijoueur, côté client : les robots sont simulés par l'hôte, on ne fait que les suivre.
# Temps (en secondes) que met le robot à rejoindre la position annoncée. Assez long pour lisser
# les trous entre deux instantanés, assez court pour qu'il ne traîne pas derrière.
LISSAGE_RESEAU = 0.06
# Vitesse maximale pour rattraper son retard. Sans ce plafond, une nouvelle qui arrive en retard
# (ça arrive) serait rattrapée d'un seul bond bien visible ; là, le retard se résorbe en quelques
# images. Le double de sa vitesse normale : il rattrape vite sans jamais avoir l'air de sauter.
VITESSE_RATTRAPAGE = 2 * ROBOT_VITESSE
# Au-delà de cette distance, il n'a pas pu marcher jusque-là : il a été déplacé (base poussée par
# ses réacteurs, monde rechargé). On le pose directement au lieu de le faire glisser.
SAUT_RESEAU = ROBOT_VITESSE  # une seconde de trajet


class Robot:
    """Un robot posé sur sa base. Quand une météorite passe près de lui il va la
    chercher, la ramasse puis revient à sa base : le butin arrive alors dans son stock
    (une case par ressource). On ne peut rien y mettre, seulement y prendre."""

    titre = "Robot"
    cases = RESSOURCES  # les ressources de son inventaire (voir stockage.py)

    def __init__(self, tx, ty, image, tilewidth, tileheight):
        self.tx = tx
        self.ty = ty
        self.stock = {ressource: 0 for ressource in RESSOURCES}  # une case par ressource
        # centré sur la case de sa base (en pixels monde)
        self.rect = image.get_rect(center=((tx + 0.5) * tilewidth, (ty + 0.5) * tileheight))
        self.base = pygame.Vector2(self.rect.center)
        self.pos = pygame.Vector2(self.base)
        self.angle = -math.pi / 2  # radians (0 = droite, y vers le bas) : regarde en haut
        self.cible = None   # météorite qu'il poursuit
        self.butin = None   # {ressource: quantité} qu'il rapporte à la base
        # Multijoueur, côté client : là où l'hôte dit qu'il est (None tant qu'il n'a rien dit).
        # On ne l'y pose pas d'un coup, on l'y emmène image par image (voir suivre).
        self.but = None
        self.angle_but = self.angle

    # ---- multijoueur : côté client, on ne fait que suivre ce que l'hôte annonce ----
    def viser(self, x, y, angle):
        """Position et orientation annoncées par l'hôte."""
        self.but = pygame.Vector2(x, y)
        self.angle_but = angle

    def suivre(self, dt):
        """Rapproche le robot de la position annoncée, un peu à chaque image.

        C'est ce qui rend son déplacement fluide chez les autres joueurs : les nouvelles de
        l'hôte arrivent par paquets (et le contenu de son stock seulement 2 fois par seconde),
        alors que le jeu dessine 60 images par seconde. Le poser à chaque fois à l'endroit
        annoncé le ferait sauter d'un point à l'autre — il va à 600 pixels par seconde."""
        if self.but is None:
            return
        reste = self.but - self.pos
        distance = reste.length()
        part = min(1.0, dt / LISSAGE_RESEAU)
        if distance > SAUT_RESEAU:
            self.pos.update(self.but)  # il a été déplacé, pas déplacé tout seul : on le pose là
            self.angle = self.angle_but
        elif distance:
            # une part de l'écart à chaque image, sans jamais dépasser la vitesse de rattrapage
            pas = min(distance * part, VITESSE_RATTRAPAGE * dt)
            self.pos += reste * (pas / distance)
            # (le tour le plus court, comme _tourner_vers : de 350° à 10° on passe par 0)
            ecart = (self.angle_but - self.angle + math.pi) % (2 * math.pi) - math.pi
            self.angle += ecart * part
        self.rect.center = (round(self.pos.x), round(self.pos.y))

    def _tourner_vers(self, voulu, dt):
        """Pivote vers l'angle voulu (au plus ROBOT_VITESSE_ROTATION * dt), par le chemin le plus court."""
        ecart = (voulu - self.angle + math.pi) % (2 * math.pi) - math.pi
        pas = ROBOT_VITESSE_ROTATION * dt
        self.angle += max(-pas, min(pas, ecart))

    def _avancer_vers(self, point, dt):
        """Se rapproche du point (au plus ROBOT_VITESSE * dt). Renvoie la distance restante."""
        reste = point - self.pos
        distance = reste.length()
        pas = ROBOT_VITESSE * dt
        if distance > 1:
            self._tourner_vers(math.atan2(reste.y, reste.x), dt)
        if distance <= pas:
            self.pos.update(point)
            return 0
        self.pos += reste * (pas / distance)
        return distance - pas

    def update(self, dt, meteorites, ciblees):
        if self.cible is None and self.butin is None:
            self._choisir_cible(meteorites, ciblees)

        if self.cible is not None:
            position = pygame.Vector2(self.cible.x, self.cible.y)
            trop_loin = self.base.distance_to(position) > ROBOT_DISTANCE_MAX
            if self.cible not in meteorites.liste or trop_loin:
                self.cible = None  # perdue (sortie de la zone) : il rentre sans rien
            else:
                self._avancer_vers(position, dt)
                if self.pos.distance_to(position) <= ROBOT_DISTANCE_PRISE:
                    table = {"soufre": BUTIN_ASTEROIDE, "shard": BUTIN_SHARD,
                             "uranium": BUTIN_URANIUM}.get(self.cible.type, BUTIN_METEORITE)
                    # un astéroïde rapporte de 1x (le plus petit) à 3x (le plus gros) le butin de base
                    multiplicateur = 1 + 2 * self.cible.grosseur if self.cible.type != "meteorite" else 1
                    meteorites.liste.remove(self.cible)
                    self.cible = None
                    self.butin = {ressource: round(random.randint(mini, maxi) * multiplicateur)
                                  for ressource, (mini, maxi) in table.items()}
        elif self._avancer_vers(self.base, dt) == 0:
            if self.butin is not None:  # de retour à la base : il dépose le butin
                for ressource, quantite in self.butin.items():
                    self.stock[ressource] += quantite
                self.butin = None

        self.rect.center = (round(self.pos.x), round(self.pos.y))

    def _choisir_cible(self, meteorites, ciblees):
        """La météorite libre la plus proche de la base, dans le rayon de détection."""
        meilleure, distance_min = None, ROBOT_RAYON_DETECTION
        for meteorite in meteorites.liste:
            if meteorite in ciblees:
                continue
            distance = self.base.distance_to((meteorite.x, meteorite.y))
            if distance <= distance_min:
                meilleure, distance_min = meteorite, distance
        if meilleure is not None:
            self.cible = meilleure
            ciblees.add(meilleure)


class Robots:
    """Les robots du monde : apparition sur la base, déplacement, affichage. Leur
    inventaire s'ouvre par un clic gauche sur le robot (voir stockage.py)."""

    def __init__(self):
        self.image = pygame.image.load(ROBOT_IMAGE).convert_alpha()
        self.robots = {}   # (tx, ty) -> Robot

    # ---- apparition / disparition ----
    def ajouter(self, tx, ty, game_map):
        self.robots[(tx, ty)] = Robot(tx, ty, self.image, game_map.tilewidth, game_map.tileheight)

    def scan(self, game_map):
        """Un robot pour chaque base de robot dessinée dans la carte (comme avec la pose en jeu).
        Une base qui a déjà son robot (monde chargé d'une sauvegarde) n'est pas recréée."""
        taille = game_map.chunk_size
        for (cx, cy), grille in game_map.layers[base_robot.CALQUE].items():
            for y, ligne in enumerate(grille):
                for x, gid in enumerate(ligne):
                    if gid == GID_BASE_ROBOT:
                        tx, ty = cx * taille + x, cy * taille + y
                        if (tx, ty) not in self.robots:
                            self.ajouter(tx, ty, game_map)

    def deplacer(self, trajet, pixels):
        """La base a bougé : {ancienne case: nouvelle case} ; les robots suivent (déplacement en pixels)."""
        anciens = self.robots
        self.robots = {}
        for cle, robot in anciens.items():
            robot.tx, robot.ty = trajet.get(cle, cle)
            if cle in trajet:
                for point in (robot.base, robot.pos):
                    point += pixels
                robot.rect.center = (round(robot.pos.x), round(robot.pos.y))
            self.robots[(robot.tx, robot.ty)] = robot

    def retirer(self, tx, ty):
        """Renvoie le robot retiré (ou None)."""
        return self.robots.pop((tx, ty), None)

    # ---- récupération des météorites ----
    def update(self, dt, meteorites, energie):
        """Fait avancer les robots : chacun part chercher une météorite proche (que
        les autres robots n'ont pas déjà choisie). Sans assez d'énergie, ils s'arrêtent."""
        if not energie.suffisante:
            return
        ciblees = {robot.cible for robot in self.robots.values() if robot.cible is not None}
        for robot in self.robots.values():
            robot.update(dt, meteorites, ciblees)

    def suivre(self, dt):
        """Multijoueur, côté client : à appeler à chaque image à la place d'update (c'est l'hôte
        qui fait bouger les robots ; nous, on les rejoint en douceur). Voir Robot.suivre."""
        for robot in self.robots.values():
            robot.suivre(dt)

    # ---- souris / clavier ----
    def robot_sous_souris(self, pos_vue, camera):
        monde = (pos_vue[0] + camera.x, pos_vue[1] + camera.y)
        for robot in self.robots.values():
            if robot.rect.collidepoint(monde):
                return robot
        return None

    # ---- dessin ----
    def draw_monde(self, vue, camera_offset, propulsion=None):
        for robot in self.robots.values():
            image = pygame.transform.rotate(self.image, -math.degrees(robot.angle + math.pi / 2))
            # (propulsion : la base poussée qui glisse, ses robots glissent avec elle)
            offset = propulsion.offset_de(camera_offset, (robot.tx, robot.ty)) if propulsion else camera_offset
            centre = (robot.rect.centerx - offset[0], robot.rect.centery - offset[1])
            vue.blit(image, image.get_rect(center=centre))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
