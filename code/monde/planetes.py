import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math
import random

from monde.systemes import (RAYON_MAX as RAYON_SYSTEME_MAX, TROU_NOIR_GALACTIQUE_RAYON,
                            corps as corps_systeme, systemes_dans, trous_noirs_autour)
from systeme.settings import (PLANETES, PLANETES_AUTOUR, PLANETES_PROFONDEUR, PLANETES_TILESET,
                              RACINE, TROU_NOIR_DEGATS, TROU_NOIR_FORCE_GRAVITE, TROU_NOIR_IMAGE)

# gid -> (image, diamètre en cases, nom, carte, couleur) de chaque planète : rempli par enregistrer() quand une
# carte qui a le tileset des repères de planètes est chargée (le gid dépend de la place du tileset dans la carte)
PLANETES_GIDS = {}
GIDS_PAR_NUMERO = {}   # id de la planète dans le tileset (voir PLANETES) -> son gid


def enregistrer(game_map):
    """Note les gids des repères de planètes de cette carte (tuiles de PLANETES_TILESET, voir PLANETES)."""
    gids = game_map.gids_tileset(PLANETES_TILESET)
    for numero, infos in PLANETES.items():
        if numero < len(gids):
            PLANETES_GIDS[gids.start + numero] = infos
            GIDS_PAR_NUMERO[numero] = gids.start + numero

DOSSIER_IMAGES = RACINE / "image" / "image"
DELAI_RECHERCHE = 2.0   # secondes entre deux recherches des tuiles de planètes dans la carte
MORCEAU_MAX = 5         # une planète est dessinée en morceaux carrés d'au plus 5x5 cases...
PIXELS_SOURCE = 128     # ...chacun tiré d'un carré de 128x128 pixels de l'image (agrandie pour tomber juste) :
                        # un morceau de m cases fait m x 128 pixels, donc il est agrandi m fois, pile (pas de raccord visible)
BORD_SOURCE = 4         # pixels des morceaux voisins pris autour de chaque carré avant de l'agrandir
MORCEAUX_GARDES = 80    # morceaux gardés en mémoire (au-delà : seulement ceux de la dernière image)

# --- Systèmes solaires procéduraux (tirés de la graine du monde, voir monde/systemes.py) ---
# Les réglages (où ils apparaissent, 5 % à deux soleils, les trous noirs...) sont dans monde/systemes.py ;
# ici il n'y a que ce qui sert à les DESSINER.
_PROC_IMAGE_COTE = 256  # côté de l'image source générée pour une planète procédurale
_PROC_MARGE_COL = 55    # pixels ignorés à chaque bord d'une colonne (zone de transition entre biomes)
_ASTRE_COTE = 256       # les étoiles et les trous noirs sont dessinés à cette taille, puis agrandis
_ASTRES_GARDES = 12     # images d'astres agrandies gardées en mémoire
_ASTRE_CACHE_MAX = 2560  # au-delà de cette taille, l'image agrandie n'est plus gardée (trop lourde)
# Aspiration : un trou noir attire le héros jusqu'à ASPIRE_PORTEE fois le rayon de son horizon, et
# lui fait des dégâts en deçà de ASPIRE_DANGER fois ce rayon.
ASPIRE_PORTEE = 7.0
ASPIRE_DANGER = 2.2
ASPIRE_DEGATS_HORIZON = 5.0   # passé l'horizon des événements, les dégâts sont bien plus forts

# Textures des biomes -> 6 zones (2 images × 3 colonnes) : chargées au premier dessin
_TEXTURES_PROC = None   # [(surf, x_debut, largeur, hauteur), ...]
# Chemin des textures : (fichier relatif à RACINE / "tilset")
_PROC_TEXTURES_FICHIERS = ("monde_biomes_lies.png", "monde_biomes_lies_1.png")

# Type de planète -> indices de zones de texture compatibles (0-5) + couleur d'atmosphère
# Zones 0,5=rouge rocailleux  1,3=gris foncé  2,4=violet lumineux
_PROC_ZONES = {
    "tellurique": [0, 5],
    "volcanique": [1, 3],
    "glaciaire":  [2, 4],
    "gazeuse":    [0, 1, 2, 3, 4, 5],
    "lunaire":    [1, 3],   # les lunes : la roche grise
}

