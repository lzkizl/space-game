import math
import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import vaisseau_joueur
from systeme import ecran
from interface.ui import dessiner_bouton
from monde.map import Map
from monde.planetes import PLANETES_GIDS
from systeme.settings import RACINE, SPAWN_PLANETE_RAYON

# =============================================
# ==== Orbite : quand le héros (ou son vaisseau) est au-dessus d'une planète, un bouton « Descendre
# ==== sur Mars » apparaît. On descend alors DANS la planète : le jeu passe sur sa carte (map/mars.tmx),
# ==== sans fond étoilé ni astéroïdes. Sur la planète, le bouton « Remonter en orbite » ramène là où
# ==== on était dans l'espace (dans son vaisseau si on le pilotait).
# ==== Avant de descendre, une animation : le héros, avec son vaisseau ou sa base, rétrécit (il
# ==== plonge vers la planète, loin en dessous), puis l'écran s'assombrit.
# ==== Descendu avec son vaisseau, on le retrouve posé à côté de soi, cassé (une des deux images au
# ==== hasard) : il ne sert plus à rien sur la planète.
# =============================================
IMAGES_VAISSEAU_CASSE = [RACINE / "image" / "image" / nom
                         for nom in ("vaisseau_joueur_casse1.png", "vaisseau_joueur_casse2.png")]
ECART_VAISSEAU_CASSE = 1.3   # distance (en cases) entre le héros et son vaisseau cassé, à sa gauche
DOSSIER_CARTES = RACINE / "map"
DUREE_FONDU = 0.8          # secondes du fondu au noir quand on change de carte
DUREE_DESCENTE = 1.6       # secondes de l'animation où le héros rétrécit avant de descendre
DEBUT_NOIR = 0.6           # à partir de cette part de l'animation, l'écran s'assombrit
TAILLE_MAX_OBJET = 1400    # l'image qui rétrécit est d'abord réduite à ce côté au plus (plus rapide)


