import math
import random
import sys
from pathlib import Path

import pygame

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction.vaisseau_teleporteur import SHARDS_PAR_SAUT
from systeme import ecran
from interface.ui import (COULEUR_ACCENT, COULEUR_BORDURE, COULEUR_TEXTE, COULEUR_TEXTE_GRIS, COULEUR_TITRE,
                          dessiner_bouton, dessiner_panneau)
from monde.planetes import (PLANETES_GIDS, chercher as chercher_planetes, orbites as orbites_planetes,
                            positions as positions_planetes)
from monde.systemes import (corps as corps_systeme, galaxies, position_galaxie, rayon_galaxie,
                            systemes_autour, systemes_dans)
from systeme.settings import CALQUE_BASE, VIDE_GIDS

# =============================================
# ==== Grande carte (touche M) : le monde qu'on a déjà parcouru, sur fond noir. Chaque case
# ==== proche du héros est « découverte » et le reste définitivement (sauvegardé avec le monde).
# ==== Les coordonnées sont en cases (1 case = tilewidth pixels), l'origine (0, 0) est la case
# ==== en haut à gauche de la carte Tiled ; la position du héros est donnée à 0,1 case près.
# =============================================
RAYON_DECOUVERTE = 10          # cases découvertes autour du héros
ECHELLE_DEPART = 14.0          # pixels de carte par case à l'ouverture
# L'échelle minimale laisse voir tout l'univers d'un coup : ±1500000 cases de galaxies, soit
# 3000000 cases de large, qui tiennent dans la vue à 0,0004 pixel par case.
ECHELLE_MIN, ECHELLE_MAX = 0.0003, 80.0
# méga dézoom : en dessous de cette échelle on ne voit plus les astéroïdes ni le terrain, seulement
# les zones découvertes et les bases (grossies pour rester visibles)
ECHELLE_LOIN = 2.0
# dézoom galactique : encore en dessous, une étoile ne ferait plus un pixel. On ne montre plus que les
# galaxies elles-mêmes (voir monde/systemes.py), chacune comme un amas lumineux. Ce seuil borne aussi
# le travail : à 0,02 la vue fait au plus ~60000 cases, soit quelques centaines de secteurs. Au-delà
# on passe aux galaxies, et il n'y a plus un seul système à calculer.
ECHELLE_GALAXIE = 0.02
ZOOM_MOLETTE = 1.18            # facteur par cran de molette...
ZOOM_MOLETTE_LOIN = 1.3        # ...plus rapide dans le méga dézoom...
ZOOM_MOLETTE_GALAXIE = 1.7     # ...et encore plus à l'échelle des galaxies (les distances y sont énormes)
TAILLE_MIN_BASE = 6            # méga dézoom : côté minimal (pixels) d'une case de base
TAILLE_MIN_PLANETE = 18        # méga dézoom : côté minimal (pixels) d'une planète
SEGMENTS_ORBITE = 240          # une orbite est dessinée en 240 petits traits (un sur deux : des pointillés)
TAILLE_MIN_SATELLITE = 28      # côté minimal (pixels) de l'icône d'un télescope sur la carte
# Systèmes solaires procéduraux (voir monde/systemes.py) : une étoile reste visible même de très loin,
# ses planètes sont bien plus petites et ne s'affichent qu'une fois le système découvert.
TAILLE_MIN_ETOILE = 11         # diamètre minimal (pixels) d'une étoile procédurale sur la carte
TAILLE_MIN_PLANETE_PROC = 4    # diamètre minimal (pixels) d'une planète procédurale
ECHELLE_NOM_SYSTEME = 0.05     # au-dessus de ce zoom, le nom du système découvert est écrit à côté
TAILLE_MIN_LUNE = 2            # diamètre minimal (pixels) d'une lune sur la carte
# Les lunes ne tournent qu'à quelques cases de leur planète : trop dézoomé, elles se confondraient avec
# elle (une planète à mille lunes ne serait qu'une tache). On ne les dessine qu'à partir de ce zoom,
# où une case fait au moins 1 pixel : les orbites sont alors séparables à l'œil.
ECHELLE_LUNES = 1.0
# Galaxies (cran de dézoom le plus large)
TAILLE_MIN_GALAXIE = 24        # diamètre minimal (pixels) d'une galaxie
LARGEUR_NOM_GALAXIE = 90       # au-delà de cette largeur à l'écran, son nom est écrit au-dessus
GALAXIES_GARDEES = 40          # images de galaxies gardées en mémoire (une par galaxie et par taille)
GALAXIE_POINTS = 420           # étoiles dessinées dans une galaxie
GALAXIE_COUCHES = 14           # disques du halo
GALAXIE_COEUR = 10             # disques du cœur lumineux
GALAXIE_CONCENTRATION = 0.75   # < 1 : les étoiles se serrent vers le centre
GALAXIE_DISPERSION = 0.22      # de combien une étoile s'écarte de son bras (radians)
TROU_NOIR_GALACTIQUE_HALO = (190, 110, 255)  # l'anneau violet du trou noir au cœur d'une galaxie
COULEUR_BASE_LOIN = (90, 150, 255)
PAS_GRILLE = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000,
              100000, 200000, 500000, 1000000, 2000000)
ECART_GRILLE = 70              # écart minimal (pixels) entre deux lignes de la grille
CHUNKS_PAR_IMAGE = 60          # carte complète : chunks (re)dessinés au plus par image (le reste suit aux suivantes)
# Budgets de génération procédurale. Le monde n'est PAS engendré quand on le découvre (sinon
# « découvrir toute la carte », F3, calculerait des centaines de milliers de secteurs d'un coup et
# figerait le jeu) : il est engendré quand on le REGARDE, et seulement par tranches. Au pire, la
# carte met quelques images à se remplir — jamais plus.
SECTEURS_PAR_IMAGE = 220       # secteurs de systèmes calculés au plus par image de carte
SECTEURS_PAR_SCAN = 400        # ... et par tour d'horizon d'un télescope
GLISSE_MAX_CLIC = 6            # pixels : au-delà, l'appui était un glissement, pas un clic (téléportation)

COULEUR_INCONNU = (0, 0, 0)    # case jamais vue
COULEUR_VIDE = (14, 18, 38)    # case vue, mais vide (espace)
COULEUR_GRILLE = (24, 30, 52)
COULEUR_GRILLE_FORTE = (60, 75, 120)
COULEUR_AXE = (110, 130, 200)
COULEUR_HEROS = (255, 255, 255)
COULEUR_TELEPORTATION = (150, 80, 255)
COULEUR_TELEPORTATION_REFUSEE = (220, 90, 90)


