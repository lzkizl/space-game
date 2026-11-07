import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import CALQUE_BASE, VIDE_GIDS

TAILLE = 240                 # côté de la minimap à l'écran (pixels)
POSITION = (20, 20)          # coin haut gauche
RAYON_TUILES = 30            # la minimap montre RAYON_TUILES cases autour du héros, dans chaque direction
RAFRAICHIR = 0.2             # secondes entre deux redessins du décor (le décor change peu)
COULEUR_FOND = (8, 10, 24, 200)
COULEUR_BORDURE = (120, 140, 200)
COULEUR_BASE = (90, 110, 150)
COULEUR_STRUCTURE = (240, 200, 90)
COULEUR_HEROS = (255, 255, 255)
COULEUR_ALIEN = (230, 60, 60)
COULEUR_VAISSEAU = (255, 140, 40)
COULEUR_METEORITE = (150, 150, 150)
COULEUR_TROU_NOIR = (180, 50, 220)   # violet : le trou noir africain
COULEUR_SOUFRE = (230, 220, 80)
COULEUR_SHARD = (190, 90, 255)
COULEUR_URANIUM = (110, 255, 90)
COULEURS_METEORITES = {"soufre": COULEUR_SOUFRE, "shard": COULEUR_SHARD, "uranium": COULEUR_URANIUM}


class Minimap:
    """Petite carte en haut à gauche : les bases, ce qu'on a posé dessus, le héros (au centre),
    les aliens, les vaisseaux ennemis et les météorites. N l'affiche ou la cache
    (M ouvre la grande carte : voir grande_carte.py)."""

    def __init__(self):
        self.visible = True
        self.fond = pygame.Surface((TAILLE, TAILLE), pygame.SRCALPHA)  # le décor, redessiné de temps en temps
        self.chrono = 0.0
        self.echelle = TAILLE / (2 * RAYON_TUILES)                      # pixels de minimap par case

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_n:
            self.visible = not self.visible
            return True
        return False

    def _redessiner_decor(self, game_map, centre):
        """centre = (tx, ty) : la case du héros."""
        self.fond.fill(COULEUR_FOND)
        taille = game_map.chunk_size
        gauche, haut = centre[0] - RAYON_TUILES, centre[1] - RAYON_TUILES
        droite, bas = centre[0] + RAYON_TUILES, centre[1] + RAYON_TUILES
        cote = max(1, round(self.echelle + 0.5))
        for nom in game_map.layers:
            couleur = COULEUR_BASE if nom == CALQUE_BASE else COULEUR_STRUCTURE
            for cy in range(haut // taille, bas // taille + 1):
                for cx in range(gauche // taille, droite // taille + 1):
                    grille = game_map.grille(nom, (cx, cy))  # carte fabriquée ou terrain généré
                    for ly, ligne in enumerate(grille):
                        ty = cy * taille + ly
                        if not haut <= ty <= bas:
                            continue
                        for lx, gid in enumerate(ligne):
                            tx = cx * taille + lx
                            if gid in VIDE_GIDS if nom == CALQUE_BASE else gid == 0:
                                continue
                            if gauche <= tx <= droite:
                                self.fond.fill(couleur, ((tx - gauche) * self.echelle, (ty - haut) * self.echelle,
                                                         cote, cote))

    def update(self, dt, game_map, hero):
        self.chrono -= dt
        if self.chrono <= 0 and self.visible:
            self.chrono = RAFRAICHIR
            x, y = hero.hitbox(hero.x, hero.y).center
            tx = int(x // game_map.tilewidth)
            ty = int(y // game_map.tileheight)
            self._redessiner_decor(game_map, (tx, ty))

    def draw(self, screen, game_map, hero, aliens, vaisseaux, meteorites, trous_noirs=None):
        if not self.visible:
            return
        carte = self.fond.copy()
        centre = hero.hitbox(hero.x, hero.y).center
        rayon_px = RAYON_TUILES * game_map.tilewidth

        def point(x, y):
            """Position (x, y) du monde -> pixel de la minimap (None si hors carte)."""
            px = (x - centre[0]) / rayon_px * (TAILLE / 2) + TAILLE / 2
            py = (y - centre[1]) / rayon_px * (TAILLE / 2) + TAILLE / 2
            if 0 <= px < TAILLE and 0 <= py < TAILLE:
                return round(px), round(py)
            return None

        for meteorite in meteorites.liste:
            p = point(meteorite.x, meteorite.y)
            if p:
                pygame.draw.circle(carte, COULEURS_METEORITES.get(meteorite.type, COULEUR_METEORITE), p, 2)
        for alien in aliens.liste:
            p = point(alien.x, alien.y)
            if p:
                pygame.draw.circle(carte, COULEUR_ALIEN, p, 3)
        for vaisseau in vaisseaux.liste:
            p = point(vaisseau.x, vaisseau.y)
            if p:
                pygame.draw.polygon(carte, COULEUR_VAISSEAU,
                                    [(p[0], p[1] - 5), (p[0] - 4, p[1] + 4), (p[0] + 4, p[1] + 4)])
        if trous_noirs:
            for tn in trous_noirs.liste:
                p = point(tn.x, tn.y)
                if p:
                    pygame.draw.circle(carte, COULEUR_TROU_NOIR, p, 7)
                    pygame.draw.circle(carte, (0, 0, 0), p, 4)
        pygame.draw.circle(carte, COULEUR_HEROS, (TAILLE // 2, TAILLE // 2), 4)
        screen.blit(carte, POSITION)
        pygame.draw.rect(screen, COULEUR_BORDURE, (*POSITION, TAILLE, TAILLE), 2)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
