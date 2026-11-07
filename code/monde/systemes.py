import math
import random
from collections import namedtuple

# =============================================
# ==== Le monde au-delà de la carte dessinée à la main, à trois échelles :
# ====
# ====   galaxies  : des amas d'étoiles de ~16000 cases de rayon, très loin les uns des autres.
# ====   systèmes  : une étoile (ou deux, ou un trou noir) et ses planètes, DANS une galaxie.
# ====   planètes  : elles tournent autour de leur étoile.
# ====   lunes     : elles tournent autour de leur planète, qui tourne elle-même.
# ====
# ==== Tout est tiré de la graine du monde : même graine = même univers, toujours au même endroit.
# ====
# ==== GÉNÉRATION PARESSEUSE : il y a bien trop de secteurs pour tous les calculer d'avance
# ==== (des dizaines de milliers). On ne calcule que ceux qu'on REGARDE — ceux qui tombent dans la
# ==== vue de la carte ou autour du héros — et on garde le résultat. C'est pour ça que « découvrir
# ==== toute la carte » (panneau admin, F3) ne coûte rien : la découverte n'engendre rien, seul le
# ==== regard engendre. Et chaque appel a un budget (voir `budget`) : même en dézoomant d'un coup
# ==== sur un million de cases, le jeu ne calcule qu'une tranche par image.
# ====
# ==== Ce fichier ne contient que les données (pas de pygame) : le dessin dans le monde est dans
# ==== monde/planetes.py, celui sur la grande carte dans monde/grande_carte.py.
# =============================================

# ---------------------------------------------------------------------------
# Galaxies
# ---------------------------------------------------------------------------
# Le monde est découpé en cellules géantes ; chaque cellule a une chance de contenir une galaxie,
# posée près du milieu de sa cellule. Comme pour les systèmes, le décalage est borné : deux galaxies
# ne se chevauchent donc jamais, et de très loin (40000 + 95000 = 135000, pour une demi-cellule de
# 250000). Entre deux galaxies il reste au minimum 500000 - 2x40000 - 2x95000 = 230000 cases de vide
# absolu : plus de deux fois le diamètre d'une grande galaxie. Traverser, c'est un très long voyage.
GALAXIE_CELLULE = 500000   # côté d'une cellule de galaxie, en cases
GALAXIE_ECART = 0.08       # de combien une galaxie s'écarte du milieu de sa cellule (part du côté)
GALAXIE_CHANCE = 0.55      # probabilité qu'une cellule contienne une galaxie
GALAXIE_RAYON = (45000, 95000)   # rayon d'une galaxie, en cases
GALAXIE_PORTEE = 3         # cellules dans chaque direction : l'univers fait ±1500000 cases
GALAXIE_BRAS = (2, 5)      # nombre de bras d'une galaxie spirale
GALAXIE_TOURS = (0.7, 1.4)  # de combien de tours les bras s'enroulent
# type de galaxie -> poids
GALAXIE_TYPES = (("spirale", 55), ("elliptique", 27), ("irrégulière", 18))
GALAXIE_COULEURS = (
    (170, 200, 255),   # bleu froid
    (255, 225, 180),   # crème
    (255, 185, 150),   # saumon
    (205, 180, 255),   # violet pâle
    (180, 245, 230),   # turquoise
)
# La galaxie de départ : la cellule (0, 0) en a toujours une, pile sur l'origine, pour que le
# système dessiné à la main (le Soleil, Mars...) soit bien dans une galaxie et pas dans le vide.
# Elle est plus grande que les autres : c'est celle où le joueur passera sa partie, il faut qu'elle
# contienne de quoi explorer longtemps. (110000 + 95000 = 205000, pour une distance minimale de
# 460000 cases à une galaxie voisine : aucun recouvrement possible.)
GALAXIE_DEPART_RAYON = 110000
# ...mais son centre n'est pas sur l'origine : il y a un trou noir supermassif au milieu de chaque
# galaxie, et on ne va pas le poser sur la base de départ du joueur. La galaxie de départ est donc
# décalée de cette part de son rayon : l'origine reste bien à l'intérieur (0,40 < 1), et le trou noir
# devient une destination lointaine, à ~44000 cases de la base.
GALAXIE_DEPART_DECALAGE = 0.40

# --- les galaxies bougent ---
# Chacune décrit lentement un grand cercle autour de sa place de départ. Un mouvement BORNÉ, et non
# une dérive en ligne droite : deux galaxies qui s'éloignent indéfiniment finiraient par se rentrer
# dedans au bout de quelques dizaines d'heures de jeu. Là, 40000 (décalage) + 30000 (dérive) + 95000
# (rayon) = 165000 < 250000 (la demi-cellule) : elles ne se toucheront jamais, quel que soit le temps.
GALAXIE_DERIVE = 30000        # rayon du cercle que décrit une galaxie, en cases
GALAXIE_DERIVE_DUREE = (9000.0, 26000.0)   # secondes de jeu pour en faire le tour (2 h 30 à 7 h)
# La galaxie de départ, elle, ne bouge pas : c'est le repère du joueur. On est dedans, donc on se
# déplace avec elle — vue de l'intérieur elle est immobile, et ce sont les autres qui défilent. Ça
# garde aussi la carte dessinée à la main (l'origine) bien calée dans sa galaxie.

