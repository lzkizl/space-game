"""
Génère les tilesets des planètes (Terre, Mars, Velmaris), les images des cristaux lumineux et celles des
gisements de minerai (avec l'icône du carbure de tungstène : `python code/outils/generer_tilesets.py minerais`).

À lancer une seule fois (le jeu utilise ensuite les images produites) :
    python code/outils/generer_tilesets.py
Il faut numpy et Pillow (le jeu, lui, n'en a pas besoin).

Disposition des tilesets : une colonne par biome, une ligne par variante (ligne 0 = la tuile principale,
les autres sont tirées moins souvent : voir SOLS_ALEATOIRES dans systeme/settings.py).
Les tuiles se raccordent de tous les côtés, entre elles aussi : près des bords, toutes les variantes d'un
biome sont faites du même hasard (bruit périodique, détails redessinés de l'autre côté du bord) ; seul le
milieu de chaque variante a son propre hasard, fondu en douceur dans le reste (voir Alea).
L'ancienne image de chaque tileset est gardée à côté (.avant_biomes.bak) la première fois.
"""
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

RACINE = Path(__file__).resolve().parent.parent.parent
N = 128          # taille d'une tuile (pixels)
S = 4            # les détails sont dessinés 4 fois plus grands, puis réduits (bords lisses)
COLONNES = 10    # tilesets de 10x10 tuiles
VARIANTES = 4    # lignes 0 à 3
MILIEU = 0.55    # un détail est « au milieu » (propre à la variante) là où la fenêtre dépasse ce seuil


# =============================================
# ==== Outils
# =============================================
def bruit(rng, echelle):
    """Bruit lisse entre 0 et 1, périodique (se raccorde de tous les côtés) : des taches d'environ
    `echelle` pixels."""
    f = np.fft.fftfreq(N)
    fx, fy = np.meshgrid(f, f)
    filtre = np.exp(-(fx ** 2 + fy ** 2) * (np.pi * echelle) ** 2 / 2)
    b = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((N, N))) * filtre))
    return normaliser(b)


def normaliser(a):
    return (a - a.min()) / (a.max() - a.min() + 1e-9)


def fbm(rng, *couches):
    """Plusieurs bruits superposés : couches = (échelle, poids), ..."""
    return normaliser(sum(poids * bruit(rng, echelle) for echelle, poids in couches))


def crete(rng, echelle):
    """Bruit en crêtes (arêtes rocheuses)."""
    return 1 - np.abs(2 * bruit(rng, echelle) - 1)


def grain(rng, force):
    return (rng.random((N, N)) - 0.5) * force


def relief(h, force):
    """Éclairage d'une carte de hauteur par la lumière en haut à gauche (1 = ni ombre ni lumière)."""
    dx = np.roll(h, -1, 1) - np.roll(h, 1, 1)
    dy = np.roll(h, -1, 0) - np.roll(h, 1, 0)
    return 1 + force * (dx + dy)


def colorier(v, stops):
    """Valeurs 0..1 -> couleurs, en suivant les étapes [(position, (r, g, b)), ...]."""
    pos = [p for p, _ in stops]
    return np.stack([np.interp(v, pos, [c[i] for _, c in stops]) for i in range(3)], -1)


