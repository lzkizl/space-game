import math
import random
import xml.etree.ElementTree as ET
from functools import lru_cache

from systeme.settings import CALQUE_BASE, MONDE_DENSITE_VIDE, VIDE_GID, VIDE_GIDS

# =============================================
# ==== Monde procédural : hors de la carte fabriquée à la main (map_1.tmx), chaque morceau
# ==== de 16x16 cases est tiré au hasard, à partir de la graine, parmi les morceaux de terrain
# ==== de la carte. Même graine = même monde.
# =============================================
CASES_PAR_MORCEAU = 16
MASQUE_GID = 0x1FFFFFFF  # retire les bits de flip de Tiled (comme monde/map.py)


@lru_cache(maxsize=4)
def morceaux_de_terrain(tmx_path, calques=(CALQUE_BASE,)):
    """Les morceaux des calques `calques` de la carte Tiled qui contiennent du terrain (pas que du vide).
    Le vide solide (qui bloque le héros) y devient de l'espace libre : un monde généré ne doit pas
    enfermer le joueur. La liste est partagée : ne pas la modifier.

    Attention : « pas du vide » ne veut pas dire « qui se voit ». Le calque de base de map_1.tmx est
    presque entièrement fait de tuiles transparentes du tileset (gids 43, 44, 45, 54, 63, 70, 71, 72) :
    elles ne sont pas du vide au sens de VIDE_GIDS, mais elles ne dessinent rien. C'est à l'appelant de
    garder les morceaux qui se voient vraiment (voir Map.morceaux_terrain, qui a les images)."""
    morceaux = []
    for layer in ET.parse(tmx_path).getroot().findall("layer"):
        if layer.get("name") not in calques:
            continue
        for chunk in layer.find("data").findall("chunk"):
            grille = [[int(v) & MASQUE_GID for v in ligne.strip().strip(",").split(",")]
                      for ligne in chunk.text.strip().splitlines() if ligne.strip().strip(",")]
            if any(gid not in VIDE_GIDS for ligne in grille for gid in ligne):
                morceaux.append([[0 if gid == VIDE_GID else gid for gid in ligne] for ligne in grille])
    return morceaux


TAILLE_NAVETTE = 5  # une navette échouée = 5x5 tuiles du tileset des épaves


def navette(graine, coord, case_libre, premier_gid, colonnes, chance, taille=CASES_PAR_MORCEAU):
    """Grille du calque des épaves pour le chunk `coord` : une navette échouée de 5x5 cases à une
    place tirée de la graine, ou None (pas de navette dans ce chunk : le plus souvent). La navette
    reste entière dans le chunk et ne se pose pas sur une case où `case_libre(lx, ly)` est False
    (du terrain). Ses tuiles sont celles de la navette du tileset : premier_gid + ligne * colonnes + colonne."""
    tirage = random.Random(f"navette:{graine}:{coord[0]}:{coord[1]}")  # même graine, mêmes navettes
    if tirage.random() >= chance:
        return None
    ox = tirage.randrange(taille - TAILLE_NAVETTE + 1)
    oy = tirage.randrange(taille - TAILLE_NAVETTE + 1)
    cases = [(ox + c, oy + r) for r in range(TAILLE_NAVETTE) for c in range(TAILLE_NAVETTE)]
    if not all(case_libre(x, y) for x, y in cases):
        return None
    grille = [[0] * taille for _ in range(taille)]
    for x, y in cases:
        grille[y][x] = premier_gid + (y - oy) * colonnes + (x - ox)
    return grille


BORD_BIOME = 7      # bords des biomes irréguliers : chaque case est décalée d'au plus 7 cases...
ONDULATION_BORD = 10  # ... de façon douce : le décalage change sur environ 10 cases (des bords qui ondulent)


@lru_cache(maxsize=65536)
def _valeur(graine, ix, iy):
    return random.Random(f"bruit:{graine}:{ix}:{iy}").random()


def bruit(graine, x, y, echelle):
    """Bruit lisse entre 0 et 1 : il change doucement, sur environ `echelle` cases (même graine, même
    bruit). Des valeurs tirées au hasard aux coins d'une grille, mélangées en douceur entre eux."""
    x, y = x / echelle, y / echelle
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)  # (pas d'angle aux coins de la grille)
    haut = _valeur(graine, ix, iy) + (_valeur(graine, ix + 1, iy) - _valeur(graine, ix, iy)) * fx
    bas = _valeur(graine, ix, iy + 1) + (_valeur(graine, ix + 1, iy + 1) - _valeur(graine, ix, iy + 1)) * fx
    return haut + (bas - haut) * fy


def _decalage(graine, x, y):
    """Décalage (entre -BORD_BIOME et BORD_BIOME) : une grande ondulation et une petite par-dessus."""
    return ((bruit(graine, x, y, ONDULATION_BORD) - 0.5) * 1.5
            + (bruit(graine + ":fin", x, y, ONDULATION_BORD / 3) - 0.5) * 0.5) * BORD_BIOME


@lru_cache(maxsize=4096)
def _cellule_biome(graine, cx, cy, taille, nb):
    """(x, y, biome) de la cellule (cx, cy) de la grille des biomes : son centre (en cases), tiré au
    hasard dans la cellule, et son biome (0 à nb - 1)."""
    tirage = random.Random(f"biome:{graine}:{cx}:{cy}")
    return (cx + tirage.random()) * taille, (cy + tirage.random()) * taille, tirage.randrange(nb)


def biome_de(graine, x, y, nb, taille):
    """Numéro du biome (0 à nb - 1) de la case (x, y). Le monde est découpé en cellules d'environ
    `taille` cases, chacune avec un centre et un biome tirés de la graine ; une case est du biome du
    centre le plus proche (des zones aux formes naturelles, pas des carrés). La case est d'abord
    décalée par un bruit lisse : les bords des biomes ondulent au lieu d'être des lignes droites."""
    x, y = x + _decalage(f"{graine}:x", x, y), y + _decalage(f"{graine}:y", x, y)
    cx, cy = int(x // taille), int(y // taille)
    cellules = [_cellule_biome(graine, cx + dx, cy + dy, taille, nb) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    return min(cellules, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)[2]


def morceau(graine, coord, morceaux):
    """Morceau du chunk `coord` (x, y) pour cette graine : une grille partagée (à ne pas
    modifier), ou None si ce chunk est vide."""
    if not morceaux:
        return None
    tirage = random.Random(f"{graine}:{coord[0]}:{coord[1]}")  # déterministe : même graine, même tirage
    if tirage.random() < MONDE_DENSITE_VIDE:
        return None
    return morceaux[tirage.randrange(len(morceaux))]