# --- le trou noir aspire sa galaxie ---
# Tout le contenu d'une galaxie se rapproche lentement de son trou noir central : les distances au
# centre sont multipliées par un facteur qui descend de 1 à 1 - ASPIRATION_MAX. C'est une contraction
# UNIFORME : tout se rapproche dans la même proportion, donc l'écart entre deux systèmes voisins se
# réduit d'autant — au pire de 12 %, ce qui laisse les 722 cases de vide mesurées à plus de 630.
# Rien ne peut donc se chevaucher, même après des centaines d'heures.
ASPIRATION_MAX = 0.12          # de combien une galaxie peut se contracter, au total
ASPIRATION_DUREE = 72000.0     # secondes de jeu pour atteindre cette contraction (20 h)

# --- le trou noir supermassif du centre de chaque galaxie ---
TROU_NOIR_GALACTIQUE_RAYON = (30, 55)       # rayon de son horizon, en cases (une étoile : 2 à 8)
TROU_NOIR_GALACTIQUE_ETOILES = (4, 8)       # étoiles prises dans son orbite
TROU_NOIR_GALACTIQUE_ORBITE = (150, 600)    # à quelle distance elles tournent, en cases
TROU_NOIR_GALACTIQUE_KEPLER = 60.0          # elles filent : un tour en 3 à 25 minutes de jeu
# aucun système ordinaire ne naît à moins de ça du centre d'une galaxie (la place du trou noir)
EXCLUSION_CENTRE = 2500

# ---------------------------------------------------------------------------
# Systèmes solaires
# ---------------------------------------------------------------------------
# Un système est posé près du MILIEU de son secteur, décalé d'au plus ECART_SECTEUR fois le côté du
# secteur. Deux systèmes voisins sont donc toujours séparés d'au moins SECTEUR * (1 - 2*ECART_SECTEUR)
# cases, soit 2100 : plus que les deux plus grands rayons possibles réunis (2 x 990). Deux systèmes
# ne se chevauchent jamais, quelle que soit la graine.
SECTEUR = 3500       # côté d'un secteur, en cases : au plus un système par secteur
ECART_SECTEUR = 0.20  # de combien un système peut s'écarter du milieu de son secteur (part du côté)
CHANCE = 0.95        # probabilité qu'un secteur DANS une galaxie (et en plein cœur) ait un système
EXCLUSION = 900      # cases autour de l'origine laissées libres (le système dessiné à la main dans Tiled)
# Densité dans la galaxie : au bord d'une galaxie il y a moins d'étoiles qu'en son cœur, et les
# galaxies spirales ont leurs étoiles le long des bras.
DENSITE_BORD = 0.32  # densité au bord de la galaxie (1 = autant qu'au centre)
DENSITE_BRAS = 0.42  # part de la densité qui dépend des bras (spirales seulement)

# --- quel genre de système ---
CHANCE_TROU_NOIR = 0.015   # 1,5 % des systèmes : un trou noir au centre au lieu d'une étoile (très rare)
CHANCE_BINAIRE = 0.05      # 5 % des systèmes : deux soleils qui tournent l'un autour de l'autre

# --- les étoiles ---
# (nom, couleur, rayon min/max en cases, poids) : les naines rouges sont les plus courantes, comme en vrai
ETOILES = (
    ("naine rouge",    (255, 120,  80), (2, 4), 34),
    ("naine orange",   (255, 170,  70), (2, 5), 22),
    ("étoile jaune",   (255, 232, 140), (3, 6), 20),
    ("étoile blanche", (245, 250, 255), (3, 6), 12),
    ("étoile bleue",   (150, 200, 255), (4, 8),  8),
    ("géante rouge",   (255,  95,  60), (6, 8),  4),
)
TROU_NOIR_RAYON = (2, 4)           # rayon de l'horizon des événements, en cases
TROU_NOIR_COULEUR = (150, 70, 210)  # violet : sa couleur sur la grande carte

BINAIRE_SEPARATION = (10, 26)      # demi-axe de l'orbite des deux soleils (cases : distance étoile ↔ centre)
BINAIRE_VITESSE = (0.02, 0.08)     # rad/s de jeu : un tour en 1 à 5 minutes

# --- les planètes ---
NB_PLANETES = (1, 6)               # nombre de planètes par système (min, max)
ORBITE_PREMIERE = (70, 140)        # rayon de l'orbite de la première planète, en cases
# Ce qui s'ajoute au rayon pour chaque planète suivante. Le plus grand système possible fait donc
# 140 + 5 x 170 = 990 cases de rayon : voir SECTEUR, qui garantit qu'ils ne se touchent pas.
ORBITE_ECART = (70, 170)
# diamètres possibles d'une planète, en cases : tous multiples de 4, pour que l'image se découpe
# en morceaux qui tombent pile (voir Planetes._decoupe_proc dans monde/planetes.py)
TAILLES = (8, 12, 16, 20, 24)
# vitesse orbitale : ω = KEPLER / rayon^1,5 rad/s (3ᵉ loi de Kepler : plus c'est loin, plus c'est lent).
# Une planète à 100 cases fait le tour en ~10 minutes de jeu, une à 500 cases en ~1 h 50.
KEPLER = 10.5

