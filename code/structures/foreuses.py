import math

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import foreuse as modele
from monde.cristaux import MINERAIS
from monde.map import CALQUES_SAUVES
from structures.coffres import Coffre
from systeme.settings import (COULEUR_ALERTE, COULEUR_DECONSTRUCTION, COULEUR_DECONSTRUCTION_BORDURE, COULEUR_ZONE,
                              COULEUR_ZONE_BORDURE, COULEUR_ZONE_REFUSEE, COULEUR_ZONE_REFUSEE_BORDURE)

# =============================================
# ==== Les foreuses posées sur les planètes (voir construction/foreuse.py). Comme dans Factorio, chacune
# ==== est posée sur un gisement de minerai (pieds en bas au milieu de sa case, comme les arbres) et en
# ==== extrait le minerai tout seule, dans son inventaire ; le gisement rétrécit, et disparaît quand il est
# ==== vide (la foreuse s'arrête). Elle tremble tant qu'elle creuse.
# =============================================
COULEUR_BARRE = (240, 150, 40)
DEVANT_GISEMENT = 3   # (pixels) la foreuse est dessinée par-dessus son gisement (voir images)


class Foreuse:
    def __init__(self, tx, ty, carte, minerai):
        self.tx = tx
        self.ty = ty
        self.carte = carte          # nom de la carte (ex : "terre.tmx") : le gisement est sur elle
        self.minerai = minerai      # le gisement sous elle ("fer"... : voir MINERAIS), None s'il n'y en a pas
        self.coffre = Coffre(tx, ty, modele)  # ce qu'elle a extrait
        self.chrono = 0.0           # secondes depuis le dernier morceau extrait

    @property
    def ressource(self):
        return MINERAIS[self.minerai][0] if self.minerai in MINERAIS else None

    def travaille(self, cristaux):
        """True tant que son gisement n'est pas vide et qu'elle a de la place pour son minerai."""
        return (self.ressource is not None and cristaux.restants(self.carte, self.tx, self.ty, self.minerai) > 0
                and self.coffre._ranger_sortie([(self.ressource, 1)], essai=True))

    def creuser(self, dt, cristaux):
        if not self.travaille(cristaux):
            self.chrono = 0.0  # (pleine ou gisement vide : pas de temps d'avance)
            return
        self.chrono += dt
        while self.chrono >= modele.DELAI and self.travaille(cristaux):
            self.chrono -= modele.DELAI
            cristaux.miner(self.carte, self.tx, self.ty, self.minerai)
            self.coffre._ranger_sortie([(self.ressource, 1)])


