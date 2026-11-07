import math
import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structures.building import case_sous_souris
from construction import canon_electromagnetique, tourelle as construction_tourelle, tourelle_plasma

# =============================================
# ==== Les tourelles posées : la tourelle, le canon électromagnétique et la tourelle plasma marchent
# ==== pareil, avec les réglages (munition, portée, cadence, dégâts, images...) de leur module de
# ==== construction/. Tir "balle" : un rond qui file jusqu'au premier ennemi touché. Tir "rayon" :
# ==== instantané, il traverse tous les ennemis sur sa ligne et reste un instant à l'écran (voir Rayon).
# ==== Tir "laser" : un trait continu braqué sur la cible, qui lui retire des HP à chaque CADENCE.
# ==== Une tourelle sans MUNITION (plasma) ne se charge pas : elle tire tant qu'elle a de l'énergie.
# =============================================
MODELES = [construction_tourelle, canon_electromagnetique, tourelle_plasma]
MODELE_DU_GID = {modele.TUILES[0][2]: modele for modele in MODELES}  # gid du socle -> son modèle
RAYON_BALLE = 6
COULEUR_VIDE = (255, 80, 80)  # nombre de munitions quand la réserve est vide
RAYON_TOUCHE = 40  # distance du centre d'un alien à laquelle un tir le touche

DUREE_RAYON = 0.45            # secondes pendant lesquelles un rayon reste visible (il s'efface)
PAS_ARC = 45                  # pixels entre deux coudes des arcs électriques autour du rayon
ECART_ARC = 14                # écart max (pixels) des arcs électriques de part et d'autre du rayon
# couches du rayon, de la plus large (le halo) au cœur : (largeur, couleur, opacité max)
COUCHES_RAYON = [(34, (30, 90, 255), 40), (20, (40, 140, 255), 80), (11, (70, 190, 255), 170),
                 (5, (170, 235, 255), 235), (2, (255, 255, 255), 255)]
COULEUR_ARC = (150, 225, 255)

# laser plasma : couches (largeur, couleur, opacité), de la plus large au cœur ; elles « respirent »
COUCHES_LASER = [(28, (20, 200, 180), 70), (16, (40, 240, 210), 150), (7, (150, 255, 240), 255),
                 (3, (255, 255, 255), 255)]
PAS_ONDE = 10                 # pixels entre deux points des filaments de plasma qui ondulent autour
LONGUEUR_ONDE = 70            # longueur d'une ondulation des filaments (pixels)
AMPLITUDE_ONDE = 7            # écart max des filaments (pixels)


class Rayon:
    """Un tir de canon électromagnétique : un trait de (x1, y1) à (x2, y2) (pixels monde), déjà arrivé
    (les dégâts sont faits au tir). Il ne sert qu'à l'effet : il s'efface en DUREE_RAYON secondes."""

    def __init__(self, x1, y1, x2, y2, impacts):
        self.debut = (x1, y1)
        self.fin = (x2, y2)
        self.impacts = impacts  # [(x, y), ...] des ennemis touchés : une onde s'y élargit
        self.age = 0.0


def _distance_au_segment(px, py, x1, y1, x2, y2):
    """Distance du point (px, py) au segment (x1, y1) -> (x2, y2)."""
    dx, dy = x2 - x1, y2 - y1
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


class Balle:
    """Un tir de tourelle : file en ligne droite (pixels monde) jusqu'à toucher un
    alien ou dépasser la portée de sa tourelle."""

    def __init__(self, x, y, angle, modele):
        self.x = x
        self.y = y
        self.modele = modele  # sa tourelle : vitesse, dégâts, dessin
        self.vx = math.cos(angle) * modele.VITESSE_TIR
        self.vy = math.sin(angle) * modele.VITESSE_TIR
        self.reste = modele.PORTEE * 1.5  # distance qu'il lui reste à parcourir