def melange(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def grille():
    yy, xx = np.mgrid[0:N, 0:N].astype(float)
    return xx, yy


def distance_periodique(x, y, px, py):
    dx = np.abs(x - px) % N
    dy = np.abs(y - py) % N
    return np.hypot(np.minimum(dx, N - dx), np.minimum(dy, N - dy))


def bords_voronoi(rng, nb, ondulation):
    """Distance (environ) au bord de cellules périodiques aux bords ondulés : petite sur les bords."""
    xx, yy = grille()
    x = xx + (bruit(rng, 10) - 0.5) * ondulation
    y = yy + (bruit(rng, 10) - 0.5) * ondulation
    germes = []
    while len(germes) < nb:  # (deux germes trop proches feraient une cellule écrasée, toute brillante)
        p = rng.uniform(0, N, 2)
        if all(distance_periodique(p[0], p[1], *q) > N / (nb ** 0.5) * 0.6 for q in germes):
            germes.append(p)
    d = np.sort(np.stack([distance_periodique(x, y, *p) for p in germes]), 0)
    return d[1] - d[0]


def flou_periodique(image, rayon):
    """Flou gaussien qui se raccorde (l'image est répétée autour avant d'être floutée)."""
    w, h = image.size
    grand = Image.new(image.mode, (w * 3, h * 3))
    for i in range(3):
        for j in range(3):
            grand.paste(image, (i * w, j * h))
    return grand.filter(ImageFilter.GaussianBlur(rayon)).crop((w, h, 2 * w, 2 * h))


_xx, _yy = grille()
FENETRE = np.sin(np.pi * (_xx + 0.5) / N) * np.sin(np.pi * (_yy + 0.5) / N)  # 0 aux bords, 1 au centre


class Alea:
    """Le hasard d'une variante de tuile. Près des bords, tout vient du hasard commun à toutes les variantes
    du biome (elles se raccordent entre elles) ; au milieu, du hasard propre à la variante (elles diffèrent)."""

    def __init__(self, commun, propre):
        self.commun, self.propre = commun, propre

    def champ(self, fabrique):
        """Une carte (N, N) faite par fabrique(rng) : celle du hasard commun aux bords, celle de la variante
        au milieu, fondues l'une dans l'autre (sans perdre de contraste)."""
        a, b = fabrique(self.commun), fabrique(self.propre)
        w = 0.95 * FENETRE
        moyenne = a.mean()
        return moyenne + (a - moyenne) * np.sqrt(1 - w * w) + (b - b.mean()) * w

    def positions(self, nb, calque):
        """Places de `nb` détails : (rng, x, y). Ceux du hasard commun ne sont gardés que près des bords, ceux
        de la variante qu'au milieu (et pas s'ils touchent un bord : `calque.interieur`)."""
        for rng, garder in ((self.commun, lambda w: w < MILIEU), (self.propre, lambda w: w >= MILIEU)):
            for _ in range(nb):
                x, y = rng.uniform(0, N, 2)
                if garder(FENETRE[int(y), int(x)]):
                    calque.interieur = rng is self.propre
                    yield rng, x, y


class Calque:
    """Détails dessinés (brins d'herbe, cailloux, fleurs...) à S fois la taille, puis réduits. Une forme qui
    dépasse d'un bord est aussi dessinée de l'autre côté : le calque se raccorde. Sauf `interieur` : la forme
    (propre à une variante) n'est dessinée que si elle ne touche aucun bord."""

    def __init__(self):
        self.image = Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.image)
        self.interieur = False

    def _copies(self, pts, marge):
        x0, x1 = min(p[0] for p in pts) - marge, max(p[0] for p in pts) + marge
        y0, y1 = min(p[1] for p in pts) - marge, max(p[1] for p in pts) + marge
        for ox in (-N, 0, N):
            for oy in (-N, 0, N):
                if self.interieur and (ox or oy or x0 < 0 or y0 < 0 or x1 > N or y1 > N):
                    continue
                if x1 + ox >= 0 and x0 + ox <= N and y1 + oy >= 0 and y0 + oy <= N:
                    yield [((x + ox) * S, (y + oy) * S) for x, y in pts]

    def ligne(self, pts, couleur, largeur=1.0):
        for p in self._copies(pts, largeur):
            self.d.line(p, fill=couleur, width=max(1, round(largeur * S)), joint="curve")

    def polygone(self, pts, couleur):
        for p in self._copies(pts, 1):
            self.d.polygon(p, fill=couleur)

    def ellipse(self, cx, cy, rx, ry, couleur):
        for p in self._copies([(cx - rx, cy - ry), (cx + rx, cy + ry)], 1):
            self.d.ellipse([p[0], p[1]], fill=couleur)

    def reduit(self):
        return self.image.resize((N, N), Image.LANCZOS)


def assembler(base, *calques):
    """Tableau de couleurs (N, N, 3) + calques de détails (images RGBA N x N) -> image RGB."""
    image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    for calque in calques:
        image = Image.alpha_composite(image, calque)
    return image.convert("RGB")


def ajouter_lueur(image, lueur, couleur, force):
    """Ajoute de la lumière (addition) : `lueur` = intensité 0..1 (N, N)."""
    a = np.asarray(image, dtype=float)
    a = a + lueur[..., None] * np.array(couleur, dtype=float) * force
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def intensite(calque):
    """Intensité 0..1 d'un calque RGBA (son alpha)."""
    return np.asarray(calque, dtype=float)[..., 3] / 255


def sol(alea, hauteur, couleurs, force_relief, grain_force=0):
    """Le sol : une carte de hauteur (faite par hauteur(rng)), coloriée et éclairée."""
    h = alea.champ(hauteur)
    base = colorier(h, couleurs) * relief(h, force_relief)[..., None]
    if grain_force:
        base += alea.champ(lambda r: grain(r, grain_force))[..., None]
    return base, h


# ---- détails ----
def herbe(alea, calque, nb, couleurs, hauteur=(5, 12), penche=3.0, largeur=1.0):
    """Brins d'herbe : les plus sombres d'abord (au fond), les plus clairs par-dessus."""
    brins = []
    for rng, x, y in alea.positions(nb, calque):
        brins.append((rng.random(), x, y, rng.uniform(*hauteur), rng.uniform(-penche, penche), calque.interieur))
    for t, x, y, h, dx, interieur in sorted(brins):
        calque.interieur = interieur
        c = melange(couleurs[0], couleurs[1], t)
        calque.ligne([(x, y), (x + dx * 0.35, y - h * 0.55), (x + dx, y - h)], c + (255,), largeur)


def cailloux(alea, calque, nb, couleur, taille=(1.5, 4.0), ombre=90):
    """Petits cailloux : ombre portée, caillou, reflet en haut à gauche."""
    for rng, x, y in alea.positions(nb, calque):
        rx = rng.uniform(*taille)
        ry = rx * rng.uniform(0.55, 0.85)
        c = melange(couleur, (0, 0, 0), rng.uniform(-0.15, 0.25))
        calque.ellipse(x + rx * 0.35, y + ry * 0.45, rx, ry, (0, 0, 0, ombre))
        calque.ellipse(x, y, rx, ry, c + (255,))
        calque.ellipse(x - rx * 0.3, y - ry * 0.35, rx * 0.45, ry * 0.4, melange(c, (255, 255, 255), 0.35) + (200,))