class Foreuses:
    def __init__(self, cristaux):
        """`cristaux` : les cristaux et gisements des planètes (ce qui reste dans chaque gisement)."""
        self.cristaux = cristaux
        self.par_carte = {}   # carte (ex : "terre.tmx") -> {(tx, ty): Foreuse}
        self.temps = 0.0
        self.message = ""
        self.message_fin = 0
        self.police = pygame.font.Font(None, 30)
        self._image = None

    def _dire(self, texte):
        self.message = texte
        self.message_fin = pygame.time.get_ticks() + 2000

    # ---- géométrie ----
    @staticmethod
    def _pied(carte, tx, ty):
        return (tx + 0.5) * carte.tilewidth, (ty + 1) * carte.tileheight

    def _socle(self, carte, tx, ty):
        """Le rectangle au sol qui bloque le héros (pixels monde)."""
        x, y = self._pied(carte, tx, ty)
        rect = pygame.Rect(0, 0, *modele.SOCLE)
        rect.midbottom = (round(x), round(y))
        return rect

    def _contour(self, carte, tx, ty):
        """Le rectangle de l'image (pixels monde) : pour viser la foreuse avec la souris."""
        image = self.image()
        x, y = self._pied(carte, tx, ty)
        return pygame.Rect(round(x - image.get_width() / 2), round(y - image.get_height() * modele.PIED),
                           image.get_width(), image.get_height())

    def _liste(self, carte):
        return self.par_carte.get(carte.nom, {})

    # ---- gisements ----
    def _gisement(self, carte, tx, ty):
        """Le minerai du gisement (pas vide) de la case (tx, ty) : "fer"..., ou None s'il n'y en a pas."""
        chunk = (tx // carte.chunk_size, ty // carte.chunk_size)
        for x, y, sorte in carte.cristaux(chunk):
            if (x, y) == (tx, ty) and sorte in MINERAIS and self.cristaux.restants(carte.nom, tx, ty, sorte) > 0:
                return sorte
        return None

    def _case_visee(self, carte, monde_x, monde_y):
        """La case sous la souris ; la souris sur l'image d'un gisement (elle dépasse de sa case) : la sienne."""
        tx, ty = int(monde_x // carte.tilewidth), int(monde_y // carte.tileheight)
        for x, y in ((tx, ty), (tx, ty + 1), (tx - 1, ty), (tx + 1, ty), (tx - 1, ty + 1), (tx + 1, ty + 1)):
            if self._gisement(carte, x, y) is not None:
                px, py = self._pied(carte, x, y)
                if abs(monde_x - px) <= carte.tilewidth * 0.55 and py - carte.tileheight <= monde_y <= py:
                    return x, y
        return tx, ty

    # ---- poser / viser / enlever ----
    @staticmethod
    def _sur_construction(carte, socle):
        """True si le socle touche une case où une construction est posée (table de craft, base...)."""
        return any(carte.get_layer_gid(nom, x, y)
                   for nom in CALQUES_SAUVES
                   for x in range(socle.left // carte.tilewidth, (socle.right - 1) // carte.tilewidth + 1)
                   for y in range(socle.top // carte.tileheight, (socle.bottom - 1) // carte.tileheight + 1))

    def _refus(self, carte, tx, ty, hero):
        """Pourquoi la foreuse ne peut pas être posée sur la case (tx, ty) ("" : elle peut)."""
        if carte is None or carte.nom not in modele.PLANETES:
            return "La foreuse se pose sur un gisement de la Terre ou de Mars"
        if (tx, ty) in self._liste(carte):
            return "Il y a déjà une foreuse sur ce gisement"
        if self._gisement(carte, tx, ty) is None:
            return "Pose-la sur un gisement de minerai"
        hx, hy = hero.hitbox(hero.x, hero.y).center
        x, y = self._pied(carte, tx, ty)
        if math.hypot(x - hx, y - hy) > modele.PORTEE:
            return "Trop loin"
        socle = self._socle(carte, tx, ty)
        if carte.bloque(socle) or self._sur_construction(carte, socle):
            return "Pas de place ici"
        if socle.colliderect(hero.hitbox(hero.x, hero.y)):
            return "Pas sur toi"
        return ""

    def poser(self, carte, monde_x, monde_y, hero):
        """Pose une foreuse sur le gisement visé. Renvoie True si c'est fait (sinon un message dit pourquoi)."""
        tx, ty = self._case_visee(carte, monde_x, monde_y) if carte is not None else (0, 0)
        refus = self._refus(carte, tx, ty, hero)
        if refus:
            self._dire(refus)
            return False
        self.par_carte.setdefault(carte.nom, {})[(tx, ty)] = Foreuse(tx, ty, carte.nom, self._gisement(carte, tx, ty))
        self._mettre_obstacles(carte)
        return True

    def sous_souris(self, carte, monde_x, monde_y):
        for foreuse in self._liste(carte).values():
            if self._contour(carte, foreuse.tx, foreuse.ty).collidepoint(monde_x, monde_y):
                return foreuse
        return None

    def enlever(self, carte, foreuse, inventaire):
        """Outil de déconstruction : la foreuse retourne dans l'inventaire, avec ce qu'elle a extrait (ce qui ne
        rentre pas reste dedans, et elle aussi). Renvoie True si elle est enlevée."""
        for i, objet in enumerate(foreuse.coffre.objets):
            if objet is not None:
                foreuse.coffre.nombres[i] = inventaire.ajouter_objet(objet, foreuse.coffre.nombres[i])
                if not foreuse.coffre.nombres[i]:
                    foreuse.coffre.objets[i] = None
        if not foreuse.coffre.vide or inventaire.place_pour(modele) < 1:
            self._dire("Inventaire plein")
            return False
        inventaire.ajouter_objet(modele)
        del self.par_carte[carte.nom][(foreuse.tx, foreuse.ty)]
        self._mettre_obstacles(carte)
        return True

    def _mettre_obstacles(self, carte):
        """Les socles des foreuses de cette carte bloquent le héros (voir Map.bloque)."""
        carte.obstacles = [self._socle(carte, f.tx, f.ty) for f in self._liste(carte).values()]

    # ---- temps ----
    def update(self, dt, carte=None):
        """Toutes les foreuses creusent (même sur les planètes où l'on n'est pas). `carte` : la planète où l'on
        est (ses foreuses bloquent le héros)."""
        self.temps += dt
        for foreuses in self.par_carte.values():
            for foreuse in foreuses.values():
                foreuse.creuser(dt, self.cristaux)
        if carte is not None:
            for foreuse in self._liste(carte).values():
                if foreuse.minerai is None:  # (posée avant les gisements : celui qui est sous elle, s'il y en a un)
                    foreuse.minerai = self._gisement(carte, foreuse.tx, foreuse.ty)
            if len(carte.obstacles) != len(self._liste(carte)):
                self._mettre_obstacles(carte)

    # ---- dessin ----
    def image(self):
        if self._image is None:
            image = pygame.image.load(modele.ICONE).convert_alpha()
            largeur = round(image.get_width() * modele.HAUTEUR / image.get_height())
            self._image = pygame.transform.smoothscale(image, (largeur, modele.HAUTEUR))
        return self._image

    def images(self, carte, camera):
        """[(pied, x, image), ...] des foreuses de cette carte : le décor les dessine avec les arbres, triées par
        pied (voir Decors.draw), juste devant leur gisement. Celles qui travaillent tremblent un peu."""
        liste = []
        for foreuse in self._liste(carte).values():
            x, pied = self._pied(carte, foreuse.tx, foreuse.ty)
            pied += DEVANT_GISEMENT
            if foreuse.travaille(self.cristaux):
                x += math.sin(self.temps * 45 + foreuse.tx) * 1.5
                pied += math.sin(self.temps * 37 + foreuse.ty) * 1.0
            liste.append((pied, x, self.image()))
        return liste

    def draw_barres(self, vue, camera, carte):
        """Au-dessus de chaque foreuse : l'avancement du morceau en cours (rien si elle est arrêtée)."""
        for foreuse in self._liste(carte).values():
            if not foreuse.travaille(self.cristaux):
                continue
            contour = self._contour(carte, foreuse.tx, foreuse.ty).move(-camera.x, -camera.y)
            barre = pygame.Rect(0, 0, 90, 10)
            barre.midbottom = (contour.centerx, contour.top + 6)
            pygame.draw.rect(vue, (20, 20, 30), barre, border_radius=4)
            plein = barre.copy()
            plein.width = round(barre.width * min(1.0, foreuse.chrono / modele.DELAI))
            pygame.draw.rect(vue, COULEUR_BARRE, plein, border_radius=4)
            pygame.draw.rect(vue, (150, 150, 170), barre, 1, border_radius=4)

    def apercu(self, vue, camera, carte, monde_x, monde_y, hero):
        """La foreuse sélectionnée, transparente, sur le gisement visé : socle vert (pose possible) ou rouge."""
        tx, ty = self._case_visee(carte, monde_x, monde_y)
        ok = not self._refus(carte, tx, ty, hero)
        couleur, bordure = (COULEUR_ZONE, COULEUR_ZONE_BORDURE) if ok else (COULEUR_ZONE_REFUSEE,
                                                                            COULEUR_ZONE_REFUSEE_BORDURE)
        self._cadre(vue, self._socle(carte, tx, ty).move(-camera.x, -camera.y), couleur, bordure)
        image = self.image().copy()
        image.set_alpha(170)
        vue.blit(image, self._contour(carte, tx, ty).move(-camera.x, -camera.y))

    def apercu_enlever(self, vue, camera, carte, monde_x, monde_y):
        """Outil de déconstruction : entoure (en orange) la foreuse sous la souris. True s'il y en a une."""
        foreuse = self.sous_souris(carte, monde_x, monde_y)
        if foreuse is None:
            return False
        self._cadre(vue, self._contour(carte, foreuse.tx, foreuse.ty).move(-camera.x, -camera.y),
                    COULEUR_DECONSTRUCTION, COULEUR_DECONSTRUCTION_BORDURE)
        return True

    @staticmethod
    def _cadre(vue, rect, couleur, bordure):
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        surface.fill(couleur)
        vue.blit(surface, rect)
        pygame.draw.rect(vue, bordure, rect, 3)

    def draw_hud(self, screen):
        if self.message and pygame.time.get_ticks() < self.message_fin:
            texte = self.police.render(self.message, True, COULEUR_ALERTE)
            screen.blit(texte, texte.get_rect(midbottom=(screen.get_width() // 2, screen.get_height() - 140)))

    # ---- sauvegarde ----
    def exporter(self, ids):
        return {nom: [{"tx": f.tx, "ty": f.ty, "minerai": f.minerai, "chrono": f.chrono,
                       "objets": ids(f.coffre.objets), "nombres": f.coffre.nombres}
                      for f in foreuses.values()]
                for nom, foreuses in self.par_carte.items()}

    def importer(self, donnees, objets):
        self.par_carte = {}
        for nom, liste in donnees.items():
            for d in liste:
                # (absent des anciennes sauvegardes : retrouvé dans update, quand on est sur la planète)
                foreuse = Foreuse(d["tx"], d["ty"], nom, d.get("minerai"))
                foreuse.chrono = d.get("chrono", 0.0)
                foreuse.coffre.objets[:] = [objets.get(i) for i in d["objets"]]
                foreuse.coffre.nombres[:] = d["nombres"]
                self.par_carte.setdefault(nom, {})[(foreuse.tx, foreuse.ty)] = foreuse


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