def _image_etoile_proc(couleur, cote=_ASTRE_COTE):
    """Surface SRCALPHA d'une étoile : halo coloré dégradé + cœur blanc + 4 rayons de diffraction.
    Toujours dessinée à _ASTRE_COTE pixels, puis agrandie à sa taille dans le monde (voir _image_astre) :
    une étoile peut faire 8 cases = 2048 pixels, bien trop pour la dessiner cercle par cercle."""
    img = pygame.Surface((cote, cote), pygame.SRCALPHA)
    r0, g0, b0 = couleur
    c = cote // 2
    rayon = c - 1
    for r in range(rayon + 10, 0, -2):
        if r > rayon:
            k = (r - rayon) / 10
            alpha = round(100 * (1 - k))
            cr = min(255, round(r0 + (255 - r0) * 0.6))
            cg = min(255, round(g0 + (255 - g0) * 0.6))
            cb = min(255, round(b0 + (255 - b0) * 0.6))
        else:
            k = r / max(1, rayon)
            alpha = 255
            cr = min(255, round(r0 + (255 - r0) * (1 - k)))
            cg = min(255, round(g0 + (255 - g0) * (1 - k)))
            cb = min(255, round(b0 + (255 - b0) * (1 - k)))
        pygame.draw.circle(img, (cr, cg, cb, alpha), (c, c), r)
    ext = c + c // 2
    for a_r in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        ex = round(c + math.cos(a_r) * ext)
        ey = round(c + math.sin(a_r) * ext)
        pygame.draw.line(img, (min(255, r0 + 60), min(255, g0 + 50), min(255, b0 + 30), 65),
                         (c, c), (ex, ey), 1)
    return img