def fleurs(alea, calque, nb, couleurs):
    for rng, x, y in alea.positions(nb, calque):
        c = couleurs[rng.integers(len(couleurs))]
        r = rng.uniform(1.0, 1.7)
        for k in range(5):
            a = k * 2 * np.pi / 5 + rng.random()
            calque.ellipse(x + np.cos(a) * r, y + np.sin(a) * r, r * 0.75, r * 0.75, c + (255,))
        calque.ellipse(x, y, r * 0.55, r * 0.55, (250, 215, 70, 255))


def feuilles(alea, calque, nb, couleurs):
    for rng, x, y in alea.positions(nb, calque):
        col = couleurs[rng.integers(len(couleurs))]
        a = rng.uniform(0, np.pi)
        r = rng.uniform(1.8, 3.2)
        calque.polygone([(x + np.cos(a) * r, y + np.sin(a) * r), (x - np.sin(a) * r * 0.45, y + np.cos(a) * r * 0.45),
                         (x - np.cos(a) * r, y - np.sin(a) * r), (x + np.sin(a) * r * 0.45, y - np.cos(a) * r * 0.45)],
                        col + (235,))


def fissures(alea, calque, nb, couleur, longueur=(10, 24), largeur=0.9):
    for rng, x, y in alea.positions(nb, calque):
        a = rng.uniform(0, 2 * np.pi)
        pts = [(x, y)]
        for _ in range(int(rng.uniform(*longueur) / 4)):
            a += rng.uniform(-0.7, 0.7)
            x, y = x + np.cos(a) * 4, y + np.sin(a) * 4
            pts.append((x, y))
        calque.ligne(pts, couleur, largeur)


def eclats(alea, calque, nb, couleur, taille=(3, 7)):
    """Petits éclats de cristal plantés dans le sol (face claire à gauche, sombre à droite)."""
    clair, sombre = melange(couleur, (255, 255, 255), 0.45), melange(couleur, (0, 0, 0), 0.35)
    for rng, x, y in alea.positions(nb, calque):
        w = rng.uniform(*taille) * 0.45
        h = w * rng.uniform(2.0, 3.2)
        a = rng.uniform(-0.5, 0.5)

        def rot(px, py, x=x, y=y, a=a):
            return x + px * np.cos(a) - py * np.sin(a), y + px * np.sin(a) + py * np.cos(a)
        calque.ellipse(x + w * 0.6, y + w * 0.3, w * 1.4, w * 0.6, (0, 0, 0, 110))
        calque.polygone([rot(-w, 0), rot(0, 0.15 * w), rot(0, -h), rot(-w, -h * 0.7)], clair + (255,))
        calque.polygone([rot(0, 0.15 * w), rot(w, 0), rot(w, -h * 0.7), rot(0, -h)], sombre + (255,))


def points_brillants(alea, calque, nb, couleurs):
    for rng, x, y in alea.positions(nb, calque):
        calque.ellipse(x, y, 0.7, 0.7, couleurs[rng.integers(len(couleurs))] + (255,))


def ondes(rng, kx, ky, torsion):
    """Rides périodiques (sable, dunes), tordues par un bruit."""
    xx, yy = grille()
    return 0.5 + 0.5 * np.sin(2 * np.pi * (kx * xx + ky * yy) / N + torsion * bruit(rng, 20))


# =============================================
# ==== Terre
# =============================================
def terre_prairie(alea, fleuri=False):
    base, _ = sol(alea, lambda r: fbm(r, (30, 0.6), (8, 0.3), (2, 0.1)),
                  [(0, (46, 92, 34)), (0.55, (70, 124, 44)), (1, (98, 150, 58))], 2.5)
    c = Calque()
    herbe(alea, c, 900, [(38, 84, 28), (132, 186, 76)])
    if fleuri:
        fleurs(alea, c, 26, [(250, 250, 250), (245, 120, 170), (150, 140, 255), (255, 200, 60)])
    return assembler(base, c.reduit())


def terre_foret(alea):
    base, _ = sol(alea, lambda r: fbm(r, (24, 0.6), (6, 0.3), (2, 0.1)),
                  [(0, (30, 56, 28)), (0.5, (44, 76, 34)), (1, (64, 98, 42))], 3.0)
    mousse = alea.champ(lambda r: bruit(r, 9))
    base = base + np.clip((mousse - 0.55) * 4, 0, 1)[..., None] * np.array([-8, 10, -6])
    c = Calque()
    feuilles(alea, c, 70, [(120, 84, 40), (92, 104, 40), (140, 110, 50), (70, 60, 30)])
    herbe(alea, c, 380, [(26, 52, 22), (72, 114, 46)], hauteur=(4, 9))
    cailloux(alea, c, 5, (96, 98, 90), (1.5, 3.5))
    return assembler(base, c.reduit())


def terre_savane(alea):
    base, _ = sol(alea, lambda r: fbm(r, (28, 0.6), (8, 0.3), (2, 0.1)),
                  [(0, (142, 118, 58)), (0.55, (172, 148, 76)), (1, (200, 176, 98))], 2.0)
    terre = alea.champ(lambda r: bruit(r, 14))
    base = base + np.clip((terre - 0.65) * 5, 0, 1)[..., None] * np.array([-14, -24, -24])
    c = Calque()
    herbe(alea, c, 650, [(150, 124, 60), (232, 210, 140)], hauteur=(6, 14), penche=4)
    cailloux(alea, c, 4, (140, 120, 96), (1.5, 3))
    return assembler(base, c.reduit())