# --- les lunes ---
# Combien de lunes autour d'une planète ? On tire à pile ou face, encore et encore : tant que le tirage
# passe, une lune de plus. Il n'y a AUCUN maximum — mais chaque lune supplémentaire est moins probable
# que la précédente, et la chance de dépasser n lunes décroît comme (chance)^n.
# Avec la chance la plus haute (0,62, une géante gazeuse), 1000 lunes a une probabilité de
# 0,62^1000 ≈ 10^-207 : c'est possible, mais ça n'arrivera jamais. 10 lunes, en revanche, arrive.
LUNE_CHANCE = 0.38          # une petite planète : ~0,6 lune en moyenne
LUNE_CHANCE_GROSSE = 0.62   # la plus grosse (24 cases) : ~1,6 lune en moyenne, et de gros cortèges
LUNE_TAILLE_MAX = 24        # taille de planète à partir de laquelle on a LUNE_CHANCE_GROSSE
# Où tournent-elles : entre le bord de la planète (+ LUNE_MARGE) et au plus LUNE_ORBITE_MAX cases du
# centre. Peu de lunes = bien espacées ; beaucoup = serrées, mais le cortège reste dans ce disque, donc
# il ne mord jamais sur l'orbite de la planète voisine (ORBITE_ECART vaut au minimum 70 cases).
LUNE_MARGE = 2.0
LUNE_ECART = 3.5            # espacement visé entre deux lunes, en cases
LUNE_ORBITE_MAX = 30.0      # distance maximale d'une lune au centre de sa planète, en cases
LUNE_PART = (0.10, 0.26)    # diamètre d'une lune, en part du diamètre de sa planète
LUNE_TAILLE_MIN = 2         # ...jamais moins que ça (sinon on ne la voit pas)
# ω = LUNE_KEPLER / rayon^1,5 : une lune à 10 cases fait son tour en ~2 minutes de jeu
LUNE_KEPLER = 1.6

# Rayon du plus grand système possible, en cases : sert à élargir les recherches par zone (un système
# dont le centre est hors de la zone peut quand même y déborder).
RAYON_MAX = (ORBITE_PREMIERE[1] + (NB_PLANETES[1] - 1) * ORBITE_ECART[1]
             + max(max(TAILLES) / 2, LUNE_ORBITE_MAX))

# Type de planète -> couleurs possibles (voir aussi _PROC_ZONES dans monde/planetes.py : la texture)
PALETTES = {
    "tellurique": [(215, 130, 80),  (200, 150, 100), (190, 110, 70)],   # orange rouille
    "volcanique": [(130, 90, 80),   (100, 70, 65),   (160, 100, 90)],   # gris chaud
    "glaciaire":  [(160, 130, 220), (180, 150, 235), (145, 115, 205)],  # violet
    "gazeuse":    [(215, 190, 140), (140, 175, 220), (170, 215, 235)],  # doré/bleu
    "lunaire":    [(190, 190, 195), (160, 160, 170), (210, 200, 185)],  # gris poussiéreux (les lunes)
}
# les types tirés au sort pour une PLANÈTE : "lunaire" est réservé aux lunes
TYPES = [t for t in PALETTES if t != "lunaire"]

# --- les noms (Ælis-417, Vexor-82...) ---
_DEBUTS = ("Æl", "Bor", "Cyn", "Dra", "Eri", "Fen", "Gal", "Hel", "Ith", "Jor", "Kae", "Lyr", "Mor",
           "Nax", "Oph", "Pra", "Qel", "Rha", "Sel", "Tyr", "Urn", "Vex", "Wyn", "Xan", "Yll", "Zor")
_FINS = ("a", "is", "or", "ae", "un", "ys", "ar", "en", "ix", "os", "ea", "il")
_ROMAINS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")


def _nom(tirage):
    """Un nom de système tiré au hasard, du genre « Vexis-417 »."""
    return f"{tirage.choice(_DEBUTS)}{tirage.choice(_FINS)}-{tirage.randrange(10, 1000)}"


def _lettres(numero):
    """Le suffixe d'une lune : a, b, ... z, aa, ab... (il n'y a pas de maximum au nombre de lunes)."""
    nom = ""
    numero += 1
    while numero:
        numero, reste = divmod(numero - 1, 26)
        nom = chr(ord("a") + reste) + nom
    return nom


# Une galaxie. `centre` = (cx, cy) en cases ; `rayon` en cases ; `bras` et `enroulement` ne servent
# qu'aux spirales (le dessin, et la densité d'étoiles le long des bras).
# `cle` : l'identité, unique et stable (les coordonnées de la cellule ou du secteur). `nom` est joli
# mais PAS unique : les noms sont tirés d'une petite réserve de syllabes, donc deux astres éloignés
# peuvent s'appeler pareil. Tout ce qui doit distinguer un astre d'un autre — le cache des images, les
# systèmes découverts, la sauvegarde — passe par `cle`, jamais par `nom`.
# `cx, cy` : sa place de DÉPART ; elle tourne autour (voir position_galaxie), sauf celle du départ.
Galaxie = namedtuple("Galaxie", "cle nom cx cy rayon type couleur bras enroulement angle0 trou_noir"
                                " derive derive_vitesse derive_angle0")
# Un système solaire. `type` : "simple" (un soleil), "binaire" (deux), "trou_noir".
# `rayon` = de quoi contenir tout le système (orbites comprises), en cases ;
# `couleur` = celle de l'astre central (sa boule sur la grande carte).
Systeme = namedtuple("Systeme", "cle nom cx cy type genre etoiles planetes rayon couleur galaxie")
# Une étoile du système. `separation` = 0 : elle est pile au centre (système simple) ; sinon elle tourne
# à `separation` cases du centre, à `vitesse` rad/s, en partant de l'angle `angle0`.
# `trou_noir` : c'est un trou noir, pas une étoile (il se dessine à l'envers — voir monde/planetes.py).
# C'est porté par l'astre et non par le système, parce qu'un centre galactique mêle les deux : un trou
# noir supermassif ET les étoiles qui tournent autour.
Etoile = namedtuple("Etoile", "rayon couleur separation vitesse angle0 trou_noir")
# Une planète : elle tourne à `orbite` cases du centre du système, à `vitesse` rad/s (négative : dans
# l'autre sens), en partant de `angle0`. `taille` = son diamètre en cases.
# `lunes` : ses lunes, de la plus proche à la plus lointaine (souvent aucune).
Planete = namedtuple("Planete", "cle nom orbite taille type couleur vitesse angle0 lunes")
# Une lune : exactement les mêmes champs qu'une planète (sans lunes à elle), mais `orbite` se compte
# depuis le centre de SA PLANÈTE, qui bouge elle-même. Les champs portent les mêmes noms exprès : le
# dessin (monde/planetes.py) et la grande carte traitent une lune comme une petite planète.
Lune = namedtuple("Lune", "cle nom orbite taille type couleur vitesse angle0")