class GrandeCarte:
    """Carte plein écran ouverte par M : molette = zoom, glisser = déplacer, Espace = recentrer sur
    le héros, M ou Echap = fermer. Les cases non découvertes restent noires.
    Dans un vaisseau téléporteur, F l'ouvre en petit (au milieu de l'écran) : un clic sur une case
    découverte y téléporte le vaisseau."""

    def __init__(self, largeur, hauteur):
        self.ouvert = False
        self.decouvert = {}        # (chunk_x, chunk_y) -> entier dont chaque bit est une case vue
        self.nb_cases = 0          # nombre de cases découvertes
        self.tout_decouvert = False  # True une fois un télescope posé : tout le monde (infini) est visible
        self.pos_heros = (0.0, 0.0)  # position du héros en cases (décimales)
        self.direction = "bas"
        self.centre = [0.0, 0.0]   # case au milieu de la vue
        self.echelle = ECHELLE_DEPART
        self.glisse = None         # position de la souris pendant un glissement
        self._derniere = None      # dernière case du héros (la découverte ne se refait que si elle change)
        self._couleurs = {}        # gid -> (r, g, b, alpha) moyens
        self._surfaces = {}        # chunk -> image 1 pixel par case
        self._sales = set()        # chunks à redessiner (nouvelles cases vues, ou monde modifié)
        self._agrandies = {}       # chunk -> (taille, image agrandie, masque agrandi des cases vues)
        self._masques = {}         # chunk -> image 1 pixel par case : blanc = vue (la grille n'est dessinée que là)
        self._bases = None         # méga dézoom : [(tx, ty), ...] des cases de base visibles (refait à l'ouverture)
        self._planetes = []        # méga dézoom : [(tx, ty, gid), ...] des planètes (refait avec _bases)
        self.telescopes = None     # les télescopes (donnés par le jeu) : une icône de satellite chacun
        self.planetes = None       # les planètes (données par le jeu) : là où elles sont en ce moment
        # noms des planètes déjà vues (par un télescope, ou en passant à côté) : les autres, et leur orbite,
        # ne sont pas sur la carte. Après un chargement, on regarde aussi les cases déjà découvertes (voir ouvrir)
        self.planetes_vues = set()
        self._revoir_planetes = False
        # clés des systèmes solaires procéduraux découverts (passé dedans, ou vu au télescope) : leurs
        # orbites et leurs planètes ne sont sur la carte qu'après. Les étoiles, elles, se voient toujours
        # (une étoile brille : on la repère de n'importe où), voir _dessiner_systemes.
        self.systemes_vus = set()
        self._icones_satellite = {}  # côté -> image du télescope à cette taille
        self._images_galaxies = {}   # (nom de la galaxie, côté) -> son image à cette taille
        # téléportation : shards à bord du vaisseau téléporteur piloté (donné par le jeu à chaque image ;
        # None : pas de téléporteur). Sur la petite carte, un clic sur une case découverte la met dans
        # `destination`, et le bouton « Carburant » met `demande_carburant` à True (lus par le jeu)
        self.teleporteur = None
        self.destination = None
        self.demande_carburant = False
        self.taille_chunk = None   # (donnée par update : sert à savoir si la case visée est découverte)
        self._appui = None         # où le bouton a été enfoncé (clic ou glissement ?)
        self.petite = False        # True : petite carte de téléportation (F), False : grande carte (M)

        self.police_titre = pygame.font.Font(None, 70)
        self.police = pygame.font.Font(None, 32)
        self.police_petite = pygame.font.Font(None, 26)
        self.taille_ecran = (largeur, hauteur)
        self._placer()

    def _placer(self):
        """Panneau et vue : presque tout l'écran (grande carte), ou au milieu (petite carte de téléportation)."""
        largeur, hauteur = self.taille_ecran
        if self.petite:
            self.panneau = pygame.Rect(0, 0, int(largeur * 0.55), int(hauteur * 0.65))
            self.panneau.center = (largeur // 2, hauteur // 2)
        else:
            self.panneau = pygame.Rect(30, 30, largeur - 60, hauteur - 60)
        self.vue = pygame.Rect(self.panneau.x + 24, self.panneau.y + 90, self.panneau.width - 48,
                               self.panneau.height - 90 - 64)
        self._calque_masque = pygame.Surface(self.vue.size)   # cases vues, en blanc
        self._calque_grille = pygame.Surface(self.vue.size)   # lignes de la grille
        self.bouton_carburant = pygame.Rect(0, 0, 240, 44)    # (petite carte) : ouvre le carburant du vaisseau
        self.bouton_carburant.topright = (self.vue.right, self.vue.bottom + 10)

    # ---- découverte ----
    def _marquer(self, taille, x, y):
        """La case (x, y) est découverte."""
        cx, lx = divmod(x, taille)
        cy, ly = divmod(y, taille)
        bit = 1 << (ly * taille + lx)
        masque = self.decouvert.get((cx, cy), 0)
        if not masque & bit:
            self.decouvert[(cx, cy)] = masque | bit
            self._sales.add((cx, cy))
            self.nb_cases += 1

    def _decouvrir(self, taille, tx, ty):
        r = RAYON_DECOUVERTE
        for y in range(ty - r, ty + r + 1):
            for x in range(tx - r, tx + r + 1):
                if (x - tx) ** 2 + (y - ty) ** 2 <= r * r:
                    self._marquer(taille, x, y)

    def decouvrir_cone(self, taille, x0, y0, direction, demi_angle, portee, depuis=1):
        """Découvre les cases d'un cône (ce que voit un télescope) : il part de (x0, y0) (en cases,
        décimales), vers `direction` (radians, 0 = droite, y vers le bas), de `depuis` à `portee` cases."""
        for d in range(depuis, portee + 1):
            rayons = max(2, math.ceil(2 * demi_angle * d) + 1)  # assez de rayons pour ne pas sauter de case
            for i in range(rayons):
                a = direction - demi_angle + 2 * demi_angle * i / (rayons - 1)
                self._marquer(taille, math.floor(x0 + math.cos(a) * d), math.floor(y0 + math.sin(a) * d))

    def update(self, game_map, hero):
        """À appeler à chaque image du jeu : découvre les cases autour du héros."""
        x, y = hero.hitbox(hero.x, hero.y).center
        self.pos_heros = (x / game_map.tilewidth, y / game_map.tileheight)
        self.direction = hero.direction
        self.taille_chunk = game_map.chunk_size
        case = (math.floor(self.pos_heros[0]), math.floor(self.pos_heros[1]))
        if case != self._derniere:
            self._derniere = case
            self._decouvrir(game_map.chunk_size, *case)
            # une planète qui touche le cercle découvert autour du héros est vue
            for _, _, gid, (px, py), rayon in self._disques_planetes():
                if math.hypot(px - case[0] - 0.5, py - case[1] - 0.5) <= RAYON_DECOUVERTE + rayon:
                    self.planetes_vues.add(PLANETES_GIDS[gid][2])
            # entrer dans un système solaire procédural le découvre (ses orbites et ses planètes).
            # On ne regarde que les secteurs autour du héros : quelques-uns, calculés une seule fois.
            autour, _ = systemes_autour(self.graine, case[0] + 0.5, case[1] + 0.5, RAYON_DECOUVERTE, self._temps())
            self.systemes_vus.update(s.cle for s in autour)

    # ---- planètes vues ----
    def _disques_planetes(self):
        """[(tx, ty, gid, (centre x, centre y), rayon), ...] des planètes en ce moment, centre et rayon en cases."""
        if self.planetes is None:
            return []
        return [(tx, ty, gid, (tx + 0.5, ty + 0.5), PLANETES_GIDS[gid][1] / 2) for tx, ty, gid in self.planetes.liste]

    def planete_vue(self, gid):
        return self.tout_decouvert or PLANETES_GIDS[gid][2] in self.planetes_vues

    @property
    def graine(self):
        """La graine du monde, ou None (pas de monde procédural, ou le jeu n'a pas encore donné les
        planètes)."""
        if self.planetes is None:
            return None
        return self.planetes.game_map.graine

    def _temps(self):
        """Les secondes de jeu écoulées : les galaxies bougent et se contractent vers leur trou noir,
        donc tout ce qu'on leur demande dépend de l'instant (voir monde/systemes.py)."""
        return self.planetes.temps if self.planetes is not None else 0.0

    def systeme_vu(self, systeme):
        """True si le joueur a découvert ce système (il y est passé, ou un télescope l'a observé)."""
        return self.tout_decouvert or systeme.cle in self.systemes_vus

    def voir_planetes_cone(self, x0, y0, direction, demi_angle, portee):
        """Un télescope regarde le cône (voir decouvrir_cone) : les planètes qui sont dedans, même en partie,
        sont vues (elles bougent : on regarde tout le cône à chaque fois, pas seulement son nouveau bout)."""
        for _, _, gid, (px, py), rayon in self._disques_planetes():
            distance = math.hypot(px - x0, py - y0)
            if distance - rayon > portee:
                continue  # trop loin
            if distance <= rayon:
                self.planetes_vues.add(PLANETES_GIDS[gid][2])  # le télescope est sur la planète
                continue
            ecart = abs((math.atan2(py - y0, px - x0) - direction + math.pi) % (2 * math.pi) - math.pi)
            if ecart <= demi_angle + math.asin(rayon / distance):  # (le bord du disque entre dans le cône)
                self.planetes_vues.add(PLANETES_GIDS[gid][2])
        # un système solaire procédural dont une partie entre dans le cône est découvert en entier.
        # Seuls les secteurs à portée du télescope sont calculés, et au plus SECTEURS_PAR_SCAN
        # nouveaux par passage : un télescope de très longue portée ne fige pas le jeu, il finit
        # simplement son tour d'horizon sur plusieurs passages.
        a_portee, _ = systemes_autour(self.graine, x0, y0, portee, self._temps(), budget=SECTEURS_PAR_SCAN)
        for systeme in a_portee:
            if systeme.cle in self.systemes_vus:
                continue
            distance = math.hypot(systeme.cx - x0, systeme.cy - y0)
            if distance - systeme.rayon > portee:
                continue  # trop loin
            if distance <= systeme.rayon:
                self.systemes_vus.add(systeme.cle)  # le télescope est dans le système
                continue
            ecart = abs((math.atan2(systeme.cy - y0, systeme.cx - x0) - direction + math.pi)
                        % (2 * math.pi) - math.pi)
            if ecart <= demi_angle + math.asin(systeme.rayon / distance):
                self.systemes_vus.add(systeme.cle)

    def _voir_planetes_decouvertes(self):
        """Les planètes dont une case est déjà découverte sont vues (mondes d'avant cette règle, après un chargement)."""
        if self.taille_chunk is None:
            return
        for tx, ty, gid, (px, py), rayon in self._disques_planetes():
            if PLANETES_GIDS[gid][2] in self.planetes_vues:
                continue
            r = math.ceil(rayon)
            if any(self.est_decouvert(self.taille_chunk, x, y)
                   for y in range(math.floor(py) - r, math.floor(py) + r + 1)
                   for x in range(math.floor(px) - r, math.floor(px) + r + 1)
                   if math.hypot(x + 0.5 - px, y + 0.5 - py) <= rayon):
                self.planetes_vues.add(PLANETES_GIDS[gid][2])

    def tout_decouvrir(self):
        """Toute la carte est découverte, définitivement (les mondes où un télescope a été posé avant
        qu'il ne découvre que là où il regarde le gardent : voir importer)."""
        self.tout_decouvert = True
        self._sales.update(self._surfaces)
        self._bases = None

    def est_decouvert(self, taille, tx, ty):
        if self.tout_decouvert:
            return True
        cx, lx = divmod(tx, taille)
        cy, ly = divmod(ty, taille)
        return bool(self.decouvert.get((cx, cy), 0) >> (ly * taille + lx) & 1)

    # ---- sauvegarde ----
    def exporter(self):
        donnees = {f"{cx},{cy}": format(masque, "x") for (cx, cy), masque in self.decouvert.items()}
        if self.tout_decouvert:
            donnees["tout"] = "1"
        donnees["planetes"] = sorted(self.planetes_vues)
        donnees["systemes"] = sorted(self.systemes_vus)
        return donnees

    def importer(self, donnees):
        self.decouvert = {}
        self.tout_decouvert = "tout" in donnees
        self.planetes_vues = set(donnees.get("planetes", []))
        self.systemes_vus = set(donnees.get("systemes", []))
        self._revoir_planetes = "planetes" not in donnees  # (sauvegarde d'avant : voir _voir_planetes_decouvertes)
        for cle, masque in donnees.items():
            if cle in ("tout", "planetes", "systemes"):
                continue
            cx, cy = (int(v) for v in cle.split(","))
            self.decouvert[(cx, cy)] = int(masque, 16)
        self.nb_cases = sum(bin(m).count("1") for m in self.decouvert.values())
        self._derniere = None
        self._surfaces.clear()
        self._masques.clear()
        self._agrandies.clear()
        self._bases = None

    # ---- couleurs ----
    def _couleur_gid(self, game_map, gid):
        if gid not in self._couleurs:
            image = game_map.tile_image(gid)
            couleur = None
            if image is not None:
                r, g, b, a = pygame.transform.average_color(image, consider_alpha=True)
                if a > 0:  # les pixels transparents comptent pour 0 : on remonte à la couleur des pixels visibles
                    couleur = (min(255, r * 255 // a), min(255, g * 255 // a), min(255, b * 255 // a), a)
            self._couleurs[gid] = couleur
        return self._couleurs[gid]

    def _couleur_case(self, game_map, tx, ty):
        """Couleur d'une case vue : celle de la tuile du dessus (base, puis structures posées)."""
        resultat = COULEUR_VIDE
        for nom in game_map.layers:  # du calque du dessous à celui du dessus
            gid = game_map.get_layer_gid(nom, tx, ty)
            if not gid or (nom == CALQUE_BASE and gid in VIDE_GIDS):
                continue
            couleur = self._couleur_gid(game_map, gid)
            if couleur is not None and (nom == CALQUE_BASE or couleur[3] > 60):
                resultat = couleur[:3]
        return resultat

    @staticmethod
    def _chunk_vide(game_map, chunk):
        """True si le chunk n'a que du vide, sur tous les calques."""
        return all((gid in VIDE_GIDS) if nom == CALQUE_BASE else not gid
                   for nom in game_map.layers for ligne in game_map.grille(nom, chunk) for gid in ligne)

    def _image_chunk(self, game_map, chunk):
        """Le chunk à 1 pixel par case (noir là où rien n'est découvert), refait s'il a changé."""
        if chunk not in self._surfaces or chunk in self._sales:
            taille = game_map.chunk_size
            image = pygame.Surface((taille, taille))
            image.fill(COULEUR_INCONNU)
            vues = pygame.Surface((taille, taille))
            vues.fill((0, 0, 0))
            masque = (1 << taille * taille) - 1 if self.tout_decouvert else self.decouvert.get(chunk, 0)
            if self.tout_decouvert and self._chunk_vide(game_map, chunk):
                image.fill(COULEUR_VIDE)  # (le plus courant : inutile de regarder chaque case)
                vues.fill((255, 255, 255))
                masque = 0
            for i in range(taille * taille):
                if masque >> i & 1:
                    ly, lx = divmod(i, taille)
                    image.set_at((lx, ly), self._couleur_case(game_map, chunk[0] * taille + lx, chunk[1] * taille + ly))
                    vues.set_at((lx, ly), (255, 255, 255))
            self._surfaces[chunk] = image
            self._masques[chunk] = vues
            self._agrandies.pop(chunk, None)
            self._sales.discard(chunk)
        return self._surfaces[chunk]

    # ---- ouverture / évènements ----
    def centrer(self):
        self.centre = list(self.pos_heros)

    def ouvrir(self, inventaire, petite=False):
        """Ouvre la grande carte, ou la petite carte de téléportation si `petite`."""
        if petite != self.petite:
            self.petite = petite
            self._placer()
            self._agrandies.clear()
        self.ouvert = True
        inventaire.ouvert = False
        if self._revoir_planetes and self.planetes is not None and self.planetes.liste:
            self._revoir_planetes = False
            self._voir_planetes_decouvertes()
        self.centrer()
        self._sales.update(self.decouvert)  # le monde a pu changer depuis la dernière fois
        if self.tout_decouvert:
            self._sales.update(self._surfaces)
        self._bases = None

    def _case_sous(self, pos):
        """Case (décimales) sous une position de l'écran."""
        return (self.centre[0] + (pos[0] - self.vue.centerx) / self.echelle,
                self.centre[1] + (pos[1] - self.vue.centery) / self.echelle)

    def _saut(self, pos):
        """Téléportation vers la case sous `pos` : (case, None) si elle est possible, sinon (case, la raison)."""
        cx, cy = self._case_sous(pos)
        case = (math.floor(cx), math.floor(cy))
        if self.taille_chunk is None or not self.est_decouvert(self.taille_chunk, *case):
            return case, "Case inconnue : impossible de s'y téléporter"
        if self.teleporteur < SHARDS_PAR_SAUT:
            return case, "Plus de shard à bord : range-en dans le vaisseau (bouton Carburant)"
        return case, None

    def handle_event(self, event, inventaire=None, libre=True):
        """M ouvre la carte quand `libre`. Ouverte, elle absorbe les évènements. Renvoie True s'il est consommé."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_m and (self.ouvert or libre):
            if self.ouvert:
                self.ouvert = False
            else:
                self.ouvrir(inventaire)
            return True
        if not self.ouvert:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE or (event.key == pygame.K_f and self.petite):
                self.ouvert = False  # (Echap ne doit pas ouvrir la pause ; F referme la petite carte)
            elif event.key == pygame.K_TAB:
                self.ouvert = False  # Tab ouvre l'inventaire à la place
                return False
            elif event.key == pygame.K_SPACE:
                self.centrer()
            return True

        if event.type == pygame.MOUSEWHEEL:
            souris = ecran.souris()
            if self.vue.collidepoint(souris):
                avant = self._case_sous(souris)
                if self.echelle < ECHELLE_GALAXIE:
                    facteur = ZOOM_MOLETTE_GALAXIE
                elif self.echelle < ECHELLE_LOIN:
                    facteur = ZOOM_MOLETTE_LOIN
                else:
                    facteur = ZOOM_MOLETTE
                self.echelle = max(ECHELLE_MIN, min(ECHELLE_MAX, self.echelle * facteur ** event.y))
                apres = self._case_sous(souris)   # la case sous la souris reste la même
                self.centre[0] += avant[0] - apres[0]
                self.centre[1] += avant[1] - apres[1]
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panneau.collidepoint(event.pos):
                self.ouvert = False
            elif self.petite and self.bouton_carburant.collidepoint(event.pos):
                self.demande_carburant = True
                self.ouvert = False
            elif self.vue.collidepoint(event.pos):
                self.glisse = event.pos
                self._appui = event.pos
            return True
        if event.type == pygame.MOUSEMOTION:
            if self.glisse is not None:
                self.centre[0] -= (event.pos[0] - self.glisse[0]) / self.echelle
                self.centre[1] -= (event.pos[1] - self.glisse[1]) / self.echelle
                self.glisse = event.pos
            return True
        if event.type == pygame.MOUSEBUTTONUP:
            # petite carte (vaisseau téléporteur) : un clic (pas un glissement) sur une case découverte, on y saute
            appui, self.glisse, self._appui = self._appui, None, None
            if (event.button == 1 and self.petite and self.teleporteur is not None and appui is not None
                    and math.hypot(event.pos[0] - appui[0], event.pos[1] - appui[1]) <= GLISSE_MAX_CLIC):
                case, refus = self._saut(event.pos)
                if refus is None:
                    self.destination = case
                    self.ouvert = False
            return True
        return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)

    # ---- dessin ----
    def _x(self, case):
        return self.vue.centerx + (case - self.centre[0]) * self.echelle

    def _y(self, case):
        return self.vue.centery + (case - self.centre[1]) * self.echelle

    def _etiquette(self, screen, texte, pos, **ancre):
        image = self.police_petite.render(texte, True, COULEUR_TEXTE)
        place = image.get_rect(**{k: pos for k in ancre})
        fond = pygame.Surface(place.inflate(8, 2).size, pygame.SRCALPHA)
        fond.fill((0, 0, 0, 170))
        screen.blit(fond, place.inflate(8, 2))
        screen.blit(image, place)

    def _dessiner_monde(self, screen, game_map):
        taille = game_map.chunk_size
        vue = self.vue
        self._calque_masque.fill((0, 0, 0))
        if self.tout_decouvert:  # monde infini : seulement les chunks dans la vue
            gauche, haut = self._case_sous(vue.topleft)
            droite, bas = self._case_sous(vue.bottomright)
            chunks = [(cx, cy) for cy in range(math.floor(haut / taille), math.floor(bas / taille) + 1)
                      for cx in range(math.floor(gauche / taille), math.floor(droite / taille) + 1)]
        else:
            chunks = self.decouvert
        refaits = 0
        for chunk in chunks:
            x0, x1 = round(self._x(chunk[0] * taille)), round(self._x((chunk[0] + 1) * taille))
            y0, y1 = round(self._y(chunk[1] * taille)), round(self._y((chunk[1] + 1) * taille))
            if x1 < vue.left or x0 > vue.right or y1 < vue.top or y0 > vue.bottom:
                continue
            if chunk not in self._surfaces or chunk in self._sales:
                if self.tout_decouvert and refaits >= CHUNKS_PAR_IMAGE:
                    if chunk not in self._surfaces:
                        continue  # dessiné à une prochaine image
                else:
                    refaits += 1
                    self._image_chunk(game_map, chunk)
            image = self._surfaces[chunk]
            if self._agrandies.get(chunk, (None,))[0] != (x1 - x0, y1 - y0):
                dimension = (x1 - x0, y1 - y0)
                self._agrandies[chunk] = (dimension, pygame.transform.scale(image, dimension),
                                          pygame.transform.scale(self._masques[chunk], dimension))
            _, agrandie, masque = self._agrandies[chunk]
            screen.blit(agrandie, (x0, y0))
            self._calque_masque.blit(masque, (x0 - vue.x, y0 - vue.y))

    # ---- méga dézoom ----
    def _cases_bases(self, game_map):
        """Cases de base visibles et découvertes (seulement celles de la carte et celles posées par
        le joueur : le terrain généré, astéroïdes compris, n'en fait pas partie)."""
        if self._bases is None:
            taille = game_map.chunk_size
            self._bases = []
            for (cx, cy), grille in game_map.layers[CALQUE_BASE].items():
                gids = set()
                for ligne in grille:
                    gids.update(ligne)
                if not any(gid not in VIDE_GIDS and gid not in PLANETES_GIDS and self._couleur_gid(game_map, gid)
                           for gid in gids):
                    continue  # (presque tous les chunks : rien à montrer, on ne regarde pas case par case)
                for ly, ligne in enumerate(grille):
                    for lx, gid in enumerate(ligne):
                        tx, ty = cx * taille + lx, cy * taille + ly
                        if (gid not in VIDE_GIDS and gid not in PLANETES_GIDS and self._couleur_gid(game_map, gid)
                                and self.est_decouvert(taille, tx, ty)):
                            self._bases.append((tx, ty))
        return self._bases

    def _dessiner_decouvert_loin(self, screen, game_map):
        """Méga dézoom : les zones découvertes, chunk par chunk, sans leur contenu."""
        vue = self.vue
        if self.tout_decouvert:
            screen.fill(COULEUR_VIDE, vue)
            self._calque_masque.fill((255, 255, 255))
            return
        self._calque_masque.fill((0, 0, 0))
        taille = game_map.chunk_size
        cote = max(1, math.ceil(taille * self.echelle))
        for cx, cy in self.decouvert:
            zone = pygame.Rect(math.floor(self._x(cx * taille)), math.floor(self._y(cy * taille)), cote, cote)
            if zone.colliderect(vue):
                screen.fill(COULEUR_VIDE, zone)
                self._calque_masque.fill((255, 255, 255), zone.move(-vue.x, -vue.y))

    def _dessiner_bases_loin(self, screen, game_map):
        """Méga dézoom : les bases, grossies pour qu'on les voie même de très loin."""
        cote = max(TAILLE_MIN_BASE, math.ceil(self.echelle))
        for tx, ty in self._cases_bases(game_map):
            x, y = self._x(tx + 0.5), self._y(ty + 0.5)
            if self.vue.collidepoint(x, y):
                screen.fill(COULEUR_BASE_LOIN, (round(x - cote / 2), round(y - cote / 2), cote, cote))

    def _dessiner_satellites(self, screen):
        """Une icône de satellite par télescope posé, tournée comme lui (2 cases de côté, mais jamais
        plus petite que TAILLE_MIN_SATELLITE pour rester visible de loin)."""
        if self.telescopes is None:
            return
        cote = max(TAILLE_MIN_SATELLITE, round(2 * self.echelle))
        if cote not in self._icones_satellite:
            if len(self._icones_satellite) > 20:
                self._icones_satellite.clear()  # (tailles des anciens zooms)
            self._icones_satellite[cote] = pygame.transform.smoothscale(self.telescopes.image, (cote, cote))
        for tx, ty in self.telescopes.tous():
            x, y = self._x(tx + 1), self._y(ty + 1)  # (milieu du bloc 2x2)
            if not self.vue.inflate(cote, cote).collidepoint(x, y):
                continue
            image = pygame.transform.rotate(self._icones_satellite[cote], -math.degrees(self.telescopes.angle(tx, ty)))
            screen.blit(image, image.get_rect(center=(round(x), round(y))))

    def _dessiner_orbite(self, screen, cx, cy, rayon, couleur):
        """Le cercle (en pointillés, de la couleur de la planète en plus sombre) que suit une planète autour
        de son astre : centre (cx, cy) et rayon en cases. (Des petits traits plutôt qu'un vrai cercle : même
        immense quand on zoome, il reste rapide à dessiner.)"""
        x, y, r = self._x(cx), self._y(cy), rayon * self.echelle
        if r < 3 or not self.vue.inflate(2 * r, 2 * r).collidepoint(x, y):
            return
        sombre = tuple(round(c * 0.6) for c in couleur)
        points = [(x + math.cos(2 * math.pi * k / SEGMENTS_ORBITE) * r, y + math.sin(2 * math.pi * k / SEGMENTS_ORBITE) * r)
                  for k in range(SEGMENTS_ORBITE + 1)]
        for k in range(0, SEGMENTS_ORBITE, 2):  # un trait sur deux : des pointillés
            pygame.draw.line(screen, sombre, points[k], points[k + 1], 2)

    def _image_galaxie(self, galaxie, cote):
        """L'image d'une galaxie à `cote` pixels : un cœur lumineux, un halo, et pour une spirale des
        bras faits de points. Dessinée une fois par galaxie et par taille, puis gardée : elle ne
        dépend que de la galaxie (tirée de la graine), donc elle ne change jamais."""
        cle = (galaxie.nom, cote)
        if cle not in self._images_galaxies:
            if len(self._images_galaxies) > GALAXIES_GARDEES:
                self._images_galaxies.clear()  # (tailles d'un ancien zoom)
            image = pygame.Surface((cote, cote), pygame.SRCALPHA)
            c = cote / 2
            r, v, b = galaxie.couleur
            # le halo : des disques de plus en plus transparents vers le bord
            for i in range(GALAXIE_COUCHES, 0, -1):
                k = i / GALAXIE_COUCHES
                pygame.draw.circle(image, (r, v, b, round(14 * (1 - k) + 3)), (c, c), c * k)
            # les étoiles : des points, plus serrés au cœur et le long des bras
            tirage = random.Random(f"galaxie:{galaxie.nom}")
            for _ in range(GALAXIE_POINTS):
                k = tirage.random() ** GALAXIE_CONCENTRATION   # vers le centre
                if galaxie.type == "spirale":
                    # sur un bras, à une petite dispersion près : c'est ce qui dessine la spirale
                    bras = tirage.randrange(galaxie.bras)
                    angle = (galaxie.angle0 + bras * math.tau / galaxie.bras
                             + k * galaxie.enroulement * math.tau
                             + tirage.gauss(0, GALAXIE_DISPERSION))
                elif galaxie.type == "irrégulière":
                    angle = tirage.uniform(0, math.tau) + math.cos(k * 6) * 0.8
                else:
                    angle = tirage.uniform(0, math.tau)
                rayon = k * c * (0.95 if galaxie.type != "elliptique" else 0.8)
                x = c + math.cos(angle) * rayon
                y = c + math.sin(angle) * rayon * (0.6 if galaxie.type == "elliptique" else 1.0)
                clarte = round(90 + 165 * (1 - k))
                pygame.draw.circle(image, (min(255, r + 40), min(255, v + 40), min(255, b + 40), clarte),
                                   (x, y), 1)
            # le cœur
            for i in range(GALAXIE_COEUR, 0, -1):
                k = i / GALAXIE_COEUR
                pygame.draw.circle(image, (255, 255, 255, round(150 * (1 - k) + 40)),
                                   (c, c), c * 0.1 * k + 1)
            # le trou noir supermassif, pile au milieu : un point noir cerclé de violet. Il est
            # beaucoup trop petit pour être à l'échelle ici (55 cases dans une galaxie de 110000) :
            # on le marque, sinon on ne le verrait jamais.
            marque = max(2, round(cote * 0.035))
            pygame.draw.circle(image, (*TROU_NOIR_GALACTIQUE_HALO, 230), (c, c), marque + 2, 2)
            pygame.draw.circle(image, (0, 0, 0, 255), (c, c), marque)
            self._images_galaxies[cle] = image
        return self._images_galaxies[cle]

    def _dessiner_galaxies(self, screen):
        """Le cran de dézoom le plus large : on ne voit plus les étoiles une à une, mais les galaxies
        entières (voir monde/systemes.py). Elles sont toujours visibles, comme les étoiles : une
        galaxie se voit de n'importe où, découverte ou non — « découvrir toute la carte » (F3) ne
        change donc rien ici, et ne coûte rien."""
        temps = self.planetes.temps if self.planetes is not None else 0.0
        for galaxie in galaxies(self.graine):
            # elles bougent, et leur trou noir les contracte : leur place et leur taille dépendent
            # de l'instant (voir position_galaxie et aspiration)
            gx, gy = position_galaxie(galaxie, temps)
            rayon = rayon_galaxie(galaxie, temps)
            cote = max(TAILLE_MIN_GALAXIE, round(rayon * 2 * self.echelle))
            centre = (round(self._x(gx)), round(self._y(gy)))
            if not self.vue.inflate(cote, cote).collidepoint(centre):
                continue
            image = self._image_galaxie(galaxie, cote)
            screen.blit(image, image.get_rect(center=centre))
            if self.echelle * rayon * 2 >= LARGEUR_NOM_GALAXIE:
                self._etiquette(screen, f"{galaxie.nom} · galaxie {galaxie.type}",
                                (centre[0], centre[1] - cote // 2 - 6), midbottom=0)

    def _dessiner_astre(self, screen, cx, cy, rayon_cases, couleur, mini, trou_noir=False):
        """Une boule à (cx, cy) (en cases), de `rayon_cases` cases de rayon, mais jamais plus petite que
        `mini` pixels de diamètre : de très loin, une étoile reste un point visible. Un trou noir est
        dessiné à l'envers : un disque noir cerclé de violet."""
        rayon = max(mini, round(rayon_cases * 2 * self.echelle)) // 2
        centre = (round(self._x(cx)), round(self._y(cy)))
        if not self.vue.inflate(2 * rayon, 2 * rayon).collidepoint(centre):
            return
        if trou_noir:
            pygame.draw.circle(screen, couleur, centre, rayon + 2, 2)      # l'anneau de lumière
            pygame.draw.circle(screen, (0, 0, 0), centre, rayon)           # l'horizon des événements
            return
        pygame.draw.circle(screen, couleur, centre, rayon)
        clair = tuple(min(255, c + 60) for c in couleur)  # un reflet : on voit que c'est une boule
        pygame.draw.circle(screen, clair, (centre[0] - rayon // 3, centre[1] - rayon // 3), max(1, rayon // 3))

    def _dessiner_systemes(self, screen):
        """Les systèmes solaires tirés de la graine (voir monde/systemes.py). Leur étoile (ou leurs deux
        soleils, ou leur trou noir) se voit toujours : une étoile brille, on la repère de n'importe où.
        Leurs orbites et leurs planètes n'apparaissent qu'une fois le système découvert — en y passant,
        ou en le visant au télescope (voir systeme_vu)."""
        if self.planetes is None:
            return
        temps = self.planetes.temps
        # on ne demande QUE les systèmes de la vue, et au plus SECTEURS_PAR_IMAGE nouveaux secteurs :
        # le reste arrivera aux images suivantes (la carte se redessine à chaque image)
        gauche, haut = self._case_sous(self.vue.topleft)
        droite, bas = self._case_sous(self.vue.bottomright)
        visibles, _ = systemes_dans(self.graine, gauche, haut, droite, bas, temps, budget=SECTEURS_PAR_IMAGE)
        for systeme in visibles:
            # tout le système tient dans un cercle de `rayon` cases : s'il ne touche pas la vue, on passe
            portee = systeme.rayon * self.echelle + TAILLE_MIN_ETOILE
            if not self.vue.inflate(2 * portee, 2 * portee).collidepoint(self._x(systeme.cx), self._y(systeme.cy)):
                continue
            etoiles, planetes, lunes = corps_systeme(systeme, temps)
            connu = self.systeme_vu(systeme)
            if connu:
                for planete in systeme.planetes:  # les orbites, sous les astres
                    self._dessiner_orbite(screen, systeme.cx, systeme.cy, planete.orbite, systeme.couleur)
            for ex, ey, etoile in etoiles:
                # `trou_noir` est porté par l'astre : un centre galactique mêle un trou noir
                # supermassif et les étoiles qui tournent autour
                self._dessiner_astre(screen, ex, ey, etoile.rayon, etoile.couleur,
                                     TAILLE_MIN_ETOILE, etoile.trou_noir)
            if not connu:
                continue
            # les lunes : seulement d'assez près (voir ECHELLE_LUNES), et sous les planètes pour que
            # la planète reste bien lisible au milieu de son cortège
            if lunes and self.echelle >= ECHELLE_LUNES:
                for lx, ly, lune in lunes:
                    self._dessiner_astre(screen, lx, ly, lune.taille / 2, lune.couleur, TAILLE_MIN_LUNE)
            for px, py, planete in planetes:
                self._dessiner_astre(screen, px, py, planete.taille / 2, planete.couleur,
                                     TAILLE_MIN_PLANETE_PROC)
            if self.echelle >= ECHELLE_NOM_SYSTEME:
                haut = self._y(systeme.cy) - max(TAILLE_MIN_ETOILE, systeme.etoiles[0].rayon * 2 * self.echelle) / 2
                nb_lunes = sum(len(p.lunes) for p in systeme.planetes)
                texte = f"{systeme.nom} · {systeme.genre} · {len(systeme.planetes)} planètes"
                if nb_lunes:
                    texte += f" · {nb_lunes} lune{'s' if nb_lunes > 1 else ''}"
                self._etiquette(screen, texte, (round(self._x(systeme.cx)), round(haut) - 6), midbottom=0)

    def _dessiner_planetes(self, screen, game_map):
        """Les planètes (Mars, le Soleil...) : une boule de leur couleur (PLANETES_GIDS[gid][4] : rouge pour
        Mars, jaune pour le Soleil), à leur taille (PLANETES_GIDS[gid][1] cases de diamètre), mais jamais plus
        petite que TAILLE_MIN_PLANETE pour rester visible de très loin, et là où elles sont en ce moment (Mars
        tourne autour du Soleil). Seulement celles déjà vues (télescope ou héros), avec leur orbite."""
        if self.planetes is not None:
            self._planetes, reperes = self.planetes.liste, self.planetes.reperes
        else:  # (sans le jeu, ex : un test) : les planètes au début de leur tour
            reperes = chercher_planetes(game_map)
            self._planetes = positions_planetes(reperes, 0)
        for cx, cy, rayon, gid in orbites_planetes(reperes):
            if self.planete_vue(gid):  # (gid : la planète qui suit cette orbite)
                self._dessiner_orbite(screen, cx + 0.5, cy + 0.5, rayon, PLANETES_GIDS[gid][4])
        for tx, ty, gid in self._planetes:
            if not self.planete_vue(gid):
                continue
            rayon = max(TAILLE_MIN_PLANETE, round(PLANETES_GIDS[gid][1] * self.echelle)) // 2
            centre = (round(self._x(tx + 0.5)), round(self._y(ty + 0.5)))
            if not self.vue.inflate(2 * rayon, 2 * rayon).collidepoint(centre):
                continue
            couleur = PLANETES_GIDS[gid][4]
            pygame.draw.circle(screen, couleur, centre, rayon)
            # un reflet plus clair en haut à gauche : on voit que c'est une boule
            clair = tuple(min(255, c + 60) for c in couleur)
            pygame.draw.circle(screen, clair, (centre[0] - rayon // 3, centre[1] - rayon // 3), max(1, rayon // 3))

    def _dessiner_grille(self, screen):
        """Grille des coordonnées : les lignes ne se voient que sur les cases découvertes (le reste
        reste noir) ; les repères chiffrés, eux, restent sur les bords."""
        vue = self.vue
        pas = next((p for p in PAS_GRILLE if p * self.echelle >= ECART_GRILLE), PAS_GRILLE[-1])
        gauche, droite = self._case_sous(vue.topleft)[0], self._case_sous(vue.bottomright)[0]
        haut, bas = self._case_sous(vue.topleft)[1], self._case_sous(vue.bottomright)[1]
        calque = self._calque_grille
        calque.fill((0, 0, 0))
        reperes = []
        for k in range(math.ceil(gauche / pas), math.floor(droite / pas) + 1):
            case = k * pas
            x = round(self._x(case))
            couleur = COULEUR_AXE if case == 0 else (COULEUR_GRILLE_FORTE if k % 5 == 0 else COULEUR_GRILLE)
            pygame.draw.line(calque, couleur, (x - vue.x, 0), (x - vue.x, vue.height), 2 if case == 0 else 1)
            reperes.append((str(case), (x + 4, vue.top + 3)))
        for k in range(math.ceil(haut / pas), math.floor(bas / pas) + 1):
            case = k * pas
            y = round(self._y(case))
            couleur = COULEUR_AXE if case == 0 else (COULEUR_GRILLE_FORTE if k % 5 == 0 else COULEUR_GRILLE)
            pygame.draw.line(calque, couleur, (0, y - vue.y), (vue.width, y - vue.y), 2 if case == 0 else 1)
            reperes.append((str(case), (vue.left + 4, y + 3)))
        calque.blit(self._calque_masque, (0, 0), special_flags=pygame.BLEND_RGB_MULT)  # noir hors des cases vues
        screen.blit(calque, vue.topleft, special_flags=pygame.BLEND_RGB_ADD)
        for texte, pos in reperes:
            self._etiquette(screen, texte, pos, topleft=0)

    def _dessiner_heros(self, screen):
        px, py = round(self._x(self.pos_heros[0])), round(self._y(self.pos_heros[1]))
        rayon = 7 + int(2 * math.sin(pygame.time.get_ticks() / 250))
        if self.vue.inflate(-20, -20).collidepoint(px, py):
            pygame.draw.circle(screen, COULEUR_ACCENT, (px, py), rayon + 4, 2)
            pygame.draw.circle(screen, COULEUR_HEROS, (px, py), 5)
            dx, dy = {"haut": (0, -1), "bas": (0, 1), "gauche": (-1, 0), "droite": (1, 0)}[self.direction]
            pygame.draw.line(screen, COULEUR_HEROS, (px, py), (px + dx * 16, py + dy * 16), 3)
        else:
            # hors de la vue : une flèche au bord, dans sa direction
            milieu = self.vue.center
            angle = math.atan2(py - milieu[1], px - milieu[0])
            bord = pygame.Rect(0, 0, self.vue.width - 40, self.vue.height - 40)
            bord.center = milieu
            t = min(bord.width / 2 / max(1e-6, abs(math.cos(angle))), bord.height / 2 / max(1e-6, abs(math.sin(angle))))
            ax, ay = milieu[0] + math.cos(angle) * t, milieu[1] + math.sin(angle) * t
            pointe = (ax + math.cos(angle) * 14, ay + math.sin(angle) * 14)
            gauche = (ax + math.cos(angle + 2.5) * 12, ay + math.sin(angle + 2.5) * 12)
            droite = (ax + math.cos(angle - 2.5) * 12, ay + math.sin(angle - 2.5) * 12)
            pygame.draw.polygon(screen, COULEUR_HEROS, [pointe, gauche, droite])

    def _dessiner_teleportation(self, screen, souris):
        """Dans un vaisseau téléporteur : une cible violette sur la case visée (rouge si on ne peut pas
        y sauter), et en bas à gauche ce que fait un clic."""
        texte = f"Clic sur une case découverte : s'y téléporter ({SHARDS_PAR_SAUT} shard, {self.teleporteur} à bord)"
        if self.vue.collidepoint(souris):
            case, refus = self._saut(souris)
            couleur = COULEUR_TELEPORTATION if refus is None else COULEUR_TELEPORTATION_REFUSEE
            centre = (round(self._x(case[0] + 0.5)), round(self._y(case[1] + 0.5)))
            rayon = max(10, round(self.echelle * 0.6))
            pygame.draw.circle(screen, couleur, centre, rayon, 3)
            pygame.draw.circle(screen, couleur, centre, 3)
            texte = refus or texte
        self._etiquette(screen, texte, (self.vue.left + 10, self.vue.bottom - 8), bottomleft=0)

    def draw(self, screen, game_map):
        if not self.ouvert:
            return
        dessiner_panneau(screen, self.panneau)
        titre = "Téléportation" if self.petite else "Carte"
        screen.blit(self.police_titre.render(titre, True, COULEUR_TITRE), (self.panneau.x + 24, self.panneau.y + 18))
        if self.petite:
            aide = "F ou Echap : fermer   ·   molette : zoom   ·   glisser : déplacer"
        else:
            aide = "M ou Echap : fermer   ·   molette : zoom   ·   glisser : déplacer   ·   Espace : recentrer"
        aide = self.police_petite.render(aide, True, COULEUR_TEXTE_GRIS)
        screen.blit(aide, aide.get_rect(topright=(self.panneau.right - 24, self.panneau.y + 36)))

        ancien = screen.get_clip()
        screen.set_clip(self.vue)
        screen.fill(COULEUR_INCONNU, self.vue)
        galactique = self.echelle < ECHELLE_GALAXIE  # on ne voit plus que les galaxies
        loin = self.echelle < ECHELLE_LOIN           # méga dézoom : les zones découvertes et les bases
        if galactique:
            # à cette échelle une case fait moins d'un centième de pixel : il n'y a rien d'autre à
            # montrer que les galaxies. La grille, elle, reste entièrement visible (le masque des
            # cases découvertes n'a plus de sens à l'échelle de l'univers).
            self._calque_masque.fill((255, 255, 255))
        elif loin:
            self._dessiner_decouvert_loin(screen, game_map)
        else:
            self._dessiner_monde(screen, game_map)
        self._dessiner_grille(screen)
        if galactique:
            self._dessiner_galaxies(screen)
        else:
            if loin:
                self._dessiner_bases_loin(screen, game_map)
            self._dessiner_systemes(screen)   # (les systèmes tirés de la graine, sous les planètes)
            self._dessiner_planetes(screen, game_map)
            self._dessiner_satellites(screen)
        if not self.petite:  # (petite carte : la place est prise par l'aide de la téléportation)
            if galactique:
                self._etiquette(screen, "Dézoom galactique : les galaxies de l'univers",
                                (self.vue.right - 10, self.vue.bottom - 8), bottomright=0)
            elif loin:
                self._etiquette(screen, "Méga dézoom : seulement les bases, les systèmes solaires, les planètes et les satellites",
                                (self.vue.right - 10, self.vue.bottom - 8), bottomright=0)
        souris = ecran.souris()
        if self.vue.collidepoint(souris):
            pygame.draw.line(screen, (90, 100, 140), (souris[0], self.vue.top), (souris[0], self.vue.bottom), 1)
            pygame.draw.line(screen, (90, 100, 140), (self.vue.left, souris[1]), (self.vue.right, souris[1]), 1)
        self._dessiner_heros(screen)
        if self.petite and self.teleporteur is not None:
            self._dessiner_teleportation(screen, souris)
        screen.set_clip(ancien)
        pygame.draw.rect(screen, COULEUR_BORDURE, self.vue, 2)

        # pied : position exacte du héros, case sous le curseur, avancement de l'exploration
        y = self.vue.bottom + 18
        hx, hy = self.pos_heros
        screen.blit(self.police.render(f"Héros : X {hx:.1f}   Y {hy:.1f}".replace(".", ","), True, COULEUR_TITRE),
                    (self.vue.x, y))
        if self.vue.collidepoint(souris):
            cx, cy = self._case_sous(souris)
            tx, ty = math.floor(cx), math.floor(cy)
            etat = "découverte" if self.est_decouvert(game_map.chunk_size, tx, ty) else "inconnue"
            texte = f"Curseur : X {tx}   Y {ty}   ({etat})"
            couleur = COULEUR_TEXTE if etat == "découverte" else COULEUR_TEXTE_GRIS
            image = self.police.render(texte, True, couleur)
            screen.blit(image, image.get_rect(midtop=(self.vue.centerx, y)))
        if self.petite:  # petite carte : le bouton du carburant (et des shards) à la place du bilan
            dessiner_bouton(screen, self.police, self.bouton_carburant, "Carburant",
                            self.bouton_carburant.collidepoint(souris))
            return
        if self.tout_decouvert:
            bilan = self.police.render("Carte complète (télescope)", True, COULEUR_ACCENT)
        else:
            bilan = self.police.render(f"Exploré : {self.nb_cases:,} cases".replace(",", " "), True, COULEUR_TEXTE_GRIS)
        screen.blit(bilan, bilan.get_rect(topright=(self.vue.right, y)))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