class _StockMunitions:
    """Vue « munitions entières » sur les tirs d'une tourelle, pour son panneau d'1 case."""

    def __init__(self, tourelle):
        self.tourelle = tourelle

    def __getitem__(self, ressource):
        return self.tourelle.tirs // self.tourelle.modele.TIRS_PAR_MUNITION

    def __setitem__(self, ressource, quantite):
        par_munition = self.tourelle.modele.TIRS_PAR_MUNITION
        reste = self.tourelle.tirs % par_munition  # tirs d'une munition entamée
        self.tourelle.tirs = quantite * par_munition + reste


class Tourelle:
    """Une tourelle posée : elle tourne vers l'alien le plus proche dans sa portée et
    tire quand elle le vise. Son inventaire (PanneauStock) a une seule case : sa munition."""

    def __init__(self, tx, ty, tilewidth, tileheight, modele=construction_tourelle):
        self.modele = modele               # tourelle, canon électromagnétique ou plasma (ses réglages)
        self.titre = modele.TITRE
        self.cases = [] if modele.MUNITION is None else [modele.MUNITION]  # (plasma : rien à charger)
        self.stock = _StockMunitions(self)
        self.laser = None                  # (tir "laser") l'ennemi sur lequel le laser est braqué
        self.tx = tx
        self.ty = ty
        self.x = (tx + 0.5) * tilewidth    # centre, en pixels monde
        self.y = (ty + 0.5) * tileheight
        self.angle = -math.pi / 2          # radians (0 = droite, y vers le bas) : regarde en haut
        self.chrono = 0                    # temps avant le prochain tir
        self.tirs = 0                      # munitions en réserve, en nombre de tirs

    def charger(self, inventaire):
        """Charge dans la tourelle les munitions de l'inventaire (autant qu'elle peut en
        garder). Renvoie le nombre de munitions chargées."""
        if self.modele.MUNITION is None:
            return 0
        place = (self.modele.STOCK_MAX - self.tirs) // self.modele.TIRS_PAR_MUNITION
        n = min(inventaire.compter(self.modele.MUNITION), place)
        if n > 0:
            inventaire.retirer(self.modele.MUNITION, n)
            self.tirs += n * self.modele.TIRS_PAR_MUNITION
        return max(n, 0)

    def _cible(self, aliens):
        """L'alien le plus proche dans la portée (ou None)."""
        meilleur, distance_min = None, self.modele.PORTEE
        for alien in aliens:
            distance = math.hypot(alien.x - self.x, alien.y - self.y)
            if distance <= distance_min:
                meilleur, distance_min = alien, distance
        return meilleur

    def update(self, dt, aliens, balles, rayons):
        self.chrono = max(0, self.chrono - dt)
        cible = self._cible(aliens)
        self.laser = None
        if cible is None:
            return
        voulu = math.atan2(cible.y - self.y, cible.x - self.x)
        ecart = (voulu - self.angle + math.pi) % (2 * math.pi) - math.pi  # dans [-pi, pi)
        pas = math.radians(self.modele.ROTATION) * dt
        self.angle += max(-pas, min(pas, ecart))
        ecart -= max(-pas, min(pas, ecart))  # (ce qu'il reste à tourner)
        # elle suit toujours l'alien ; sans munitions (voir charger) elle ne tire pas. Elle tire quand
        # elle le vise assez bien pour le toucher (plus il est loin, plus il faut viser juste)
        distance = math.hypot(cible.x - self.x, cible.y - self.y)
        precision = min(math.radians(5), math.atan2(RAYON_TOUCHE / 2, distance))
        if self.modele.TIR == "laser":
            # le laser reste braqué sur la cible tant qu'elle est visée, et la ronge à chaque CADENCE
            if abs(ecart) < precision:
                self.laser = cible
                if self.chrono < 1e-6:  # (pas == 0 : les arrondis feraient attendre une image de plus)
                    self.chrono = self.modele.CADENCE
                    cible.subir(self.modele.DEGATS)
            return
        if self.tirs > 0 and abs(ecart) < precision and self.chrono == 0:
            self.chrono = self.modele.CADENCE
            self.tirs -= 1
            x0 = self.x + math.cos(self.angle) * self.modele.PORTEE_CANON  # bout du canon
            y0 = self.y + math.sin(self.angle) * self.modele.PORTEE_CANON
            if self.modele.TIR == "rayon":
                self._tirer_rayon(x0, y0, aliens, rayons)
            else:
                balles.append(Balle(x0, y0, self.angle, self.modele))

    def _tirer_rayon(self, x0, y0, aliens, rayons):
        """Rayon instantané jusqu'à la portée : chaque ennemi sur sa ligne est touché."""
        x1 = self.x + math.cos(self.angle) * self.modele.PORTEE
        y1 = self.y + math.sin(self.angle) * self.modele.PORTEE
        impacts = []
        for alien in aliens:
            if _distance_au_segment(alien.x, alien.y, x0, y0, x1, y1) <= RAYON_TOUCHE:
                alien.subir(self.modele.DEGATS)
                impacts.append((alien.x, alien.y))
        rayons.append(Rayon(x0, y0, x1, y1, impacts))