# ---------------------------------------------------------------------------
# Galaxies
# ---------------------------------------------------------------------------
_galaxies = {}   # graine -> [Galaxie, ...] (il y en a quelques dizaines : on les calcule d'un coup)


def galaxies(graine):
    """Toutes les galaxies du monde pour cette graine. Elles sont peu nombreuses (~25) : contrairement
    aux systèmes, on peut les calculer toutes d'un coup, une fois pour toutes."""
    if graine is None:
        return []
    if graine not in _galaxies:
        if len(_galaxies) > 8:
            _galaxies.clear()  # (on a changé de monde plusieurs fois)
        trouvees = []
        ecart = round(GALAXIE_CELLULE * GALAXIE_ECART)
        for gx in range(-GALAXIE_PORTEE, GALAXIE_PORTEE + 1):
            for gy in range(-GALAXIE_PORTEE, GALAXIE_PORTEE + 1):
                tirage = random.Random(f"galaxie:{graine}:{gx}:{gy}")
                depart = gx == 0 and gy == 0   # la cellule du milieu a toujours sa galaxie
                if not depart and tirage.random() >= GALAXIE_CHANCE:
                    continue
                if depart:
                    # décalée, pour que son trou noir central ne tombe pas sur la base du joueur
                    angle = tirage.uniform(0, math.tau)
                    loin = GALAXIE_DEPART_RAYON * GALAXIE_DEPART_DECALAGE
                    cx, cy = round(math.cos(angle) * loin), round(math.sin(angle) * loin)
                    rayon = GALAXIE_DEPART_RAYON
                else:
                    cx = gx * GALAXIE_CELLULE + tirage.randint(-ecart, ecart)
                    cy = gy * GALAXIE_CELLULE + tirage.randint(-ecart, ecart)
                    rayon = tirage.randint(*GALAXIE_RAYON)
                type_g = tirage.choices([t for t, _ in GALAXIE_TYPES],
                                        [p for _, p in GALAXIE_TYPES])[0]
                trouvees.append(Galaxie(
                    cle=f"{gx}:{gy}",
                    nom=f"{tirage.choice(_DEBUTS)}{tirage.choice(_FINS)}",
                    cx=cx, cy=cy, rayon=rayon, type=type_g,
                    couleur=tirage.choice(GALAXIE_COULEURS),
                    bras=tirage.randint(*GALAXIE_BRAS),
                    enroulement=tirage.uniform(*GALAXIE_TOURS),
                    angle0=tirage.uniform(0, math.tau),
                    trou_noir=tirage.randint(*TROU_NOIR_GALACTIQUE_RAYON),
                    # la galaxie de départ est le repère du joueur : elle ne bouge pas
                    derive=0 if depart else GALAXIE_DERIVE,
                    derive_vitesse=(0.0 if depart else
                                    math.tau / tirage.uniform(*GALAXIE_DERIVE_DUREE)
                                    * tirage.choice((-1, 1))),
                    derive_angle0=tirage.uniform(0, math.tau)))
        # Les noms sont tirés d'une petite réserve de syllabes : sur 28 galaxies, deux peuvent tomber
        # sur le même. Leur identité (`cle`) ne s'en trouve pas affectée, mais deux galaxies du même
        # nom sur la carte seraient déroutantes : on numérote les doublons (Ophar, Ophar II...).
        vus = {}
        propres = []
        for galaxie in trouvees:
            vus[galaxie.nom] = vus.get(galaxie.nom, 0) + 1
            if vus[galaxie.nom] > 1:
                galaxie = galaxie._replace(nom=f"{galaxie.nom} {_ROMAINS[vus[galaxie.nom] - 1]}")
            propres.append(galaxie)
        _galaxies[graine] = propres
    return _galaxies[graine]


def position_galaxie(galaxie, temps):
    """(x, y) du centre de la galaxie — donc de son trou noir — à l'instant `temps` (secondes de jeu).
    Elle décrit un lent cercle autour de sa place de départ. Celle du joueur ne bouge pas."""
    if not galaxie.derive:
        return galaxie.cx, galaxie.cy
    angle = galaxie.derive_angle0 + galaxie.derive_vitesse * temps
    return (galaxie.cx + math.cos(angle) * galaxie.derive,
            galaxie.cy + math.sin(angle) * galaxie.derive)


def aspiration(temps):
    """De combien tout ce que contient une galaxie s'est rapproché de son trou noir : un facteur qui
    part de 1 et descend jusqu'à 1 - ASPIRATION_MAX, puis s'y arrête. Multiplie les distances au
    centre. Uniforme, donc rien ne peut se chevaucher (voir ASPIRATION_MAX)."""
    return 1.0 - ASPIRATION_MAX * min(1.0, max(0.0, temps) / ASPIRATION_DUREE)


