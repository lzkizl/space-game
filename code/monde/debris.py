import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import (ASTEROIDES_FOND_CHAMP_CHANCE, ASTEROIDES_FOND_CHAMP_FACTEUR, ASTEROIDES_FOND_IMAGE,
                              ASTEROIDES_FOND_LUMIERE, ASTEROIDES_FOND_PAR_CHUNK, ASTEROIDES_FOND_PROFONDEUR,
                              ASTEROIDES_FOND_TAILLE, DEBRIS_CHAMP_CHANCE, DEBRIS_CHAMP_FACTEUR, DEBRIS_DOSSIER,
                              DEBRIS_LUMIERE, DEBRIS_PAR_CHUNK, DEBRIS_PROFONDEUR, DEBRIS_TAILLE)

# =============================================
# ==== Décor de l'espace : du décor fixe placé partout et à l'infini à partir de la graine du
# ==== monde, morceau de 16x16 cases par morceau (même graine = même décor). Deux couches :
# ==== des astéroïdes lointains, qui défilent plus lentement (effet de profondeur), et des débris
# ==== de vaisseaux dans le monde. Tout est dessiné derrière la carte : visible dans le vide,
# ==== caché par les bases. On ne peut ni les toucher ni les ramasser.
# =============================================
GRAINE_PAR_DEFAUT = "monde"  # mondes sans graine (anciennes sauvegardes)
CACHE_MAX = 300              # morceaux gardés en mémoire par couche (au-delà : on ne garde que les visibles)


def _charger(chemin):
    """Image sans son bord transparent (pour que la taille voulue soit celle du dessin)."""
    image = pygame.image.load(chemin).convert_alpha()
    return image.subsurface(image.get_bounding_rect()).copy()


def _sur_un_disque(px, py, image, disques):
    """True si l'image posée en (px, py) touche un des disques (x, y, rayon)."""
    demi_l, demi_h = image.get_width() / 2, image.get_height() / 2
    cx, cy = px + demi_l, py + demi_h
    for x, y, rayon in disques:
        r = rayon + max(demi_l, demi_h)
        if (cx - x) ** 2 + (cy - y) ** 2 < r * r:
            return True
    return False


class _Couche:
    """Une couche de décor : des images tirées au hasard, de tailles, d'angles et de luminosités
    variés, qui défile à `profondeur` fois la vitesse du monde."""

    def __init__(self, nom, images, par_chunk, champ_chance, champ_facteur, taille, lumiere, profondeur):
        self.nom = nom
        self.images = images
        self.par_chunk = par_chunk
        self.champ_chance = champ_chance
        self.champ_facteur = champ_facteur
        self.taille = taille
        self.lumiere = lumiere
        self.profondeur = profondeur
        self._morceaux = {}  # (graine, chunk_x, chunk_y) -> [(x, y, image)] en pixels de la couche

    def _generer(self, graine, cx, cy, taille_px):
        """Le décor d'un morceau (tiré de la graine : toujours le même)."""
        tirage = random.Random(f"{self.nom}:{graine}:{cx}:{cy}")
        nombre = tirage.randint(*self.par_chunk)
        if tirage.random() < self.champ_chance:
            nombre *= self.champ_facteur
        elements = []
        mini, maxi = self.taille
        for _ in range(nombre):
            source = tirage.choice(self.images)
            proportion = tirage.random() ** 1.8  # beaucoup de petits, quelques gros
            cote = mini + (maxi - mini) * proportion  # (plus grande dimension de l'image)
            echelle = cote / max(source.get_size())
            image = pygame.transform.smoothscale(source, (max(1, round(source.get_width() * echelle)),
                                                          max(1, round(source.get_height() * echelle))))
            image = pygame.transform.rotate(image, tirage.uniform(0, 360))
            gris = round(255 * (self.lumiere[0] + (self.lumiere[1] - self.lumiere[0]) * proportion))
            image.fill((gris, gris, gris), special_flags=pygame.BLEND_RGB_MULT)
            x = (cx + tirage.random()) * taille_px
            y = (cy + tirage.random()) * taille_px
            elements.append((x - image.get_width() / 2, y - image.get_height() / 2, image))
        elements.sort(key=lambda e: e[2].get_width())  # les petits (lointains) d'abord, les gros par-dessus
        return elements

    def draw(self, surface, camera, graine, taille_px, exclus=()):
        """`exclus` : disques (x, y, rayon) de la vue où rien n'est dessiné (une planète)."""
        # coin haut gauche de la vue dans la couche : une couche lointaine défile moins vite quand la
        # caméra se déplace, mais suit le zoom comme le monde (sinon elle glisserait en zoomant)
        retard = 1 - self.profondeur
        x0 = camera.x - retard * getattr(camera, "deplacement_x", camera.x)
        y0 = camera.y - retard * getattr(camera, "deplacement_y", camera.y)
        marge = self.taille[1]  # un élément au bord d'un morceau peut déborder sur la vue
        visibles = set()
        for cy in range(int((y0 - marge) // taille_px), int((y0 + camera.screen_height + marge) // taille_px) + 1):
            for cx in range(int((x0 - marge) // taille_px), int((x0 + camera.screen_width + marge) // taille_px) + 1):
                cle = (graine, cx, cy)
                visibles.add(cle)
                if cle not in self._morceaux:
                    self._morceaux[cle] = self._generer(graine, cx, cy, taille_px)
                for x, y, image in self._morceaux[cle]:
                    px, py = round(x - x0), round(y - y0)
                    if exclus and _sur_un_disque(px, py, image, exclus):
                        continue  # (sur une planète : on ne le dessine pas)
                    surface.blit(image, (px, py))
        if len(self._morceaux) > CACHE_MAX:
            self._morceaux = {cle: e for cle, e in self._morceaux.items() if cle in visibles}


class Debris:
    def __init__(self):
        self.fond = _Couche("asteroides", [_charger(ASTEROIDES_FOND_IMAGE)], ASTEROIDES_FOND_PAR_CHUNK,
                            ASTEROIDES_FOND_CHAMP_CHANCE, ASTEROIDES_FOND_CHAMP_FACTEUR, ASTEROIDES_FOND_TAILLE,
                            ASTEROIDES_FOND_LUMIERE, ASTEROIDES_FOND_PROFONDEUR)
        images = [_charger(chemin) for chemin in sorted(Path(DEBRIS_DOSSIER).glob("*.png"))]  # (tri : même tirage)
        self.epaves = _Couche("debris", images, DEBRIS_PAR_CHUNK, DEBRIS_CHAMP_CHANCE, DEBRIS_CHAMP_FACTEUR,
                              DEBRIS_TAILLE, DEBRIS_LUMIERE, DEBRIS_PROFONDEUR) if images else None

    def draw(self, surface, camera, game_map, exclus=()):
        """`exclus` : disques (x, y, rayon) de la vue sans astéroïdes ni débris (les planètes)."""
        graine = game_map.graine if game_map.graine is not None else GRAINE_PAR_DEFAUT
        taille_px = game_map.chunk_size * game_map.tilewidth
        self.fond.draw(surface, camera, graine, taille_px, exclus)  # le plus loin d'abord
        if self.epaves is not None:
            self.epaves.draw(surface, camera, graine, taille_px, exclus)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
