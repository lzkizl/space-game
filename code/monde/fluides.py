import math

import pygame

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# =============================================
# ==== Fluides procéduraux sur les planètes : mares d'eau, d'acide, de pétrole et de lave,
# ==== tirées avec le sol de chaque biome (voir FLUIDES_BIOMES et map.py).
# ==== Chaque mare est une ellipse aplatie dessinée sur le sol, animée (shimmer, pulsation).
# ==== La lave et l'acide projettent une lueur colorée sur le sol (BLEND_RGB_ADD).
# =============================================

# Paramètres visuels par type de fluide :
# couleur  : couleur au centre
# bord     : couleur au bord (plus claire / plus saturée)
# freq     : fréquence de pulsation (radians/seconde)
# alpha    : (min, max) de l'alpha global pendant la pulsation
# lueur    : couleur de la lueur sur le sol (None = pas de lueur)
TYPES = {
    "eau": {
        "couleur": (35,  100, 210),
        "bord":    (80,  160, 255),
        "freq":    1.1,
        "alpha":   (115, 170),
        "lueur":   None,
    },
    "acide": {
        "couleur": (50,  185,  25),
        "bord":    (110, 255,  55),
        "freq":    2.4,
        "alpha":   (145, 205),
        "lueur":   (60,  210,  30),
    },
    "petrole": {
        "couleur": (14,   8,  22),
        "bord":    (48,  28,  68),
        "freq":    0.6,
        "alpha":   (195, 240),
        "lueur":   None,
    },
    "lave": {
        "couleur": (225,  65,  10),
        "bord":    (255, 185,  40),
        "freq":    1.8,
        "alpha":   (195, 245),
        "lueur":   (255, 100,  25),
    },
}

NIVEAUX_ANIM = 10          # niveaux d'alpha précalculés (animation lisse par quantification)
TAILLE_MODELE = (64, 32)   # taille du modèle de base (2:1 : ellipse aplatie vue de dessus)
FORCE_LUEUR = 0.45         # intensité max de la lueur ajoutée au sol
TAILLE_LUEUR_MODELE = 32   # côté du modèle de lueur avant agrandissement
RATIO_HAUTEUR = 0.55       # hauteur de la mare = rayon * tileheight * RATIO_HAUTEUR