def galaxie_depart(graine):
    """La galaxie où commence le joueur : celle qui contient l'origine (0, 0), c'est-à-dire la carte
    dessinée à la main. Son centre, lui, est décalé (voir GALAXIE_DEPART_DECALAGE) : le trou noir
    supermassif ne doit pas tomber sur la base de départ."""
    return galaxie_de(graine, 0, 0)


def rayon_galaxie(galaxie, temps):
    """Le rayon de la galaxie à cet instant : il rétrécit, puisque son trou noir l'aspire."""
    return galaxie.rayon * aspiration(temps)


def galaxie_de(graine, x, y, temps=0.0):
    """La galaxie qui contient le point (x, y) en cases du monde à l'instant `temps`, ou None
    (le vide intergalactique)."""
    for galaxie in galaxies(graine):
        gx, gy = position_galaxie(galaxie, temps)
        rayon = rayon_galaxie(galaxie, temps)
        if (x - gx) ** 2 + (y - gy) ** 2 <= rayon * rayon:
            return galaxie
    return None


def _densite(galaxie, dx, dy):
    """Part des secteurs qui portent une étoile à cet endroit de la galaxie (0 à 1) : le cœur est
    dense, le bord presque vide, et dans une spirale les étoiles suivent les bras.
    (dx, dy) se comptent depuis le centre de la galaxie."""
    k = math.hypot(dx, dy) / galaxie.rayon   # 0 au centre, 1 au bord
    if k >= 1:
        return 0.0
    densite = 1 - (1 - DENSITE_BORD) * k * k
    if galaxie.type == "spirale":
        phase = (math.atan2(dy, dx) - galaxie.angle0) * galaxie.bras - k * galaxie.enroulement * math.tau
        bras = 0.5 + 0.5 * math.cos(phase)   # 1 sur un bras, 0 entre deux bras
        densite *= (1 - DENSITE_BRAS) + DENSITE_BRAS * bras
    elif galaxie.type == "irrégulière":
        densite *= 0.55 + 0.45 * math.cos((math.atan2(dy, dx) - galaxie.angle0) * 3)
    return densite


# ---------------------------------------------------------------------------
# Systèmes : un secteur à la fois, et seulement quand on le regarde
# ---------------------------------------------------------------------------
# Les secteurs sont LOCAUX à leur galaxie : leurs coordonnées se comptent depuis le centre de la
# galaxie, pas depuis l'origine du monde. C'est ce qui permet à une galaxie de bouger (et de se
# contracter vers son trou noir) en emportant tout son contenu : on calcule une fois la place d'un
# système dans sa galaxie, et sa place dans le monde s'en déduit à chaque instant.
_secteurs = {}        # (graine, cle de la galaxie, sx, sy) -> Systeme LOCAL, ou None
_SECTEURS_GARDES = 400_000   # au-delà, on vide le cache (un secteur pèse quelques centaines d'octets)


def oublier_tout():
    """Vide les caches (changement de monde)."""
    _secteurs.clear()
    _galaxies.clear()
    _centres.clear()


def secteur_de(x, y):
    """Le secteur (sx, sy) qui contient la case (x, y)."""
    return math.floor((x - SECTEUR / 2) / SECTEUR + 0.5), math.floor((y - SECTEUR / 2) / SECTEUR + 0.5)


def systeme_du_secteur(graine, galaxie, sx, sy):
    """Le système du secteur (sx, sy) de cette galaxie, en coordonnées LOCALES (depuis son centre),
    ou None s'il n'y en a pas. Calculé une fois puis gardé. Pour l'avoir dans le monde, voir
    `_dans_le_monde` : il faut l'instant, puisque la galaxie bouge."""
    cle = (graine, galaxie.cle, sx, sy)
    if cle not in _secteurs:
        if len(_secteurs) > _SECTEURS_GARDES:
            _secteurs.clear()
        _secteurs[cle] = _tirer_secteur(graine, galaxie, sx, sy)
    return _secteurs[cle]


def _dans_le_monde(systeme, gx, gy, k):
    """Le système, placé dans le monde : sa position locale est multipliée par `k` (l'aspiration vers
    le trou noir) puis ramenée au centre de la galaxie, qui est en (gx, gy) à cet instant."""
    return systeme._replace(cx=gx + systeme.cx * k, cy=gy + systeme.cy * k)


_centres = {}   # (graine, nom de la galaxie) -> le Systeme de son trou noir supermassif


def systeme_central(graine, galaxie):
    """Le trou noir supermassif au milieu de la galaxie, avec les étoiles happées par son orbite —
    comme Sagittarius A* au centre de la Voie lactée. C'est un Systeme comme les autres : il se
    dessine, se découvre et se sauvegarde exactement pareil."""
    cle = (graine, galaxie.cle)
    if cle not in _centres:
        tirage = random.Random(f"centre:{graine}:{galaxie.cle}")
        astres = [Etoile(galaxie.trou_noir, TROU_NOIR_COULEUR, 0, 0.0, 0.0, True)]
        for _ in range(tirage.randint(*TROU_NOIR_GALACTIQUE_ETOILES)):
            orbite = tirage.randint(*TROU_NOIR_GALACTIQUE_ORBITE)
            _, couleur, bornes, _ = tirage.choices(ETOILES, [e[3] for e in ETOILES])[0]
            astres.append(Etoile(
                rayon=tirage.randint(*bornes),
                couleur=couleur,
                separation=orbite,
                vitesse=TROU_NOIR_GALACTIQUE_KEPLER / orbite ** 1.5 * tirage.choice((-1, 1)),
                angle0=tirage.uniform(0, math.tau),
                trou_noir=False))
        rayon = max(e.separation + e.rayon for e in astres)
        _centres[cle] = Systeme(f"centre:{galaxie.cle}", f"{galaxie.nom} A*",
                                galaxie.cx, galaxie.cy, "trou_noir", "trou noir supermassif",
                                tuple(astres), (), rayon, TROU_NOIR_COULEUR, galaxie.nom)
    return _centres[cle]