def _charger_textures():
    """Charge les textures de biomes et les découpe en 6 colonnes (paresseux)."""
    global _TEXTURES_PROC
    if _TEXTURES_PROC is not None:
        return _TEXTURES_PROC
    _TEXTURES_PROC = []
    for nom in _PROC_TEXTURES_FICHIERS:
        surf = pygame.image.load(str(RACINE / "tilset" / nom)).convert()
        w, h = surf.get_size()
        cw = w // 3
        marge = min(_PROC_MARGE_COL, cw // 6)
        for col in range(3):
            x = col * cw + marge
            larg = cw - 2 * marge
            if larg > 0:
                _TEXTURES_PROC.append((surf, x, larg, h))
    return _TEXTURES_PROC


def _image_trou_noir_proc(cote=_ASTRE_COTE):
    """Le vrai trou noir : l'image trou_afriquain.png (celle du trou noir qui traverse l'espace, voir
    ennemis/trou_noir.py), ramenée à `cote` pixels. Comme les étoiles, chargée une seule fois puis
    agrandie à la taille qu'il faut (voir Planetes._dessiner_astre)."""
    source = pygame.image.load(str(TROU_NOIR_IMAGE)).convert_alpha()
    return pygame.transform.smoothscale(source, (cote, cote))


def _image_planete_proc(nom, type_p, couleur):
    """Image (_PROC_IMAGE_COTE × _PROC_IMAGE_COTE, SRCALPHA) d'une planète procédurale,
    générée à partir des textures rocheuses HD. Le tirage dépend du NOM de la planète (pas de sa
    position : elle tourne autour de son étoile, donc elle bouge)."""
    textures = _charger_textures()
    rng = random.Random(f"img:{nom}")
    n = _PROC_IMAGE_COTE
    cx, cy = n // 2, n // 2
    rayon = n // 2 - 4
    r0, g0, b0 = couleur

    # --- Choisir et préparer la texture ---
    zones = _PROC_ZONES.get(type_p, list(range(len(textures))))
    idx = rng.choice(zones)
    surf, x_debut, cw, ch = textures[idx]

    # Zoom aléatoire (0.35–0.95 de la colonne) pour varier l'échelle de la roche visible.
    # Le zoom ne descend jamais sous ce qu'il faut pour que la découpe de n x n pixels tienne dans
    # la colonne : sinon un seul des deux côtés serait rattrapé, et la roche serait étirée.
    scale_mini = (n + 1) / min(cw, ch)
    scale = max(scale_mini, 0.35 + rng.random() * 0.60)
    sw = max(n + 1, round(cw * scale))
    sh = max(n + 1, round(ch * scale))
    col_surf = pygame.transform.smoothscale(surf.subsurface((x_debut, 0, cw, ch)), (sw, sh))
    ox = rng.randint(0, sw - n)
    oy = rng.randint(0, sh - n)
    crop = col_surf.subsurface((ox, oy, n, n)).copy()

    # Rotation aléatoire (par pas de 90°)
    rot = rng.choice([0, 90, 180, 270])
    if rot:
        crop = pygame.transform.rotate(crop, rot)

    # --- Masque circulaire via BLEND_RGBA_MULT ---
    # convert_alpha() donne A=255 partout ; le masque met A=0 hors du cercle
    tex_a = crop.convert_alpha()
    masque = pygame.Surface((n, n), pygame.SRCALPHA)
    masque.fill((255, 255, 255, 0))
    pygame.draw.circle(masque, (255, 255, 255, 255), (cx, cy), rayon)
    tex_a.blit(masque, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # --- Teinte de couleur légère (atmosphère, type de planète) ---
    tinte = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(tinte, (r0, g0, b0, 28), (cx, cy), rayon)
    tex_a.blit(tinte, (0, 0))

    # --- Limb darkening : bords assombris (effet de sphère) ---
    # On dessine 24 anneaux noirs de plus en plus transparents vers l'intérieur
    for r_limb in range(rayon, rayon - 24, -1):
        k = (rayon - r_limb) / 24          # 0 au bord, 1 profond dans la planète
        alpha = round(130 * (1 - k))        # sombre au bord externe, transparent à l'intérieur
        pygame.draw.circle(tex_a, (0, 0, 0, alpha), (cx, cy), r_limb, 1)

    # --- Reflet lumineux (source de lumière douce en haut à gauche) ---
    reflet = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(reflet, (255, 255, 255, 48),
                       (cx - rayon // 3, cy - rayon // 3), rayon // 2)
    tex_a.blit(reflet, (0, 0))

    # --- Halo d'atmosphère autour de la planète ---
    image = pygame.Surface((n, n), pygame.SRCALPHA)
    image.blit(tex_a, (0, 0))
    for r_h in range(rayon + 14, rayon, -1):
        k = (r_h - rayon) / 14
        pygame.draw.circle(image,
            (min(255, r0 + 60), min(255, g0 + 60), min(255, b0 + 60), round(90 * (1 - k))),
            (cx, cy), r_h)

    return image


def chercher(game_map):
    """[(tx, ty, gid), ...] des planètes : celles dont le repère est posé dans la carte (sur n'importe quel
    calque). Les planètes qui tournent autour d'un astre (PLANETES_AUTOUR : Mars) n'en font pas partie : voir
    positions."""
    taille = game_map.chunk_size
    tournent = {GIDS_PAR_NUMERO[n] for n in PLANETES_AUTOUR if n in GIDS_PAR_NUMERO}
    trouvees = []
    for chunks in game_map.layers.values():
        for (cx, cy), grille in chunks.items():
            gids = set()
            for ligne in grille:
                gids.update(ligne)
            if gids.isdisjoint(PLANETES_GIDS):
                continue  # (presque tous les chunks : on ne regarde pas case par case)
            for ly, ligne in enumerate(grille):
                for lx, gid in enumerate(ligne):
                    if gid in PLANETES_GIDS and gid not in tournent:  # (un repère oublié de Mars ne compte pas)
                        trouvees.append((cx * taille + lx, cy * taille + ly, gid))
    return trouvees


def orbites(reperes):
    """[(cx, cy, rayon, gid), ...] des orbites : le cercle (centre en cases, rayon en cases) que parcourt
    chaque planète qui tourne autour d'un astre (PLANETES_AUTOUR), gid = la planète."""
    resultat = []
    for numero, (centre, distance, _, _) in PLANETES_AUTOUR.items():
        gid_centre = GIDS_PAR_NUMERO.get(centre)
        if numero not in GIDS_PAR_NUMERO or gid_centre is None:
            continue
        for tx, ty, gid in reperes:
            if gid == gid_centre:
                resultat.append((tx, ty, distance, GIDS_PAR_NUMERO[numero]))
    return resultat


def positions(reperes, temps):
    """[(tx, ty, gid), ...] de toutes les planètes à l'instant `temps` (secondes de jeu) : celles des repères
    posés dans la carte (voir chercher), plus celles qui tournent autour d'un astre (PLANETES_AUTOUR) : sur un
    cercle centré sur le repère de l'astre, un tour en `durée` secondes (tx, ty à virgule : elles glissent)."""
    resultat = list(reperes)
    for numero, (centre, distance, direction, duree) in PLANETES_AUTOUR.items():
        gid_centre = GIDS_PAR_NUMERO.get(centre)
        if numero not in GIDS_PAR_NUMERO or gid_centre is None:
            continue
        a = math.radians(direction) + 2 * math.pi * temps / duree
        for tx, ty, gid in reperes:
            if gid == gid_centre:
                resultat.append((tx + math.cos(a) * distance, ty + math.sin(a) * distance, GIDS_PAR_NUMERO[numero]))
    return resultat


def image_planete(gid):
    """Grande image de la planète (taille d'origine). Si son fichier n'existe pas encore : un disque
    lumineux de remplacement (jaune, comme un soleil), pour que le jeu ne plante pas."""
    chemin = DOSSIER_IMAGES / PLANETES_GIDS[gid][0]
    if chemin.exists():
        return pygame.image.load(chemin).convert_alpha()
    return _image_remplacement()


def _image_remplacement(cote=512):
    """Un soleil dessiné : un cœur blanc-jaune, puis un halo orange qui s'efface vers le bord."""
    image = pygame.Surface((cote, cote), pygame.SRCALPHA)
    centre, rayon = cote // 2, cote // 2
    for r in range(rayon, 0, -2):
        k = r / rayon  # 1 au bord, 0 au centre
        couleur = (255, round(250 - 120 * k), round(200 - 200 * k))
        alpha = 255 if k < 0.7 else round(255 * (1 - k) / 0.3)
        pygame.draw.circle(image, (*couleur, alpha), (centre, centre), r)
    return image


class Planetes:
    """Les planètes du monde : à la place de leur petite tuile (que la carte ne dessine pas, voir
    Map._render_chunk), une grande image de PLANETES_GIDS[gid][1] cases de diamètre, centrée sur la tuile.
    Elles sont dessinées derrière la carte : les bases passent devant. Elles sont loin : elles défilent
    moins vite que le monde (PLANETES_PROFONDEUR, voir centre_affiche). Mars tourne autour du Soleil
    (PLANETES_AUTOUR, voir positions).
    Une planète peut être immense (50 cases = 6400 pixels) : elle est découpée en morceaux, préparés
    seulement quand ils sont à l'écran (une seule image de cette taille prendrait des centaines de Mo)."""

    def __init__(self, game_map):
        self.game_map = game_map
        self.liste = []          # [(tx, ty, gid), ...] de toutes les planètes en ce moment (voir positions)
        self.reperes = []        # [(tx, ty, gid), ...] des repères posés dans la carte (voir chercher)
        self.temps = 0.0         # secondes de jeu (sauvegardé) : où en sont les planètes qui tournent
        self.chrono = 0.0
        self._decoupes = {}      # gid -> (cases par morceau, morceaux par côté, image source agrandie et bordée)
        self._morceaux = {}      # (gid, i, j) -> morceau à sa taille dans le monde
        # --- systèmes solaires procéduraux (voir monde/systemes.py) ---
        # Ils ne sont PAS tous calculés d'avance (il y en a des centaines de milliers possibles) :
        # on ne demande que ceux qui peuvent se voir, et monde/systemes.py garde ce qu'il a calculé.
        self._decoupes_proc = {} # nom de la planète -> (m, n, source)
        self._morceaux_proc = {} # (nom, i, j) -> morceau à sa taille dans le monde
        self._sources_astres = {}  # couleur, ou "trou noir" -> image de l'astre à _ASTRE_COTE pixels
        self._images_astres = {}   # (côté, couleur ou "trou noir") -> cette image agrandie

    def _decoupe(self, gid):
        """(m, n, source) : la planète fait n x n morceaux de m x m cases ; la source a n x PIXELS_SOURCE
        pixels de côté, plus BORD_SOURCE pixels transparents tout autour (pour que les morceaux se raccordent)."""
        if gid not in self._decoupes:
            cases = PLANETES_GIDS[gid][1]
            m = max(d for d in range(1, MORCEAU_MAX + 1) if cases % d == 0)
            n = cases // m
            cote = n * PIXELS_SOURCE
            source = pygame.Surface((cote + 2 * BORD_SOURCE, cote + 2 * BORD_SOURCE), pygame.SRCALPHA)
            source.blit(pygame.transform.smoothscale(image_planete(gid), (cote, cote)), (BORD_SOURCE, BORD_SOURCE))
            self._decoupes[gid] = (m, n, source)
        return self._decoupes[gid]

    def _morceau(self, gid, i, j):
        cle = (gid, i, j)
        if cle not in self._morceaux:
            m, _, source = self._decoupe(gid)
            cote = m * self.game_map.tilewidth
            f = cote // PIXELS_SOURCE  # (nombre entier : les pixels tombent pile)
            # le carré de la source avec un peu de ses voisins autour : agrandi, puis recoupé au centre.
            # (smoothscale place le pixel d'arrivée d au pixel (taille source - 1) / taille arrivée * d de la
            # source : avec une arrivée de (taille source - 1) x f pixels, c'est d / f pile, comme dans les
            # morceaux voisins, donc les raccords ne se voient pas)
            avec_bord = PIXELS_SOURCE + 2 * BORD_SOURCE
            bord = pygame.transform.smoothscale(
                source.subsurface((i * PIXELS_SOURCE, j * PIXELS_SOURCE, avec_bord, avec_bord)),
                ((avec_bord - 1) * f, (avec_bord - 1) * f))
            morceau = bord.subsurface((BORD_SOURCE * f, BORD_SOURCE * f, cote, cote)).copy()
            if pygame.mask.from_surface(morceau, 254).count() == cote * cote:
                morceau = morceau.convert()  # tout opaque (le milieu de la planète) : bien plus rapide à dessiner
            self._morceaux[cle] = morceau
        return self._morceaux[cle]

    def _decoupe_proc(self, planete):
        """Comme _decoupe, pour une planète procédurale : indexée par son NOM, pas par sa position
        (elle tourne autour de son étoile : sa position change à chaque image)."""
        if planete.cle not in self._decoupes_proc:
            m = max(d for d in range(1, MORCEAU_MAX + 1) if planete.taille % d == 0)
            n = planete.taille // m
            cote = n * PIXELS_SOURCE
            source = pygame.Surface((cote + 2 * BORD_SOURCE, cote + 2 * BORD_SOURCE), pygame.SRCALPHA)
            source.blit(pygame.transform.smoothscale(
                _image_planete_proc(planete.cle, planete.type, planete.couleur), (cote, cote)),
                (BORD_SOURCE, BORD_SOURCE))
            self._decoupes_proc[planete.cle] = (m, n, source)
        return self._decoupes_proc[planete.cle]

    def _morceau_proc(self, planete, i, j):
        cle = (planete.cle, i, j)
        if cle not in self._morceaux_proc:
            m, _, source = self._decoupe_proc(planete)
            cote = m * self.game_map.tilewidth
            f = cote // PIXELS_SOURCE
            avec_bord = PIXELS_SOURCE + 2 * BORD_SOURCE
            bord = pygame.transform.smoothscale(
                source.subsurface((i * PIXELS_SOURCE, j * PIXELS_SOURCE, avec_bord, avec_bord)),
                ((avec_bord - 1) * f, (avec_bord - 1) * f))
            morceau = bord.subsurface((BORD_SOURCE * f, BORD_SOURCE * f, cote, cote)).copy()
            if pygame.mask.from_surface(morceau, 254).count() == cote * cote:
                morceau = morceau.convert()
            self._morceaux_proc[cle] = morceau
        return self._morceaux_proc[cle]

    def _source_astre(self, couleur, trou_noir):
        """L'image de base d'un astre, à _ASTRE_COTE pixels : dessinée une seule fois par couleur."""
        cle = "trou noir" if trou_noir else couleur
        if cle not in self._sources_astres:
            self._sources_astres[cle] = (_image_trou_noir_proc() if trou_noir
                                         else _image_etoile_proc(couleur))
        return self._sources_astres[cle]

    def _dessiner_astre(self, vue, ecran, centre_x, centre_y, cote, couleur, trou_noir):
        """Dessine un astre de `cote` pixels de côté, centré en (centre_x, centre_y) dans la vue.

        Seule la partie visible est calculée. C'est indispensable : un trou noir supermassif fait
        55 cases de rayon, soit 14080 pixels de côté — l'agrandir en entier demanderait une surface
        de près de 800 Mo. On découpe donc la portion correspondante de l'image de base et on ne
        l'agrandit qu'à la taille de ce qu'on voit, bornée par l'écran."""
        place = pygame.Rect(0, 0, cote, cote)
        place.center = (round(centre_x), round(centre_y))
        visible = place.clip(ecran)
        if not visible.width or not visible.height:
            return
        source = self._source_astre(couleur, trou_noir)
        if visible.size == place.size and cote <= _ASTRE_CACHE_MAX:
            # l'astre tient en entier à l'écran et reste raisonnable : on garde son image agrandie
            cle = (cote, "trou noir" if trou_noir else couleur)
            if cle not in self._images_astres:
                if len(self._images_astres) > _ASTRES_GARDES:
                    self._images_astres.clear()  # (tailles d'un ancien zoom, ou astres quittés)
                self._images_astres[cle] = pygame.transform.smoothscale(source, (cote, cote))
            vue.blit(self._images_astres[cle], place)
            return
        # sinon : on ne prend que le morceau de l'image de base qui tombe dans l'écran
        n = source.get_width()
        gauche = max(0, math.floor((visible.x - place.x) / cote * n))
        haut = max(0, math.floor((visible.y - place.y) / cote * n))
        largeur = min(n - gauche, max(1, math.ceil(visible.width / cote * n) + 1))
        hauteur = min(n - haut, max(1, math.ceil(visible.height / cote * n) + 1))
        # la découpe est un peu plus large que le visible (arrondis) : on redresse la destination
        arrivee = pygame.Rect(place.x + round(gauche / n * cote), place.y + round(haut / n * cote),
                              max(1, round(largeur / n * cote)), max(1, round(hauteur / n * cote)))
        vue.blit(pygame.transform.smoothscale(source.subsurface((gauche, haut, largeur, hauteur)),
                                              arrivee.size), arrivee)

    def aspirer(self, dt, joueurs):
        """Les trous noirs du monde aspirent chaque joueur à portée (voir _aspirer_un)."""
        for joueur in joueurs:
            self._aspirer_un(dt, joueur)

    def _aspirer_un(self, dt, joueur):
        """Les trous noirs aspirent vraiment le héros : celui du cœur d'une galaxie comme celui d'un
        système ordinaire. Plus le trou noir est gros, plus il attire loin et fort — un supermassif de
        55 cases porte jusqu'à 385 cases, et ne lâche plus grand-chose. Trop près de l'horizon, le
        héros prend des dégâts (même calcul que le trou noir d'ennemis/trou_noir.py).

        On ne demande que les trous noirs autour du héros : une poignée de secteurs, donc rien à
        calculer la plupart du temps."""
        if self.game_map.graine is None:
            return
        hero = joueur.hero
        tw = self.game_map.tilewidth
        hx, hy = hero.x, hero.y
        portee_max = max(TROU_NOIR_GALACTIQUE_RAYON) * ASPIRE_PORTEE
        for ex, ey, rayon_cases in trous_noirs_autour(self.game_map.graine, hx / tw, hy / tw,
                                                      portee_max, self.temps):
            rayon_px = rayon_cases * tw
            portee = rayon_px * ASPIRE_PORTEE
            dx, dy = ex * tw - hx, ey * tw - hy
            distance = math.hypot(dx, dy) or 1.0
            if distance > portee:
                continue
            # Exactement la loi du trou noir qui traverse l'espace : au bord du puits l'attraction
            # vaut TROU_NOIR_FORCE_GRAVITE (200 px/s), soit moins que les 300 px/s du héros — on peut
            # donc encore s'enfuir. Elle grimpe en 1/distance^1,5 et devient sans appel vers les deux
            # tiers du puits. Ce n'est pas la FORCE qui grandit avec le trou noir, c'est la PORTÉE :
            # un supermassif aspire sur 308 cases, une naine sur 14.
            force = TROU_NOIR_FORCE_GRAVITE * (portee / max(distance, rayon_px)) ** 1.5
            # on ne dépasse jamais le centre : sans ça, l'attraction d'un supermassif est si forte
            # qu'elle propulse le héros de l'autre côté, et il oscille au lieu d'être avalé
            pas = min(force * dt, distance * 0.9)
            hero.x += dx / distance * pas
            hero.y += dy / distance * pas
            danger = rayon_px * ASPIRE_DANGER
            if distance < danger:
                degats = TROU_NOIR_DEGATS * (1 - distance / danger)
                if distance < rayon_px:
                    degats *= ASPIRE_DEGATS_HORIZON  # passé l'horizon, on ne ressort pas
                joueur.vie.subir(degats * dt)

    def update(self, dt):
        """Les planètes qui tournent avancent ; les repères de la carte sont recherchés de temps en temps."""
        self.temps += dt
        self.chrono -= dt
        if self.chrono <= 0:
            self.chrono = DELAI_RECHERCHE
            self.reperes = chercher(self.game_map)
        self.liste = positions(self.reperes, self.temps)

    def centre(self, gid):
        """Centre (pixels monde) de la planète gid en ce moment, ou None si elle n'est pas dans la carte."""
        tw = self.game_map.tilewidth
        for tx, ty, g in self.liste:
            if g == gid:
                return (tx + 0.5) * tw, (ty + 0.5) * tw
        return None

    def centre_affiche(self, tx, ty, camera):
        """Centre (pixels monde) où l'on voit la planète de la tuile (tx, ty) : elle est loin, donc son
        écart avec le centre de la caméra n'est que PLANETES_PROFONDEUR fois son vrai écart (elle défile
        moins vite que le monde) ; pile à sa place quand la caméra est centrée dessus."""
        return self.place_affichee(tx + 0.5, ty + 0.5, camera)

    def place_affichee(self, x, y, camera):
        """Comme centre_affiche, mais pour un point déjà donné en cases décimales (le centre d'un corps
        d'un système procédural, qui tourne : il n'est pas posé sur une case précise)."""
        tw = self.game_map.tilewidth
        cx = camera.x + camera.screen_width / 2
        cy = camera.y + camera.screen_height / 2
        return (cx + (x * tw - cx) * PLANETES_PROFONDEUR,
                cy + (y * tw - cy) * PLANETES_PROFONDEUR)

    def systemes_a_l_ecran(self, camera):
        """Les systèmes procéduraux dont une partie se voit, avec la position de leurs corps en ce
        moment : [(systeme, [(x, y, etoile), ...], [(x, y, planete), ...], [(x, y, lune), ...]), ...]
        (positions en cases).

        Seuls les secteurs qui peuvent se voir sont calculés. À cause de la parallaxe, un astre
        apparaît à PLANETES_PROFONDEUR fois son vrai écart avec le centre de la caméra : pour qu'il
        tombe dans la demi-vue, son écart réel ne peut donc pas dépasser cette demi-vue divisée par
        PLANETES_PROFONDEUR. Ça fait une zone d'à peine quelques centaines de cases : une poignée de
        secteurs, calculés une seule fois."""
        if self.game_map.graine is None:
            return []
        tw = self.game_map.tilewidth
        ecran = pygame.Rect(0, 0, camera.screen_width, camera.screen_height)
        milieu_x = (camera.x + camera.screen_width / 2) / tw
        milieu_y = (camera.y + camera.screen_height / 2) / tw
        portee_x = camera.screen_width / 2 / tw / PLANETES_PROFONDEUR + RAYON_SYSTEME_MAX
        portee_y = camera.screen_height / 2 / tw / PLANETES_PROFONDEUR + RAYON_SYSTEME_MAX
        proches, _ = systemes_dans(self.game_map.graine, milieu_x - portee_x, milieu_y - portee_y,
                                   milieu_x + portee_x, milieu_y + portee_y, self.temps)
        vus = []
        for systeme in proches:
            x, y = self.place_affichee(systeme.cx, systeme.cy, camera)
            cote = systeme.rayon * tw
            if not ecran.colliderect((x - camera.x - cote, y - camera.y - cote, cote * 2, cote * 2)):
                continue
            vus.append((systeme, *corps_systeme(systeme, self.temps)))
        return vus

    def disques(self, camera):
        """Disques (x, y, rayon), en pixels de la vue, des astres tels qu'on les voit : les planètes
        de la carte, et aussi celles des systèmes procéduraux, leurs lunes et leurs étoiles (sinon les
        astéroïdes de fond se dessineraient par-dessus : voir monde/debris.py)."""
        tw = self.game_map.tilewidth
        resultat = []
        for tx, ty, gid in self.liste:
            x, y = self.centre_affiche(tx, ty, camera)
            resultat.append((x - camera.x, y - camera.y, PLANETES_GIDS[gid][1] / 2 * tw))
        for _, etoiles, planetes, lunes in self.systemes_a_l_ecran(camera):
            for ex, ey, etoile in etoiles:
                x, y = self.place_affichee(ex, ey, camera)
                resultat.append((x - camera.x, y - camera.y, etoile.rayon * tw))
            for px, py, corps in (*planetes, *lunes):   # une lune cache le fond comme une planète
                x, y = self.place_affichee(px, py, camera)
                resultat.append((x - camera.x, y - camera.y, corps.taille / 2 * tw))
        return resultat

    def draw(self, vue, camera):
        ecran = pygame.Rect(0, 0, *vue.get_size())
        tw = self.game_map.tilewidth
        utilises = set()
        for tx, ty, gid in self.liste:
            m, n, _ = self._decoupe(gid)
            cases = PLANETES_GIDS[gid][1]
            # coin haut gauche de la planète, en pixels de la vue (centrée là où on la voit)
            centre_x, centre_y = self.centre_affiche(tx, ty, camera)
            x0 = round(centre_x - cases / 2 * tw - camera.x)
            y0 = round(centre_y - cases / 2 * tw - camera.y)
            if not ecran.colliderect((x0, y0, cases * tw, cases * tw)):
                continue
            pas = m * tw
            for j in range(n):
                for i in range(n):
                    place = pygame.Rect(x0 + i * pas, y0 + j * pas, pas, pas)
                    if place.colliderect(ecran):
                        utilises.add((gid, i, j))
                        vue.blit(self._morceau(gid, i, j), place)
        if len(self._morceaux) > MORCEAUX_GARDES:
            self._morceaux = {cle: morceau for cle, morceau in self._morceaux.items() if cle in utilises}

        # --- Systèmes solaires procéduraux : l'étoile (ou les deux soleils, ou le trou noir),
        #     puis les planètes qui tournent autour (voir monde/systemes.py) ---
        utilises_proc = set()
        for _, etoiles, planetes, lunes in self.systemes_a_l_ecran(camera):
            for ex, ey, etoile in etoiles:
                centre_x, centre_y = self.place_affichee(ex, ey, camera)
                self._dessiner_astre(vue, ecran, centre_x - camera.x, centre_y - camera.y,
                                     max(16, etoile.rayon * tw * 2), etoile.couleur, etoile.trou_noir)
            # les planètes, puis les lunes par-dessus (une Lune a les mêmes champs qu'une Planete :
            # même découpe, même cache d'images, voir monde/systemes.py)
            for px, py, planete in (*planetes, *lunes):
                centre_x, centre_y = self.place_affichee(px, py, camera)
                taille_px = planete.taille * tw
                x0 = round(centre_x - taille_px / 2 - camera.x)
                y0 = round(centre_y - taille_px / 2 - camera.y)
                if not ecran.colliderect((x0, y0, taille_px, taille_px)):
                    continue
                m_p, n_p, _ = self._decoupe_proc(planete)
                pas = m_p * tw
                for jj in range(n_p):
                    for ii in range(n_p):
                        place = pygame.Rect(x0 + ii * pas, y0 + jj * pas, pas, pas)
                        if place.colliderect(ecran):
                            utilises_proc.add((planete.cle, ii, jj))
                            vue.blit(self._morceau_proc(planete, ii, jj), place)
        if len(self._morceaux_proc) > MORCEAUX_GARDES:
            self._morceaux_proc = {cle: m for cle, m in self._morceaux_proc.items() if cle in utilises_proc}
            # les images sources des planètes quittées ne servent plus à rien (plusieurs Mo chacune)
            gardes = {nom for nom, _, _ in self._morceaux_proc}
            self._decoupes_proc = {nom: d for nom, d in self._decoupes_proc.items() if nom in gardes}


if __name__ == "__main__":
    from lanceur import lancer

    lancer()