def terre_sable(alea):
    base, _ = sol(alea, lambda r: 0.35 * ondes(r, 4, 1, 5) + 0.65 * fbm(r, (16, 0.6), (2, 0.4)),
                  [(0, (200, 172, 120)), (0.6, (218, 194, 140)), (1, (234, 214, 164))], 0.9, grain_force=14)
    c = Calque()
    cailloux(alea, c, 7, (168, 146, 110), (1.2, 2.6), ombre=60)
    return assembler(base, c.reduit())


def terre_roche(alea):
    base, _ = sol(alea, lambda r: normaliser(fbm(r, (22, 0.55), (7, 0.3), (2, 0.15)) + 0.25 * crete(r, 12)),
                  [(0, (86, 86, 84)), (0.5, (118, 116, 110)), (1, (156, 152, 144))], 3.5)
    c = Calque()
    fissures(alea, c, 7, (52, 52, 52, 200))
    cailloux(alea, c, 14, (130, 128, 120), (1.5, 4.5))
    herbe(alea, c, 90, [(56, 92, 40), (110, 150, 70)], hauteur=(3, 6))
    return assembler(base, c.reduit())


# =============================================
# ==== Mars
# =============================================
def mars_poussiere(alea):
    base, _ = sol(alea, lambda r: fbm(r, (30, 0.55), (9, 0.3), (2, 0.15)),
                  [(0, (146, 66, 38)), (0.5, (178, 88, 50)), (1, (210, 114, 66))], 2.0, grain_force=12)
    c = Calque()
    cailloux(alea, c, 16, (110, 50, 32), (1.0, 2.6))
    return assembler(base, c.reduit())


def mars_basalte(alea):
    base, _ = sol(alea, lambda r: normaliser(0.6 * crete(r, 16) + 0.4 * fbm(r, (6, 0.6), (2, 0.4))),
                  [(0, (70, 34, 26)), (0.5, (102, 52, 36)), (1, (142, 78, 52))], 4.5)
    c = Calque()
    fissures(alea, c, 6, (34, 16, 12, 210))
    cailloux(alea, c, 12, (84, 44, 32), (2, 5))
    return assembler(base, c.reduit())


def crateres(rng):
    xx, yy = grille()
    h = 0.35 * fbm(rng, (24, 0.6), (3, 0.4))
    for _ in range(rng.integers(1, 4)):
        px, py = rng.uniform(0, N, 2)
        r = rng.uniform(7, 22)
        d = distance_periodique(xx, yy, px, py)
        h = h - 0.6 * np.clip(1 - (d / r) ** 2, 0, None) + 0.25 * np.exp(-((d - r) / (0.25 * r)) ** 2)
    return normaliser(h)


def mars_crateres(alea):
    base, _ = sol(alea, crateres, [(0, (140, 62, 38)), (0.55, (178, 88, 50)), (1, (210, 116, 70))], 3.5,
                  grain_force=10)
    c = Calque()
    cailloux(alea, c, 8, (110, 50, 32), (1.0, 2.4))
    return assembler(base, c.reduit())


def mars_dunes(alea):
    base, _ = sol(alea, lambda r: 0.5 * ondes(r, 3, 2, 6) + 0.5 * fbm(r, (14, 0.6), (2, 0.4)),
                  [(0, (182, 94, 50)), (0.6, (206, 120, 66)), (1, (224, 144, 88))], 1.4, grain_force=10)
    return assembler(base)


# =============================================
# ==== Velmaris (la planète violette, pleine de cristaux)
# =============================================
def velmaris_poussiere(alea):
    base, _ = sol(alea, lambda r: fbm(r, (28, 0.55), (8, 0.3), (2, 0.15)),
                  [(0, (46, 22, 84)), (0.5, (68, 38, 116)), (1, (96, 60, 150))], 2.5, grain_force=12)
    c = Calque()
    cailloux(alea, c, 10, (40, 24, 70), (1.2, 3.2))
    p = Calque()  # poussière de cristal qui brille
    points_brillants(alea, p, 18, [(120, 220, 255), (120, 220, 255), (240, 140, 255)])
    p = p.reduit()
    image = assembler(base, c.reduit(), p)
    return ajouter_lueur(image, intensite(flou_periodique(p, 2.5)), (150, 120, 255), 1.6)


def velmaris_obsidienne(alea):
    h = alea.champ(lambda r: normaliser(0.7 * crete(r, 20) + 0.3 * fbm(r, (8, 0.7), (3, 0.3))))
    eclairage = relief(h, 3.5)
    base = colorier(h, [(0, (22, 12, 46)), (0.5, (38, 24, 74)), (1, (62, 40, 108))]) * eclairage[..., None]
    reflet = np.clip(eclairage - 1.12, 0, None)[..., None] * np.array([110, 120, 230])  # reflets vitreux
    c = Calque()
    fissures(alea, c, 5, (8, 4, 18, 220))
    return assembler(base + reflet, c.reduit())