def _tirer_secteur(graine, galaxie, sx, sy):
    """Le système du secteur (sx, sy) de cette galaxie, en coordonnées locales, ou None : hors de la
    galaxie, sur le trou noir central, sur la carte dessinée à la main, ou simplement pas tiré."""
    tirage = random.Random(f"systeme:{graine}:{galaxie.cle}:{sx}:{sy}")
    # au milieu du secteur, à ECART_SECTEUR près : c'est ce décalage borné qui garantit
    # que deux systèmes voisins ne se chevauchent jamais (voir SECTEUR)
    ecart = round(SECTEUR * ECART_SECTEUR)
    lx = sx * SECTEUR + SECTEUR // 2 + tirage.randint(-ecart, ecart)
    ly = sy * SECTEUR + SECTEUR // 2 + tirage.randint(-ecart, ecart)
    distance = math.hypot(lx, ly)
    if distance < EXCLUSION_CENTRE:
        return None  # (le trou noir supermassif occupe le milieu : voir systeme_central)
    if distance > galaxie.rayon:
        return None  # (au-delà du bord de la galaxie : le vide intergalactique)
    # la carte dessinée à la main est à l'origine du MONDE : on écarte sa place
    if math.hypot(galaxie.cx + lx, galaxie.cy + ly) < EXCLUSION:
        return None
    if tirage.random() >= CHANCE * _densite(galaxie, lx, ly):
        return None
    return _construire(tirage, f"{galaxie.cle}|{sx}:{sy}", lx, ly, galaxie.nom)


def _lunes(tirage, cle_planete, nom_planete, taille_planete):
    """Les lunes d'une planète : un tuple de Lune, souvent vide.

    COMBIEN ? On ajoute une lune, puis on retire un jeton : tant qu'il passe, une lune de plus. Il n'y a
    donc pas de maximum — mais la probabilité d'en avoir n décroît géométriquement (chance^n). Une
    planète à deux ou trois lunes est banale, une à dix est remarquable, et mille lunes reste possible
    sans jamais arriver (10^-207 pour une géante gazeuse : voir LUNE_CHANCE).

    OÙ ? Toutes dans un disque de LUNE_ORBITE_MAX cases autour de la planète, réparties régulièrement :
    peu de lunes = bien espacées (LUNE_ECART), beaucoup = serrées. Le cortège ne déborde donc jamais sur
    l'orbite de la planète voisine, même avec mille lunes."""
    # une grosse planète retient plus de lunes : la chance monte avec sa taille
    k = min(1.0, (taille_planete - min(TAILLES)) / max(1, LUNE_TAILLE_MAX - min(TAILLES)))
    chance = LUNE_CHANCE + (LUNE_CHANCE_GROSSE - LUNE_CHANCE) * k
    combien = 0
    while tirage.random() < chance:
        combien += 1
    if not combien:
        return ()

    interieur = taille_planete / 2 + LUNE_MARGE          # la première lune ne touche pas la planète
    dehors = min(LUNE_ORBITE_MAX, interieur + LUNE_ECART * combien)
    lunes = []
    for numero in range(combien):
        # réparties de `interieur` à `dehors` (une seule lune : à mi-chemin)
        part = (numero + 1) / (combien + 1) if combien > 1 else 0.5
        orbite = interieur + (dehors - interieur) * part
        taille = max(LUNE_TAILLE_MIN, round(taille_planete * tirage.uniform(*LUNE_PART)))
        lunes.append(Lune(
            cle=f"{cle_planete}:{numero}",
            nom=f"{nom_planete} {_lettres(numero)}",
            orbite=orbite,
            taille=taille,
            type="lunaire",
            couleur=tirage.choice(PALETTES["lunaire"]),
            vitesse=LUNE_KEPLER / orbite ** 1.5 * tirage.choice((-1, 1)),
            angle0=tirage.uniform(0, math.tau),
        ))
    return tuple(lunes)


def rayon_planete(planete):
    """De quoi contenir la planète ET ses lunes, en cases (depuis le centre de la planète)."""
    return max([planete.taille / 2] + [l.orbite + l.taille / 2 for l in planete.lunes])