class Orbite:
    def __init__(self, largeur, hauteur):
        self.planete = None    # gid de la planète où l'on est descendu (None : dans l'espace)
        self.cible = None      # dans l'espace : (tx, ty, gid) de la planète sous le héros, ou None
        # sur une planète : {"ecart": (dx, dy) du héros par rapport au centre de la planète (elle tourne : on
        # remonte au-dessus d'elle, là où elle est rendue), "vaisseau": vaisseau piloté, "position": (x, y) au départ}
        self.retour = None
        self.tilewidth = 128   # (taille d'une case de l'espace, donnée par update)
        self.cartes = {}       # gid -> carte de la planète (chargée à la première descente)
        self.fondu = 0.0       # 1 juste après un changement de carte, puis descend à 0
        self.animation = None  # descente en cours (voir commencer_descente), sinon None
        self.vaisseau_casse = None  # sur une planète : (image, centre en pixels monde) du vaisseau écrasé
        self.police = pygame.font.Font(None, 40)
        self.bouton = pygame.Rect(0, 0, 420, 64)
        self.bouton.midbottom = (largeur // 2, hauteur - 140)   # au-dessus de la barre d'inventaire

    @property
    def bouton_visible(self):
        return self.planete is not None or self.cible is not None

    @property
    def texte(self):
        if self.planete is not None:
            return "Remonter en orbite"
        return f"Descendre sur {PLANETES_GIDS[self.cible[2]][2]}"

    def update(self, dt, planetes, hero, tilewidth, camera):
        """Dans l'espace : cherche la planète au-dessus de laquelle est le héros (dans son disque, là
        où on la voit : elle est loin, voir Planetes.centre_affiche)."""
        self.fondu = max(0.0, self.fondu - dt / DUREE_FONDU)
        self.tilewidth = tilewidth
        self.cible = None
        if self.planete is not None:
            return
        x, y = hero.hitbox(hero.x, hero.y).center
        for tx, ty, gid in planetes.liste:
            if PLANETES_GIDS[gid][3] is None:
                continue  # (le Soleil : pas de carte, on ne peut pas y descendre)
            rayon = PLANETES_GIDS[gid][1] / 2 * tilewidth
            px, py = planetes.centre_affiche(tx, ty, camera)
            if math.hypot(px - x, py - y) <= rayon:
                self.cible = (tx, ty, gid)
                return

    def clic(self, event):
        """True si on vient de cliquer sur le bouton (visible)."""
        return (self.bouton_visible and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.bouton.collidepoint(event.pos))

    def _carte(self, gid):
        if gid not in self.cartes:
            # (cache_radius=1 : seulement les chunks à l'écran en mémoire ; sur une planète ils sont tous pleins)
            self.cartes[gid] = Map(str(DOSSIER_CARTES / PLANETES_GIDS[gid][3]), cache_radius=1, planete=True)
        return self.cartes[gid]

    def descendre(self, joueur):
        """On descend sur la planète visée : le héros sort de son vaisseau (qui reste en orbite) et
        arrive au milieu de la carte de la planète. Renvoie cette carte."""
        hero = joueur.hero
        tx, ty, gid = self.cible
        centre = ((tx + 0.5) * self.tilewidth, (ty + 0.5) * self.tilewidth)
        self.retour = {"ecart": (hero.x - centre[0], hero.y - centre[1]), "vaisseau": joueur.pilote,
                       "position": (hero.x, hero.y)}
        joueur.pilote = None
        carte = self._carte(gid)
        coins = [c for chunks in carte.layers.values() for c in chunks]
        cx = cy = 0  # (carte où rien n'est dessiné, tout le sol est généré : autour du milieu du monde)
        if coins:
            cx = (min(x for x, _ in coins) + max(x for x, _ in coins) + 1) / 2 * carte.chunk_size
            cy = (min(y for _, y in coins) + max(y for _, y in coins) + 1) / 2 * carte.chunk_size
        cx, cy = self._point_d_arrivee(carte, hero, cx, cy)
        milieu = hero.hitbox(0, 0).center
        hero.x, hero.y = cx * carte.tilewidth - milieu[0], cy * carte.tileheight - milieu[1]
        self.vaisseau_casse = None
        if self.retour["vaisseau"] is not None:
            # descendu avec son vaisseau : il est là, à côté, écrasé (un peu de travers) et inutilisable
            image = pygame.image.load(random.choice(IMAGES_VAISSEAU_CASSE)).convert_alpha()
            image = pygame.transform.smoothscale(image, (vaisseau_joueur.TAILLE, vaisseau_joueur.TAILLE))
            image = pygame.transform.rotate(image, random.uniform(-35, 35))
            centre = ((cx - ECART_VAISSEAU_CASSE) * carte.tilewidth, cy * carte.tileheight)
            self.vaisseau_casse = (image, centre)
        self.planete, self.cible, self.fondu = gid, None, 1.0
        return carte

    @staticmethod
    def _point_d_arrivee(carte, hero, cx, cy):
        """(x, y) en cases où l'on arrive : tiré au hasard à chaque descente, à au plus SPAWN_PLANETE_RAYON cases
        du milieu (cx, cy), pas dans un arbre (ni à côté : la place du vaisseau écrasé reste libre)."""
        milieu = hero.hitbox(0, 0).center
        for _ in range(100):
            angle = random.uniform(0, 2 * math.pi)
            distance = SPAWN_PLANETE_RAYON * math.sqrt(random.random())  # (réparti sur tout le disque)
            x, y = cx + math.cos(angle) * distance, cy + math.sin(angle) * distance
            zone = hero.hitbox(x * carte.tilewidth - milieu[0], y * carte.tileheight - milieu[1])
            if not carte.bloque(zone.inflate(2 * ECART_VAISSEAU_CASSE * carte.tilewidth, carte.tileheight)):
                return x, y
        return cx, cy  # (aucune place libre trouvée : le milieu, comme avant)

    def dessiner_vaisseau_casse(self, vue, camera):
        """Sur la planète : le vaisseau écrasé (s'il y en a un), à sa place."""
        if self.vaisseau_casse is not None:
            image, (x, y) = self.vaisseau_casse
            vue.blit(image, image.get_rect(center=(round(x - camera.x), round(y - camera.y))))

    # ---- animation de la descente ----
    def commencer_descente(self, fond, objet, pos, ancre):
        """Lance l'animation : `fond` = la vue sans ce qui descend ; `objet` = ce qui descend (héros,
        avec son vaisseau ou sa base), posé en `pos` dans la vue ; il rétrécit vers `ancre` (le héros)."""
        taille = max(objet.get_size())
        reduit = objet
        if taille > TAILLE_MAX_OBJET:
            f = TAILLE_MAX_OBJET / taille
            reduit = pygame.transform.smoothscale(objet, (max(1, round(objet.get_width() * f)),
                                                          max(1, round(objet.get_height() * f))))
        self.animation = {"fond": fond, "objet": reduit, "taille": objet.get_size(), "pos": pos,
                          "ancre": ancre, "temps": 0.0}

    def avancer_animation(self, dt):
        """Fait avancer l'animation. Renvoie True quand elle est finie (il est temps de descendre)."""
        self.animation["temps"] += dt
        if self.animation["temps"] < DUREE_DESCENTE:
            return False
        self.animation = None
        return True

    def dessiner_animation(self, vue):
        a = self.animation
        t = min(1.0, a["temps"] / DUREE_DESCENTE)
        echelle = (1 - t) ** 1.6  # rétrécit de plus en plus vite
        vue.blit(a["fond"], (0, 0))
        largeur, hauteur = round(a["taille"][0] * echelle), round(a["taille"][1] * echelle)
        if largeur >= 1 and hauteur >= 1:
            image = pygame.transform.smoothscale(a["objet"], (largeur, hauteur))
            ax, ay = a["ancre"]
            vue.blit(image, (round(ax + (a["pos"][0] - ax) * echelle), round(ay + (a["pos"][1] - ay) * echelle)))
        # (l'écran qui s'assombrit à la fin est dessiné par draw, à la taille de la fenêtre : moins de pixels)

    def position_retour(self, planetes):
        """(x, y) du héros quand il remontera : au même endroit au-dessus de la planète qu'à la descente,
        mais là où la planète est rendue (elle tourne autour du Soleil pendant qu'on est dessus)."""
        centre = planetes.centre(self.planete)
        if centre is None:
            return self.retour["position"]
        return centre[0] + self.retour["ecart"][0], centre[1] + self.retour["ecart"][1]

    def remonter(self, joueur, engins, planetes):
        """Retour dans l'espace, au-dessus de la planète (de nouveau dans son vaisseau si on le pilotait :
        le vaisseau, resté en orbite, a suivi la planète)."""
        hero = joueur.hero
        hero.x, hero.y = self.position_retour(planetes)
        joueur.pilote = self.retour["vaisseau"]
        if joueur.pilote is not None:
            joueur.pilote.x, joueur.pilote.y = hero.x, hero.y
        self.planete, self.retour, self.fondu, self.vaisseau_casse = None, None, 1.0, None

    def draw(self, screen, libre=True):
        """Le bouton (si `libre` : aucun menu ouvert), puis le fondu au noir après un changement de carte."""
        if self.bouton_visible and libre and self.animation is None:
            dessiner_bouton(screen, self.police, self.bouton, self.texte, self.bouton.collidepoint(ecran.souris()))
        noir = self.fondu
        if self.animation is not None:  # fin de l'animation de la descente : l'écran s'assombrit
            t = min(1.0, self.animation["temps"] / DUREE_DESCENTE)
            noir = max(noir, (t - DEBUT_NOIR) / (1 - DEBUT_NOIR))
        if noir > 0:
            voile = pygame.Surface(screen.get_size())
            voile.set_alpha(round(255 * noir))
            screen.blit(voile, (0, 0))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
