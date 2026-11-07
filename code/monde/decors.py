import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import RACINE

# =============================================
# ==== Décors des planètes (arbres...) : tirés avec le sol de chaque biome (voir DECORS_BIOMES et
# ==== Map._sol). Une image est posée à sa taille, le pied au milieu du bas de sa case. Le héros passe
# ==== derrière ceux dont le pied est plus bas que le sien, devant les autres.
# =============================================
DOSSIER_IMAGES = RACINE / "image" / "image"
PIED = 0.93   # hauteur du pied dans l'image (part de sa hauteur, depuis le haut) : sous le tronc, l'ombre

_VARIATION_ECHELLE = 0.15   # ±15 % de variation de taille selon la position (reproductible)
_OMBRE_ALPHA = 55            # opacité de l'ombre elliptique au sol


class Decors:
    def __init__(self):
        self._images = {}    # nom -> image originale
        self._echelles = {}  # (nom, tx, ty) -> image mise à l'échelle
        self._ombres = {}    # largeur_pixels -> surface d'ombre elliptique

    def _image(self, nom):
        if nom not in self._images:
            self._images[nom] = pygame.image.load(DOSSIER_IMAGES / nom).convert_alpha()
        return self._images[nom]

    def _image_echelle(self, nom, tx, ty):
        """Image légèrement redimensionnée de façon reproductible selon la position."""
        cle = (nom, tx, ty)
        if cle not in self._echelles:
            base = self._image(nom)
            h = (tx * 2654435761 ^ ty * 2246822519) & 0xFFFFFFFF
            facteur = 1.0 + _VARIATION_ECHELLE * ((h / 0xFFFFFFFF) * 2 - 1)
            w = max(1, round(base.get_width() * facteur))
            hh = max(1, round(base.get_height() * facteur))
            self._echelles[cle] = pygame.transform.smoothscale(base, (w, hh))
        return self._echelles[cle]

    def _ombre(self, largeur):
        """Surface d'ombre elliptique au sol pour un arbre de cette largeur."""
        if largeur not in self._ombres:
            ow = max(4, round(largeur * 0.55))
            oh = max(2, round(ow * 0.22))
            surf = pygame.Surface((ow, oh), pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (0, 0, 0, _OMBRE_ALPHA), (0, 0, ow, oh))
            self._ombres[largeur] = surf
        return self._ombres[largeur]

    def draw(self, vue, camera, game_map, pied_heros, devant, autres=()):
        """Les décors autour de la vue : ceux qui sont derrière le héros (devant=False : pied plus haut que
        `pied_heros`, en pixels monde), ou ceux qui sont devant lui (devant=True). Avec eux, triés de la même
        façon, ce que donnent `autres` (leur méthode images : cristaux lumineux, foreuses...)."""
        tw, th = game_map.tilewidth, game_map.tileheight
        taille = game_map.chunk_size * tw
        cam_x, cam_y = int(camera.x), int(camera.y)
        # (pied_monde, x_monde, image, ombre_or_None)
        items = []
        # (1 chunk de plus autour de la vue : un arbre déborde de sa case)
        for cy in range(cam_y // taille - 1, (cam_y + camera.screen_height) // taille + 2):
            for cx in range(cam_x // taille - 1, (cam_x + camera.screen_width) // taille + 2):
                for tx, ty, nom in game_map.decors((cx, cy)):
                    pied = (ty + 1) * th
                    if (pied > pied_heros) == devant:
                        image = self._image_echelle(nom, tx, ty)
                        items.append((pied, (tx + 0.5) * tw, image, self._ombre(image.get_width())))
        for autre in autres:
            for pied, x, image in autre.images(game_map, camera):
                if (pied > pied_heros) == devant:
                    items.append((pied, x, image, None))
        for pied, x, image, ombre in sorted(items, key=lambda v: v[:2]):
            ix = round(x - image.get_width() / 2) - cam_x
            iy = round(pied - image.get_height() * PIED) - cam_y
            if ombre is not None:
                ow, oh = ombre.get_size()
                vue.blit(ombre, (round(x - ow / 2) - cam_x, pied - oh // 2 - cam_y))
            vue.blit(image, (ix, iy))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