def _construire(tirage, cle, cx, cy, galaxie):
    """Un système solaire complet, tiré de `tirage` (déjà semé par la graine et le secteur).
    `cle` l'identifie de façon unique (les coordonnées de son secteur)."""
    nom = _nom(tirage)
    de = tirage.random()
    if de < CHANCE_TROU_NOIR:
        type_s = "trou_noir"
    elif de < CHANCE_TROU_NOIR + CHANCE_BINAIRE:
        type_s = "binaire"
    else:
        type_s = "simple"

    # --- l'astre (ou les astres) du centre ---
    if type_s == "trou_noir":
        genre = "trou noir"
        rayon = tirage.randint(*TROU_NOIR_RAYON)
        etoiles = [Etoile(rayon, TROU_NOIR_COULEUR, 0, 0.0, 0.0, True)]
        couleur = TROU_NOIR_COULEUR
        orbite_min = rayon * 6
    else:
        genres = [e[0] for e in ETOILES]
        poids = [e[3] for e in ETOILES]
        genre = tirage.choices(genres, poids)[0]
        _, couleur, bornes, _ = next(e for e in ETOILES if e[0] == genre)
        if type_s == "binaire":
            genre = f"{genre} double"
            separation = tirage.randint(*BINAIRE_SEPARATION)
            vitesse = tirage.uniform(*BINAIRE_VITESSE) * tirage.choice((-1, 1))
            angle0 = tirage.uniform(0, math.tau)
            etoiles = [Etoile(tirage.randint(*bornes), couleur, separation, vitesse, angle0, False),
                       Etoile(tirage.randint(*bornes), couleur, separation, vitesse,
                              angle0 + math.pi, False)]
            orbite_min = separation * 3  # (les planètes tournent autour des deux soleils, bien plus loin)
        else:
            etoiles = [Etoile(tirage.randint(*bornes), couleur, 0, 0.0, 0.0, False)]
            orbite_min = etoiles[0].rayon * 5

    # --- les planètes, de la plus proche à la plus lointaine ---
    planetes = []
    orbite = max(orbite_min, tirage.randint(*ORBITE_PREMIERE))
    for numero in range(tirage.randint(*NB_PLANETES)):
        type_p = tirage.choice(TYPES)
        taille = tirage.choice(TAILLES)
        planetes.append(Planete(
            cle=f"{cle}/{numero}",
            nom=f"{nom} {_ROMAINS[numero]}",
            orbite=orbite,
            taille=taille,
            type=type_p,
            couleur=tirage.choice(PALETTES[type_p]),
            vitesse=KEPLER / orbite ** 1.5 * tirage.choice((-1, 1)),
            angle0=tirage.uniform(0, math.tau),
            lunes=_lunes(tirage, f"{cle}/{numero}", f"{nom} {_ROMAINS[numero]}", taille),
        ))
        orbite += tirage.randint(*ORBITE_ECART)

    # de quoi contenir tout le système : l'orbite la plus large (plus la planète et ses lunes dessus),
    # ou les astres
    rayon_total = max([p.orbite + rayon_planete(p) for p in planetes]
                      + [e.separation + e.rayon for e in etoiles])
    return Systeme(cle, nom, cx, cy, type_s, genre, tuple(etoiles), tuple(planetes), rayon_total,
                   couleur, galaxie)


def systemes_dans(graine, x0, y0, x1, y1, temps=0.0, budget=None):
    """Les systèmes qui touchent le rectangle (x0, y0)-(x1, y1), en cases du MONDE, à l'instant
    `temps` : ([Systeme, ...], complet). Les systèmes renvoyés sont déjà placés dans le monde.

    On commence par écarter les galaxies qui ne touchent pas le rectangle (il y en a moins de trente :
    c'est immédiat). Pour chacune de celles qui restent, on ramène le rectangle dans SES coordonnées
    — c'est là que le mouvement et l'aspiration sont annulés — et on ne calcule que les secteurs de
    cette tranche-là. C'est tout l'intérêt : on n'engendre que ce qu'on regarde.

    `budget` borne le nombre de secteurs NOUVEAUX calculés pendant cet appel ; au-delà on s'arrête et
    `complet` vaut False (l'appel suivant reprendra où on en est, les secteurs déjà calculés étant
    gardés). C'est ce qui empêche un dézoom brutal — ou « découvrir toute la carte » (F3) — de bloquer
    le jeu : au pire la carte se remplit en quelques images."""
    if graine is None:
        return [], True
    k = aspiration(temps)
    trouves = []
    neufs = 0
    complet = True
    for galaxie in galaxies(graine):
        gx, gy = position_galaxie(galaxie, temps)
        portee = galaxie.rayon * k + RAYON_MAX
        if gx + portee < x0 or gx - portee > x1 or gy + portee < y0 or gy - portee > y1:
            continue  # (cette galaxie est hors du rectangle : rien à calculer dedans)
        # le rectangle, vu depuis la galaxie : on défait le déplacement puis l'aspiration
        lx0 = max(-galaxie.rayon, (x0 - gx) / k - RAYON_MAX)
        ly0 = max(-galaxie.rayon, (y0 - gy) / k - RAYON_MAX)
        lx1 = min(galaxie.rayon, (x1 - gx) / k + RAYON_MAX)
        ly1 = min(galaxie.rayon, (y1 - gy) / k + RAYON_MAX)
        sx0, sy0 = secteur_de(lx0, ly0)
        sx1, sy1 = secteur_de(lx1, ly1)
        for sx in range(sx0, sx1 + 1):
            for sy in range(sy0, sy1 + 1):
                if (graine, galaxie.cle, sx, sy) not in _secteurs:
                    if budget is not None and neufs >= budget:
                        complet = False
                        continue  # (calculé à un prochain appel)
                    neufs += 1
                local = systeme_du_secteur(graine, galaxie, sx, sy)
                if local is None:
                    continue
                systeme = _dans_le_monde(local, gx, gy, k)
                if (systeme.cx + systeme.rayon >= x0 and systeme.cx - systeme.rayon <= x1
                        and systeme.cy + systeme.rayon >= y0 and systeme.cy - systeme.rayon <= y1):
                    trouves.append(systeme)
        # le trou noir supermassif n'est pas sur la grille des secteurs : il EST le centre
        centre = systeme_central(graine, galaxie)._replace(cx=gx, cy=gy)
        if (centre.cx + centre.rayon >= x0 and centre.cx - centre.rayon <= x1
                and centre.cy + centre.rayon >= y0 and centre.cy - centre.rayon <= y1):
            trouves.append(centre)
    return trouves, complet