class Fluides:
    def __init__(self):
        self.temps = 0.0
        self._modeles = {}  # (type_fluide, niveau) -> Surface TAILLE_MODELE
        self._images = {}   # (type_fluide, largeur, hauteur, niveau) -> Surface agrandie
        self._lueurs = {}   # (type_fluide, r_px) -> Surface de lueur

    # ---- animation ----

    def update(self, dt):
        self.temps += dt

    def _niveau(self, type_fluide, tx, ty):
        """Niveau d'animation (0..NIVEAUX_ANIM-1) selon le temps et la position (phase spatiale)."""
        cfg = TYPES[type_fluide]
        phase = self.temps * cfg["freq"] + tx * 1.37 + ty * 2.11
        v = 0.5 + 0.5 * math.sin(phase)
        return max(0, min(NIVEAUX_ANIM - 1, round(v * (NIVEAUX_ANIM - 1))))

    # ---- images ----

    def _modele(self, type_fluide, niveau):
        """Surface 64×32 du fluide au niveau d'alpha `niveau`. Gradient radial centre→bord,
        iridescence nacrée pour le pétrole baked dans les 10 niveaux."""
        cle = (type_fluide, niveau)
        if cle not in self._modeles:
            cfg = TYPES[type_fluide]
            alpha_min, alpha_max = cfg["alpha"]
            alpha_global = round(alpha_min + (alpha_max - alpha_min) * niveau / (NIVEAUX_ANIM - 1))
            w, h = TAILLE_MODELE
            img = pygame.Surface((w, h), pygame.SRCALPHA)
            coul = cfg["couleur"]
            bord = cfg["bord"]
            cx, cy = w / 2.0, h / 2.0
            for y in range(h):
                for x in range(w):
                    dx = (x + 0.5 - cx) / cx
                    dy = (y + 0.5 - cy) / cy
                    d = math.hypot(dx, dy)
                    if d >= 1.0:
                        continue
                    t = 1.0 - d          # 1 au centre, 0 au bord
                    t2 = t * t
                    r = round(bord[0] + (coul[0] - bord[0]) * t2)
                    g = round(bord[1] + (coul[1] - bord[1]) * t2)
                    b = round(bord[2] + (coul[2] - bord[2]) * t2)
                    a = round(alpha_global * math.sqrt(t))
                    # reflets nacrés du pétrole : franges iridescentes selon la direction
                    if type_fluide == "petrole":
                        angle = math.atan2(dy, dx)
                        iridescence = 0.5 + 0.5 * math.sin(angle * 3.0 + niveau * 0.7)
                        force = iridescence * (1.0 - d) * 0.55
                        r = min(255, r + round(70 * force))
                        g = min(255, g + round(45 * force))
                        b = min(255, b + round(110 * force))
                    img.set_at((x, y), (r, g, b, a))
            self._modeles[cle] = img
        return self._modeles[cle]

    def _image(self, type_fluide, largeur, hauteur, niveau):
        """Image de la mare à la taille réelle (pixels monde), scalée depuis le modèle 64×32."""
        cle = (type_fluide, largeur, hauteur, niveau)
        if cle not in self._images:
            self._images[cle] = pygame.transform.smoothscale(
                self._modele(type_fluide, niveau), (largeur, hauteur))
        return self._images[cle]

    def _lueur(self, type_fluide, r_px):
        """Surface de lueur ronde (noir = transparent, couleur = lumière à ajouter), mise en cache."""
        cle = (type_fluide, r_px)
        if cle not in self._lueurs:
            cfg = TYPES[type_fluide]
            couleur = cfg["lueur"]
            n = TAILLE_LUEUR_MODELE
            petit = pygame.Surface((n, n))
            for y in range(n):
                for x in range(n):
                    d = math.hypot(x - n / 2, y - n / 2) / (n / 2)
                    v = max(0.0, 1.0 - d) ** 2 * FORCE_LUEUR
                    petit.set_at((x, y), tuple(round(c * v) for c in couleur))
            diam = r_px * 2
            self._lueurs[cle] = pygame.transform.smoothscale(petit, (diam, diam))
        return self._lueurs[cle]

    # ---- collision ----

    def dans_acide(self, hero, carte):
        """True si les pieds du héros sont dans une mare d'acide."""
        if carte.calque_sol is None or not getattr(carte, '_fluides_biomes', None):
            return False
        hb = hero.hitbox(hero.x, hero.y)
        px, py = hb.centerx, hb.bottom
        tw, th = carte.tilewidth, carte.tileheight
        taille_chunk = carte.chunk_size * tw
        cx0 = int(px - taille_chunk) // taille_chunk
        cx1 = int(px + taille_chunk) // taille_chunk + 2
        cy0 = int(py - taille_chunk) // taille_chunk
        cy1 = int(py + taille_chunk) // taille_chunk + 2
        for cy in range(cy0, cy1):
            for cx in range(cx0, cx1):
                for tx, ty, type_fluide, rayon in carte.fluides((cx, cy)):
                    if type_fluide != "acide":
                        continue
                    mcx = (tx + 0.5) * tw
                    mcy = (ty + 0.5) * th
                    semi_w = rayon * tw
                    semi_h = rayon * th * RATIO_HAUTEUR / 2
                    if semi_w == 0 or semi_h == 0:
                        continue
                    dx = (px - mcx) / semi_w
                    dy = (py - mcy) / semi_h
                    if dx * dx + dy * dy <= 1.0:
                        return True
        return False

    # ---- rendu ----

    def draw(self, vue, camera, carte):
        """Mares et fluides sur le sol de la planète (à dessiner après game_map.draw,
        avant les décors et les cristaux). Inclut les lueurs de lave/acide."""
        if carte.calque_sol is None or not getattr(carte, '_fluides_biomes', None):
            return
        tw, th = carte.tilewidth, carte.tileheight
        taille_chunk = carte.chunk_size * tw
        cam_x, cam_y = int(camera.x), int(camera.y)
        marge = 7 * tw

        vue_rect = pygame.Rect(0, 0, *vue.get_size())
        for cy in range((cam_y - marge) // taille_chunk - 1,
                        (cam_y + camera.screen_height + marge) // taille_chunk + 2):
            for cx in range((cam_x - marge) // taille_chunk - 1,
                            (cam_x + camera.screen_width + marge) // taille_chunk + 2):
                for tx, ty, type_fluide, rayon in carte.fluides((cx, cy)):
                    largeur = rayon * 2 * tw
                    hauteur = round(rayon * th * RATIO_HAUTEUR)
                    px = round((tx + 0.5) * tw - camera.x) - largeur // 2
                    py = round((ty + 0.5) * th - camera.y) - hauteur // 2

                    cfg = TYPES[type_fluide]

                    # lueur sous la mare (lave / acide)
                    if cfg["lueur"] is not None:
                        r_lueur = rayon * tw + tw  # un peu plus large que la mare
                        pulsation = 0.7 + 0.3 * math.sin(
                            self.temps * cfg["freq"] * 1.5 + tx * 1.9 + ty * 2.7)
                        lueur_img = self._lueur(type_fluide, round(r_lueur * pulsation))
                        lx = round((tx + 0.5) * tw - camera.x) - lueur_img.get_width() // 2
                        ly = round((ty + 0.5) * th - camera.y) - lueur_img.get_height() // 2
                        vue.blit(lueur_img, (lx, ly), special_flags=pygame.BLEND_RGB_ADD)

                    # mare elle-même
                    if not vue_rect.colliderect((px, py, largeur, hauteur)):
                        continue
                    niveau = self._niveau(type_fluide, tx, ty)
                    img = self._image(type_fluide, largeur, hauteur, niveau)
                    vue.blit(img, (px, py))


if __name__ == "__main__":
    from lanceur import lancer
    lancer()