def velmaris_failles(alea):
    base, _ = sol(alea, lambda r: fbm(r, (24, 0.6), (6, 0.25), (2, 0.15)),
                  [(0, (30, 14, 54)), (0.5, (48, 24, 82)), (1, (70, 40, 110))], 3.0)
    bord = np.clip(alea.champ(lambda r: bords_voronoi(r, 7, 14)), 0, None)
    image = assembler(base * (0.75 + 0.25 * np.clip(bord / 10, 0, 1))[..., None])
    image = ajouter_lueur(image, np.exp(-bord / 5.0), (150, 50, 230), 0.9)   # halo des failles
    image = ajouter_lueur(image, np.exp(-bord / 1.2), (255, 170, 255), 1.0)  # cœur brûlant
    return image


def velmaris_cristaux(alea):
    base, _ = sol(alea, lambda r: fbm(r, (26, 0.55), (7, 0.3), (2, 0.15)),
                  [(0, (36, 26, 90)), (0.5, (54, 44, 124)), (1, (80, 70, 160))], 3.0)
    c = Calque()
    eclats(alea, c, 22, (80, 200, 255))
    eclats(alea, c, 6, (200, 120, 255))
    cailloux(alea, c, 6, (40, 30, 80), (1.2, 3.0))
    c = c.reduit()
    image = assembler(base, c)
    return ajouter_lueur(image, intensite(flou_periodique(c, 5)), (60, 140, 255), 0.55)


# =============================================
# ==== Infernus (planète apocalyptique — lave, cendres, feu éternel, style Nether+)
# =============================================
def infernus_obsidienne(alea):
    """Col 1 : obsidienne calcinée — presque noire, zébrée de failles rouge sang."""
    h = alea.champ(lambda r: normaliser(0.6 * crete(r, 18) + 0.4 * fbm(r, (8, 0.6), (3, 0.4))))
    eclairage = relief(h, 4.0)
    base = colorier(h, [(0, (10, 4, 4)), (0.5, (24, 10, 8)), (1, (44, 18, 12))]) * eclairage[..., None]
    bord = np.clip(alea.champ(lambda r: bords_voronoi(r, 8, 12)), 0, None)
    image = assembler(base * (0.78 + 0.22 * np.clip(bord / 8, 0, 1))[..., None])
    image = ajouter_lueur(image, np.exp(-bord / 4.5), (200, 30, 10), 0.75)
    image = ajouter_lueur(image, np.exp(-bord / 0.9), (255, 90, 25), 0.55)
    return image


def infernus_cendres_lune(alea):
    """Col 2 : cendres de lune — poussière grise pale, dépouillée, silence de mort."""
    base, _ = sol(alea, lambda r: fbm(r, (26, 0.55), (7, 0.3), (2, 0.15)),
                  [(0, (58, 54, 52)), (0.5, (90, 86, 82)), (1, (128, 122, 116))], 1.5, grain_force=20)
    c = Calque()
    cailloux(alea, c, 20, (70, 66, 62), (0.8, 2.5), ombre=50)
    fissures(alea, c, 4, (48, 44, 42, 120), longueur=(6, 14), largeur=0.5)
    return assembler(base, c.reduit())


def infernus_braises(alea):
    """Col 3 : sol de braises — roche sombre parsemée de tisons incandescents."""
    base, _ = sol(alea, lambda r: fbm(r, (22, 0.6), (6, 0.3), (2, 0.1)),
                  [(0, (28, 10, 6)), (0.5, (50, 18, 10)), (1, (78, 28, 14))], 3.5)
    c = Calque()
    points_brillants(alea, c, 60, [(255, 120, 20), (255, 80, 10), (255, 180, 40)])
    cailloux(alea, c, 8, (38, 14, 8), (1.5, 3.5))
    c_img = c.reduit()
    image = assembler(base, c_img)
    return ajouter_lueur(image, intensite(flou_periodique(c_img, 4)), (255, 80, 10), 1.4)


def infernus_magma(alea):
    """Col 4 : roche de magma — orange vif, rivières de lave qui coulent sous la croûte."""
    base, _ = sol(alea, lambda r: fbm(r, (20, 0.6), (5, 0.3), (2, 0.1)),
                  [(0, (100, 28, 8)), (0.5, (160, 55, 10)), (1, (220, 100, 20))], 3.0)
    bord = np.clip(alea.champ(lambda r: bords_voronoi(r, 6, 10)), 0, None)
    image = assembler(base * (0.5 + 0.5 * np.clip(bord / 6, 0, 1))[..., None])
    image = ajouter_lueur(image, np.exp(-bord / 6.0), (255, 120, 20), 1.0)
    image = ajouter_lueur(image, np.exp(-bord / 1.5), (255, 220, 80), 0.8)
    return image


def infernus_basalte(alea):
    """Col 5 : basalte volcanique — colonnes noires de lave refroidie, géologie brute."""
    h = alea.champ(lambda r: normaliser(0.5 * crete(r, 22) + 0.5 * fbm(r, (10, 0.65), (3, 0.35))))
    eclairage = relief(h, 5.0)
    base = colorier(h, [(0, (8, 8, 10)), (0.5, (22, 22, 26)), (1, (44, 42, 50))]) * eclairage[..., None]
    c = Calque()
    fissures(alea, c, 10, (6, 6, 8, 230), longueur=(14, 28), largeur=1.1)
    cailloux(alea, c, 6, (18, 18, 22), (2.0, 5.5))
    return assembler(base, c.reduit())