class Tourelles:
    """Les tourelles du monde : une `Tourelle` par tuile de tourelle (ou de canon) posée, et leurs tirs."""

    def __init__(self):
        self.tourelles = {}  # (tx, ty) -> Tourelle
        self.balles = []
        self.rayons = []     # rayons du canon électromagnétique en train de s'effacer
        self.images = {}     # modèle -> (image du haut, décalage du pivot par rapport au centre de l'image)
        for modele in MODELES:
            image = pygame.image.load(modele.IMAGE_HAUT).convert_alpha()
            image = pygame.transform.rotate(image, modele.ROTATION_IMAGE)  # canon vers la droite
            image = pygame.transform.smoothscale(image, (modele.TAILLE_IMAGE_HAUT, modele.TAILLE_IMAGE_HAUT))
            decalage = ((modele.PIVOT_HAUT[0] - 0.5) * modele.TAILLE_IMAGE_HAUT,
                        (modele.PIVOT_HAUT[1] - 0.5) * modele.TAILLE_IMAGE_HAUT)
            self.images[modele] = (image, decalage)
        self.police = pygame.font.Font(None, 40)

    # ---- apparition / disparition ----
    def scan(self, game_map):
        """Crée une Tourelle pour chaque tuile de tourelle de la carte qui n'en a pas
        encore (monde chargé : les tourelles posées avant reviennent d'elles-mêmes)."""
        taille = game_map.chunk_size
        for (cx, cy), grille in game_map.layers[construction_tourelle.CALQUE].items():
            for y, ligne in enumerate(grille):
                for x, gid in enumerate(ligne):
                    if gid in MODELE_DU_GID:
                        tx, ty = cx * taille + x, cy * taille + y
                        self.ajouter(tx, ty, game_map)

    def ajouter(self, tx, ty, game_map):
        """Une tourelle sur la case (tx, ty) : son modèle est celui de la tuile posée là."""
        if (tx, ty) not in self.tourelles:
            gid = game_map.get_layer_gid(construction_tourelle.CALQUE, tx, ty)
            modele = MODELE_DU_GID.get(gid, construction_tourelle)
            self.tourelles[(tx, ty)] = Tourelle(tx, ty, game_map.tilewidth, game_map.tileheight, modele)

    def deplacer(self, trajet, pixels):
        """La base a bougé : {ancienne case: nouvelle case} ; les tourelles suivent (déplacement en pixels)."""
        anciennes = self.tourelles
        self.tourelles = {}
        for cle, tourelle in anciennes.items():
            tourelle.tx, tourelle.ty = trajet.get(cle, cle)
            if cle in trajet:
                tourelle.x += pixels[0]
                tourelle.y += pixels[1]
            self.tourelles[(tourelle.tx, tourelle.ty)] = tourelle

    def retirer(self, tx, ty, inventaire):
        """La tourelle part : ses munitions non tirées vont dans l'inventaire (celles qui
        ne rentrent pas sont perdues). Renvoie la tourelle retirée (ou None)."""
        tourelle = self.tourelles.pop((tx, ty), None)
        if tourelle is not None and tourelle.tirs >= tourelle.modele.TIRS_PAR_MUNITION:
            inventaire.ajouter_objet(tourelle.modele.MUNITION, tourelle.tirs // tourelle.modele.TIRS_PAR_MUNITION)
        return tourelle

    # ---- tir ----
    def update(self, dt, groupes, energie):
        """Sans assez d'énergie, les tourelles ne bougent ni ne tirent. `groupes` : les objets
        qui ont une liste d'ennemis (`.liste` : aliens, vaisseaux...)."""
        ennemis = [e for groupe in groupes for e in groupe.liste]
        for tourelle in self.tourelles.values():
            if energie.suffisante:
                tourelle.update(dt, ennemis, self.balles, self.rayons)
            else:
                tourelle.laser = None  # plus d'énergie : le laser s'éteint
        for rayon in self.rayons:
            rayon.age += dt
        self.rayons = [rayon for rayon in self.rayons if rayon.age < DUREE_RAYON]

        restantes = []
        for balle in self.balles:
            balle.x += balle.vx * dt
            balle.y += balle.vy * dt
            balle.reste -= balle.modele.VITESSE_TIR * dt
            touche = next((a for a in ennemis
                           if math.hypot(a.x - balle.x, a.y - balle.y) <= RAYON_TOUCHE), None)
            if touche is not None:
                touche.subir(balle.modele.DEGATS)
            elif balle.reste > 0:
                restantes.append(balle)
        self.balles = restantes
        for groupe in groupes:
            groupe.liste = [a for a in groupe.liste if not a.mort]  # les ennemis tués disparaissent

    # ---- souris ----
    def sous_souris(self, game_map, camera, pos_vue):
        return self.tourelles.get(case_sous_souris(game_map, camera, pos_vue))

    # ---- sauvegarde ----
    def exporter(self):
        return [{"tx": t.tx, "ty": t.ty, "tirs": t.tirs} for t in self.tourelles.values()]

    def importer(self, donnees, game_map):
        """(le modèle de chaque tourelle se retrouve avec la tuile de la carte, déjà chargée)"""
        self.tourelles = {}
        for d in donnees:
            self.ajouter(d["tx"], d["ty"], game_map)
            self.tourelles[(d["tx"], d["ty"])].tirs = d["tirs"]

    # ---- dessin ----
    def draw_monde(self, vue, camera_offset, propulsion=None):
        """La tuile (le socle) est dessinée par la carte ; on ajoute ici le canon qui
        tourne, les munitions restantes (en rouge quand il n'y en a plus) et les tirs.
        `propulsion` : la base poussée qui glisse (ses tourelles glissent avec elle)."""
        lasers = []  # (bout du canon, cible) des lasers allumés, dessinés par-dessus les tourelles
        for tourelle in self.tourelles.values():
            image, decalage = self.images[tourelle.modele]
            image = pygame.transform.rotate(image, -math.degrees(tourelle.angle))
            offset = propulsion.offset_de(camera_offset, (tourelle.tx, tourelle.ty)) if propulsion else camera_offset
            centre = (tourelle.x - offset[0], tourelle.y - offset[1])
            # le corps (pivot) reste sur la case : on décale l'image de son pivot tourné
            cos, sin = math.cos(tourelle.angle), math.sin(tourelle.angle)
            ox = decalage[0] * cos - decalage[1] * sin
            oy = decalage[0] * sin + decalage[1] * cos
            vue.blit(image, image.get_rect(center=(centre[0] - ox, centre[1] - oy)))
            if tourelle.modele.MUNITION is not None:  # (plasma : pas de munitions à compter)
                couleur = tourelle.modele.COULEUR_TIR if tourelle.tirs > 0 else COULEUR_VIDE
                texte = self.police.render(str(tourelle.tirs), True, couleur)
                vue.blit(texte, texte.get_rect(midbottom=(centre[0], centre[1] - 50)))
            if tourelle.laser is not None and not tourelle.laser.mort:
                bout = (centre[0] + cos * tourelle.modele.PORTEE_CANON, centre[1] + sin * tourelle.modele.PORTEE_CANON)
                cible = (tourelle.laser.x - camera_offset[0], tourelle.laser.y - camera_offset[1])
                lasers.append((bout, cible))
        for balle in self.balles:
            pygame.draw.circle(vue, balle.modele.COULEUR_TIR,
                               (round(balle.x - camera_offset[0]), round(balle.y - camera_offset[1])), RAYON_BALLE)
        for rayon in self.rayons:
            self._dessiner_rayon(vue, camera_offset, rayon)
        for bout, cible in lasers:
            self._dessiner_laser(vue, bout, cible)

    @staticmethod
    def _dessiner_laser(vue, a, b):
        """Le laser plasma, de `a` (bout du canon) à `b` (la cible), en pixels de la vue : des couches
        turquoise autour d'un cœur blanc qui « respirent », deux filaments de plasma qui ondulent autour en
        avançant vers la cible, une lueur au bout du canon et une boule d'énergie qui crépite sur la cible.
        Dessiné sur une surface transparente juste assez grande (la partie du laser dans la vue)."""
        temps = pygame.time.get_ticks() / 1000
        pouls = 0.85 + 0.15 * math.sin(temps * 18)  # le laser vibre
        marge = COUCHES_LASER[0][0] + AMPLITUDE_ONDE + 50
        zone = pygame.Rect(min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]), abs(b[1] - a[1]))
        zone = zone.inflate(2 * marge, 2 * marge).clip(vue.get_rect())
        longueur = math.hypot(b[0] - a[0], b[1] - a[1])
        if zone.width <= 0 or zone.height <= 0 or longueur < 1:
            return
        calque = pygame.Surface(zone.size, pygame.SRCALPHA)
        a = (a[0] - zone.x, a[1] - zone.y)
        b = (b[0] - zone.x, b[1] - zone.y)

        for largeur, couleur, opacite in COUCHES_LASER[:2]:  # le halo (le cœur passe par-dessus les filaments)
            pygame.draw.line(calque, (*couleur, round(opacite * pouls)), a, b, max(1, round(largeur * pouls)))

        # deux filaments en opposition qui ondulent le long du laser et avancent vers la cible
        ux, uy = (b[0] - a[0]) / longueur, (b[1] - a[1]) / longueur
        nx, ny = -uy, ux
        for phase in (0, math.pi):
            points = []
            for k in range(int(longueur // PAS_ONDE) + 1):
                d = min(longueur, k * PAS_ONDE)
                ecart = AMPLITUDE_ONDE * math.sin(2 * math.pi * d / LONGUEUR_ONDE - temps * 25 + phase)
                points.append((a[0] + ux * d + nx * ecart, a[1] + uy * d + ny * ecart))
            if len(points) > 1:
                pygame.draw.lines(calque, (120, 255, 230, 200), False, points, 2)
        for largeur, couleur, opacite in COUCHES_LASER[2:]:  # le cœur
            pygame.draw.line(calque, (*couleur, round(opacite * pouls)), a, b, max(1, round(largeur * pouls)))

        # lueur au bout du canon, boule d'énergie et étincelles sur la cible
        for r, couleur, opacite in ((20, (40, 240, 210), 90), (10, (180, 255, 245), 200), (4, (255, 255, 255), 255)):
            pygame.draw.circle(calque, (*couleur, opacite), a, round(r * pouls))
        for r, couleur, opacite in ((34, (20, 200, 180), 60), (20, (60, 250, 220), 140), (9, (255, 255, 255), 255)):
            pygame.draw.circle(calque, (*couleur, opacite), b, round(r * pouls))
        for _ in range(5):
            angle = random.uniform(0, 2 * math.pi)
            r1, r2 = random.uniform(8, 16), random.uniform(22, 42)
            pygame.draw.line(calque, (200, 255, 245, 200), (b[0] + math.cos(angle) * r1, b[1] + math.sin(angle) * r1),
                             (b[0] + math.cos(angle) * r2, b[1] + math.sin(angle) * r2), 2)
        vue.blit(calque, zone.topleft)

    @staticmethod
    def _dessiner_rayon(vue, camera_offset, rayon):
        """Le rayon bleu : un halo en plusieurs couches autour d'un cœur blanc, deux arcs électriques qui
        crépitent autour (redessinés au hasard à chaque image), un éclair à la bouche du canon et une onde
        sur chaque ennemi touché ; le tout s'efface (et s'affine) en DUREE_RAYON secondes. Dessiné sur une
        surface transparente juste assez grande (la partie du rayon dans la vue)."""
        f = 1 - rayon.age / DUREE_RAYON  # 1 au tir, 0 quand il a disparu
        (x1, y1), (x2, y2) = rayon.debut, rayon.fin
        x1, y1, x2, y2 = x1 - camera_offset[0], y1 - camera_offset[1], x2 - camera_offset[0], y2 - camera_offset[1]
        marge = COUCHES_RAYON[0][0] + ECART_ARC + 60
        zone = pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)).inflate(2 * marge, 2 * marge)
        zone = zone.clip(vue.get_rect())
        if zone.width <= 0 or zone.height <= 0:
            return
        calque = pygame.Surface(zone.size, pygame.SRCALPHA)
        a, b = (x1 - zone.x, y1 - zone.y), (x2 - zone.x, y2 - zone.y)

        for largeur, couleur, opacite in COUCHES_RAYON:
            pygame.draw.line(calque, (*couleur, round(opacite * f)), a, b, max(1, round(largeur * (0.4 + 0.6 * f))))

        # arcs électriques : des zigzags de part et d'autre du rayon
        longueur = math.hypot(b[0] - a[0], b[1] - a[1])
        ux, uy = (b[0] - a[0]) / longueur, (b[1] - a[1]) / longueur  # le long du rayon
        nx, ny = -uy, ux                                             # en travers
        for _ in range(2):
            points = []
            for k in range(int(longueur // PAS_ARC) + 1):
                d = min(longueur, k * PAS_ARC + random.uniform(-10, 10))
                ecart = random.uniform(-ECART_ARC, ECART_ARC) * (0.5 + f)
                points.append((a[0] + ux * d + nx * ecart, a[1] + uy * d + ny * ecart))
            if len(points) > 1:
                pygame.draw.lines(calque, (*COULEUR_ARC, round(200 * f)), False, points, 2)

        # éclair à la bouche du canon
        for r, couleur, opacite in ((30, (40, 140, 255), 90), (18, (90, 200, 255), 170), (8, (230, 250, 255), 255)):
            pygame.draw.circle(calque, (*couleur, round(opacite * f)), a, max(1, round(r * (0.5 + 0.5 * f))))
        # une onde qui s'élargit sur chaque ennemi touché
        for ix, iy in rayon.impacts:
            centre = (ix - camera_offset[0] - zone.x, iy - camera_offset[1] - zone.y)
            r = round(12 + 50 * (1 - f))
            pygame.draw.circle(calque, (120, 210, 255, round(220 * f)), centre, r, 4)
            pygame.draw.circle(calque, (255, 255, 255, round(255 * f)), centre, max(1, round(10 * f)))
        vue.blit(calque, zone.topleft)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