def systemes_autour(graine, x, y, rayon, temps=0.0, budget=None):
    """Les systèmes à moins de `rayon` cases du point (x, y) à l'instant `temps`."""
    trouves, complet = systemes_dans(graine, x - rayon, y - rayon, x + rayon, y + rayon,
                                     temps, budget)
    return ([s for s in trouves
             if math.hypot(s.cx - x, s.cy - y) <= rayon + s.rayon], complet)


def trous_noirs_autour(graine, x, y, rayon, temps=0.0):
    """[(x, y, rayon en cases), ...] des trous noirs à moins de `rayon` cases de (x, y) : ceux des
    centres de galaxies comme ceux des systèmes. Sert à l'aspiration du héros (voir monde/aspire.py)."""
    trouves = []
    for systeme in systemes_autour(graine, x, y, rayon, temps)[0]:
        for etoile in systeme.etoiles:
            if not etoile.trou_noir:
                continue
            ex, ey = position_etoile(systeme, etoile, temps)
            if math.hypot(ex - x, ey - y) <= rayon:
                trouves.append((ex, ey, etoile.rayon))
    return trouves


# ---------------------------------------------------------------------------
# Où sont les corps à un instant donné
# ---------------------------------------------------------------------------
def position_etoile(systeme, etoile, temps):
    """(x, y) en cases de cette étoile à l'instant `temps` (secondes de jeu)."""
    if not etoile.separation:
        return systeme.cx, systeme.cy
    angle = etoile.angle0 + etoile.vitesse * temps
    return (systeme.cx + math.cos(angle) * etoile.separation,
            systeme.cy + math.sin(angle) * etoile.separation)


def position_planete(systeme, planete, temps):
    """(x, y) en cases de cette planète à l'instant `temps` (secondes de jeu)."""
    angle = planete.angle0 + planete.vitesse * temps
    return (systeme.cx + math.cos(angle) * planete.orbite,
            systeme.cy + math.sin(angle) * planete.orbite)


def position_lune(px, py, lune, temps):
    """(x, y) en cases de cette lune, sa planète étant en (px, py) : elle tourne autour d'elle, et
    la planète tourne elle-même autour de son étoile (voir position_planete)."""
    angle = lune.angle0 + lune.vitesse * temps
    return px + math.cos(angle) * lune.orbite, py + math.sin(angle) * lune.orbite


def corps(systeme, temps):
    """Tous les corps du système à l'instant `temps`, positions en cases :
    ([(x, y, etoile), ...], [(x, y, planete), ...], [(x, y, lune), ...]).

    Les lunes sont à part et non rangées dans leur planète : celui qui dessine n'a qu'à les traiter
    comme de petites planètes (elles ont les mêmes champs, voir Lune)."""
    etoiles = [(*position_etoile(systeme, e, temps), e) for e in systeme.etoiles]
    planetes = []
    lunes = []
    for planete in systeme.planetes:
        px, py = position_planete(systeme, planete, temps)
        planetes.append((px, py, planete))
        for lune in planete.lunes:
            lunes.append((*position_lune(px, py, lune, temps), lune))
    return etoiles, planetes, lunes


if __name__ == "__main__":
    import sys
    import time
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    # récapitulatif pour vérifier les réglages (python code/monde/systemes.py)
    amas = galaxies("demo")
    print(f"{len(amas)} galaxies, l'univers fait ±{GALAXIE_PORTEE * GALAXIE_CELLULE} cases")
    for g in amas[:5]:
        print(f"  {g.nom:8s} {g.type:12s} rayon {g.rayon:6d} à ({g.cx}, {g.cy})")

    depart = time.perf_counter()
    liste, complet = systemes_dans("demo", -25000, -25000, 25000, 25000)
    duree = time.perf_counter() - depart
    binaires = [s for s in liste if s.type == "binaire"]
    trous = [s for s in liste if s.type == "trou_noir"]
    print(f"\ngalaxie de départ : {len(liste)} systèmes en {duree * 1000:.0f} ms")
    print(f"  {len(binaires)} à deux soleils ({len(binaires) / max(1, len(liste)):.1%}), "
          f"{len(trous)} trous noirs ({len(trous) / max(1, len(liste)):.1%})")
    proche = min(liste, key=lambda s: s.cx ** 2 + s.cy ** 2)
    print(f"  le plus proche : {proche.nom} ({proche.genre}) à "
          f"{math.hypot(proche.cx, proche.cy):.0f} cases, {len(proche.planetes)} planètes")

    # --- les lunes : la loi « une de plus est toujours possible, mais de moins en moins probable » ---
    toutes = [p for s in liste for p in s.planetes]
    compte = {}
    for p in toutes:
        compte[len(p.lunes)] = compte.get(len(p.lunes), 0) + 1
    total = sum(len(p.lunes) for p in toutes)
    print(f"\n{total} lunes pour {len(toutes)} planètes ({total / max(1, len(toutes)):.2f} par planète)")
    for n in sorted(compte):
        print(f"  {n:3d} lune(s) : {compte[n]:4d} planètes ({compte[n] / len(toutes):6.2%})")
    record = max(toutes, key=lambda p: len(p.lunes))
    print(f"  record : {record.nom} ({record.type}, {record.taille} cases) en a {len(record.lunes)}")
    # vérification : le cortège d'une planète ne déborde jamais sur l'orbite de sa voisine
    debord = max(rayon_planete(p) for p in toutes)
    print(f"  cortège le plus large : {debord:.1f} cases de rayon "
          f"(écart minimal entre deux orbites : {ORBITE_ECART[0]})")