def infernus_soufre(alea):
    """Col 6 : poussière de soufre — jaune-vert acide, toxique, couleurs de mort chimique."""
    base, _ = sol(alea, lambda r: 0.4 * ondes(r, 3, 2, 5) + 0.6 * fbm(r, (18, 0.6), (4, 0.3)),
                  [(0, (120, 108, 20)), (0.5, (160, 148, 30)), (1, (200, 190, 48))], 1.2, grain_force=18)
    c = Calque()
    cailloux(alea, c, 12, (100, 90, 16), (1.0, 2.8), ombre=55)
    return assembler(base, c.reduit())


# =============================================
# ==== Cristaux lumineux (objets posés sur les planètes, voir monde/cristaux.py)
# =============================================
CRISTAL_TAILLE = (120, 140)   # image d'un cristal (pixels) ; son pied est à 93 % de la hauteur
COULEURS_CRISTAUX = {
    "violet": (160, 96, 250),
    "bleu": (70, 190, 255),
    "rose": (255, 110, 200),
    "rouge": (255, 55, 25),
    "ambre": (255, 155, 20),
}


def image_cristal(couleur, graine):
    rng = np.random.default_rng(graine)
    l, h = CRISTAL_TAILLE
    image = Image.new("RGBA", (l * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    clair, sombre = melange(couleur, (255, 255, 255), 0.45), melange(couleur, (0, 0, 0), 0.42)
    milieu, arete = melange(couleur, (255, 255, 255), 0.15), melange(couleur, (255, 255, 255), 0.85)
    pied = h * 0.93
    # ombre au sol
    d.ellipse([(l * 0.14) * S, (pied - 7) * S, (l * 0.86) * S, (pied + 6) * S], fill=(0, 0, 0, 85))

    def prisme(x, largeur, hauteur, angle):
        a = np.radians(angle)

        def p(px, py):  # point du prisme (pied en 0, 0 ; vers le haut = y négatif), tourné puis placé
            return ((x + px * np.cos(a) - py * np.sin(a)) * S, (pied + px * np.sin(a) + py * np.cos(a)) * S)
        w = largeur / 2
        arrete = 0.12 * w
        d.polygon([p(-w, 0), p(arrete, 3), p(arrete, -hauteur), p(-w, -hauteur * 0.74)], fill=clair)
        d.polygon([p(arrete, 3), p(w, 0), p(w, -hauteur * 0.74), p(arrete, -hauteur)], fill=sombre)
        d.polygon([p(-w * 0.35, 1), p(arrete, 3), p(arrete, -hauteur), p(-w * 0.35, -hauteur * 0.8)], fill=milieu)
        # reflets : arête centrale et petit éclat sur la face claire
        d.line([p(arrete, 2), p(arrete, -hauteur)], fill=arete + (200,), width=max(1, S // 2))
        d.polygon([p(-w * 0.8, -hauteur * 0.25), p(-w * 0.6, -hauteur * 0.25), p(-w * 0.6, -hauteur * 0.62),
                   p(-w * 0.8, -hauteur * 0.55)], fill=arete + (170,))

    # du fond vers l'avant : les deux penchés derrière, le grand au milieu, deux petits devant
    for x, largeur, hauteur, angle in [(-26, 20, 58, -30), (28, 22, 66, 26), (2, 30, 108, -3),
                                       (-18, 18, 44, -14), (20, 16, 38, 16)]:
        x += rng.uniform(-3, 3)
        prisme(l / 2 + x, largeur, hauteur * rng.uniform(0.92, 1.05), angle + rng.uniform(-4, 4))
    # cailloux au pied
    for _ in range(5):
        cx, rx = l / 2 + rng.uniform(-34, 34), rng.uniform(3, 6)
        d.ellipse([(cx - rx) * S, (pied - rx * 0.7) * S, (cx + rx) * S, (pied + rx * 0.5) * S], fill=(66, 56, 84, 255))
        d.ellipse([(cx - rx * 0.6) * S, (pied - rx * 0.6) * S, (cx) * S, (pied - rx * 0.1) * S], fill=(104, 94, 124, 255))
    image = image.resize((l, h), Image.LANCZOS)
    # lueur douce autour (dans l'image ; le jeu ajoute en plus une lumière qui pulse sur le sol)
    alpha = image.getchannel("A").filter(ImageFilter.GaussianBlur(6))
    lueur = Image.new("RGBA", image.size, couleur + (0,))
    lueur.putalpha(alpha.point(lambda v: v * 0.55))
    return Image.alpha_composite(lueur, image)


# =============================================
# ==== Gisements de minerai (posés sur les planètes, récoltés comme les cristaux : voir monde/cristaux.py)
# =============================================
MINERAI_TAILLE = (130, 110)   # image d'un gisement (pixels) ; son pied est à 93 % de la hauteur
# nom -> (couleur de la roche, couleurs des veines (la première plus souvent), couleur des reflets)
MINERAIS = {
    "fer": ((112, 104, 98), [(176, 92, 58), (150, 74, 46), (196, 196, 206)], (236, 236, 244)),
    "cuivre": ((104, 98, 92), [(214, 124, 60), (190, 100, 44), (70, 170, 124)], (255, 206, 150)),
    "carbure": ((92, 56, 46), [(70, 76, 92), (110, 118, 140), (46, 50, 62)], (190, 205, 245)),
}


def image_minerai(roche, veines, reflet, graine):
    """Un tas de blocs de roche, parcourus de veines de minerai (avec quelques reflets)."""
    rng = np.random.default_rng(graine)
    l, h = MINERAI_TAILLE
    pied = h * 0.93
    image = Image.new("RGBA", (l * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.ellipse([(l * 0.08) * S, (pied - 9) * S, (l * 0.92) * S, (pied + 6) * S], fill=(0, 0, 0, 90))  # ombre au sol
    clair, sombre = melange(roche, (255, 255, 255), 0.28), melange(roche, (0, 0, 0), 0.4)

    def contour(cx, cy, rx, ry):
        """Bloc anguleux : des points autour d'une ellipse, à des distances un peu au hasard."""
        n = rng.integers(7, 10)
        angles = np.sort(rng.uniform(0, 2 * np.pi, n))
        return [(cx + np.cos(a) * rx * rng.uniform(0.8, 1.05), cy + np.sin(a) * ry * rng.uniform(0.8, 1.05))
                for a in angles]

    def echelle(pts, cx, cy, f, dx, dy):
        return [((cx + (x - cx) * f + dx) * S, (cy + (y - cy) * f + dy) * S) for x, y in pts]

    # du fond vers l'avant : deux blocs derrière, un gros au milieu, deux petits devant
    for x, y, rx, ry in [(-28, -30, 26, 22), (26, -34, 28, 24), (0, -38, 40, 34), (-34, -14, 20, 15),
                         (34, -12, 18, 13)]:
        cx, cy = l / 2 + x + rng.uniform(-3, 3), pied + y + rng.uniform(-2, 2)
        pts = contour(cx, cy, rx, ry)
        bloc = Image.new("L", image.size, 0)
        ImageDraw.Draw(bloc).polygon(echelle(pts, cx, cy, 1, 0, 0), fill=255)
        couche = Image.new("RGBA", image.size, (0, 0, 0, 0))
        c = ImageDraw.Draw(couche)
        c.polygon(echelle(pts, cx, cy, 1, 0, 0), fill=sombre)              # face à l'ombre (en bas à droite)
        c.polygon(echelle(pts, cx, cy, 0.86, -2, -3), fill=roche)          # le bloc
        c.polygon(echelle(pts, cx, cy, 0.5, -rx * 0.28, -ry * 0.34), fill=clair + (150,))  # éclairé en haut à gauche
        # veines et pépites de minerai, seulement sur le bloc
        for _ in range(int(rx * ry / 55)):
            couleur = veines[0] if rng.random() < 0.55 else veines[rng.integers(1, len(veines))]
            px, py = cx + rng.uniform(-rx, rx) * 0.8, cy + rng.uniform(-ry, ry) * 0.8
            if rng.random() < 0.5:  # une veine : petit trait cassé
                pts_veine = [(px, py)]
                for _ in range(rng.integers(2, 4)):
                    px, py = px + rng.uniform(-7, 7), py + rng.uniform(-4, 4)
                    pts_veine.append((px, py))
                c.line([(a * S, b * S) for a, b in pts_veine], fill=couleur, width=round(rng.uniform(1.6, 3.2) * S),
                       joint="curve")
            else:  # une pépite, avec son reflet
                r = rng.uniform(2.2, 4.5)
                c.ellipse([(px - r) * S, (py - r * 0.8) * S, (px + r) * S, (py + r * 0.8) * S], fill=couleur)
                c.ellipse([(px - r * 0.6) * S, (py - r * 0.6) * S, (px - r * 0.05) * S, (py - r * 0.1) * S],
                          fill=reflet + (200,))
        couche.putalpha(Image.fromarray(np.minimum(np.asarray(couche.getchannel("A")), np.asarray(bloc))))
        image = Image.alpha_composite(image, couche)
        d = ImageDraw.Draw(image)
    # cailloux au pied
    for _ in range(6):
        cx, rx = l / 2 + rng.uniform(-50, 50), rng.uniform(2.5, 5)
        d.ellipse([(cx - rx) * S, (pied - rx * 0.7) * S, (cx + rx) * S, (pied + rx * 0.5) * S], fill=sombre + (255,))
        d.ellipse([(cx - rx * 0.6) * S, (pied - rx * 0.6) * S, cx * S, (pied - rx * 0.1) * S], fill=clair + (255,))
    return image.resize((l, h), Image.LANCZOS)


def icone_carbure():
    """Icône du carbure de tungstène (512 x 512, comme les autres ressources) : un cube gris acier, plus sombre
    que le tungstène, aux reflets bleutés, avec des cristaux hexagonaux sur le dessus."""
    t = 512
    image = Image.new("RGBA", (t * 2, t * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)

    def p(x, y):
        return x * 2, y * 2

    d.ellipse([p(128, 400), p(384, 450)], fill=(0, 0, 0, 40))  # ombre
    haut, gauche, droite = [(256, 70), (398, 150), (256, 230), (114, 150)], [(114, 150), (256, 230), (256, 392), (114, 312)], \
        [(256, 230), (398, 150), (398, 312), (256, 392)]
    d.polygon([p(*q) for q in haut], fill=(120, 128, 150))
    d.polygon([p(*q) for q in gauche], fill=(70, 76, 94))
    d.polygon([p(*q) for q in droite], fill=(46, 50, 64))
    for face in (haut, gauche, droite):
        d.line([p(*q) for q in face + face[:1]], fill=(150, 162, 196), width=4)
    # cristaux hexagonaux sur le dessus (aplatis comme la face)
    for cx, cy, r in [(212, 150, 30), (292, 132, 22), (286, 182, 18)]:
        pts = [(cx + np.cos(a) * r, cy + np.sin(a) * r * 0.56) for a in np.radians(np.arange(0, 360, 60) + 30)]
        d.polygon([p(*q) for q in pts], fill=(170, 184, 222))
        d.polygon([p(*q) for q in pts[3:] + [(cx, cy)]], fill=(214, 224, 250))
    # rayures sur les faces, comme les autres cubes de ressource
    for y in (205, 240, 275):
        d.line([p(150, y), p(210, y + 30)], fill=(110, 118, 140), width=6)
    for y in (215, 270):
        d.line([p(310, y + 20), p(360, y - 8)], fill=(84, 90, 110), width=6)
    return image.resize((t, t), Image.LANCZOS)


def images_minerais():
    for i, (nom, (roche, veines, reflet)) in enumerate(MINERAIS.items()):
        chemin = RACINE / "image" / "image" / f"minerai_{nom}.png"
        image_minerai(roche, veines, reflet, 21 + i).save(chemin)
        print("écrit :", chemin.relative_to(RACINE))
    chemin = RACINE / "image" / "image" / "ressource" / "carbure_tungstene.png"
    icone_carbure().save(chemin)
    print("écrit :", chemin.relative_to(RACINE))


# =============================================
# ==== Assemblage des tilesets
# =============================================
def hash_texte(texte):
    return sum(ord(c) * 31 ** i for i, c in enumerate(texte)) % (2 ** 32)


def tuile(nom_tileset, colonne, ligne, fabrique):
    """Variante `ligne` du biome de la colonne : même hasard commun pour toutes les lignes d'une colonne."""
    graine = hash_texte(nom_tileset)
    alea = Alea(np.random.default_rng([graine, colonne]), np.random.default_rng([graine, colonne, ligne, 1]))
    return fabrique(alea)


def sauver_tileset(chemin, biomes, garder=()):
    """biomes = {colonne: fonction(alea) -> tuile}. Les tuiles `garder` (ids) de l'ancienne image sont reprises
    telles quelles. L'ancienne image est copiée en .avant_biomes.bak la première fois."""
    sauvegarde = chemin.with_name(chemin.name + ".avant_biomes.bak")
    if chemin.exists() and not sauvegarde.exists():
        shutil.copy(chemin, sauvegarde)
    ancienne = Image.open(sauvegarde).convert("RGBA") if sauvegarde.exists() else None
    image = Image.new("RGBA", (N * COLONNES, N * COLONNES), (0, 0, 0, 0))
    for colonne, fabrique in biomes.items():
        for ligne in range(VARIANTES):
            image.paste(tuile(chemin.name, colonne, ligne, fabrique).convert("RGBA"), (colonne * N, ligne * N))
    for i in garder if ancienne is not None else ():
        boite = ((i % COLONNES) * N, (i // COLONNES) * N, (i % COLONNES + 1) * N, (i // COLONNES + 1) * N)
        image.paste(ancienne.crop(boite), boite[:2])
    image.save(chemin)
    print("écrit :", chemin.relative_to(RACINE))


TILESETS = {
    RACINE / "tilset" / "planette" / "terre" / "tilset-terre_1.png": ({
        0: terre_prairie,
        1: terre_foret,
        2: lambda alea: terre_prairie(alea, fleuri=True),
        3: terre_savane,
        4: terre_sable,
        5: terre_roche,
    }, ()),
    RACINE / "tilset" / "mars-tilset.png": ({
        1: mars_poussiere,
        2: mars_basalte,
        3: mars_crateres,
        4: mars_dunes,
    }, (0,)),
    RACINE / "tilset" / "velmaris-tilset.png": ({
        1: velmaris_poussiere,
        2: velmaris_obsidienne,
        3: velmaris_failles,
        4: velmaris_cristaux,
    }, (0, 10)),
    RACINE / "tilset" / "infernus-tilset.png": ({
        1: infernus_obsidienne,
        2: infernus_cendres_lune,
        3: infernus_braises,
        4: infernus_magma,
        5: infernus_basalte,
        6: infernus_soufre,
    }, ()),
}


def main():
    for chemin, (biomes, garder) in TILESETS.items():
        sauver_tileset(chemin, biomes, garder)
    for i, (nom, couleur) in enumerate(COULEURS_CRISTAUX.items()):
        chemin = RACINE / "image" / "image" / f"cristal_{nom}.png"
        image_cristal(couleur, 7 + i).save(chemin)
        print("écrit :", chemin.relative_to(RACINE))
    images_minerais()


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["minerais"]:
        images_minerais()  # python code/outils/generer_tilesets.py minerais : seulement les minerais
    else:
        main()
