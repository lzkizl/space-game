# =============================================
# ==== Réglages généraux du jeu
# =============================================
from pathlib import Path

# Dossier du projet (celui qui contient code/, image/, map/...) : les chemins
# fonctionnent ainsi quel que soit le dossier depuis lequel on lance le jeu.
RACINE = Path(__file__).resolve().parent.parent.parent

FPS = 60
MAP_PATH = str(RACINE / "map" / "map_1.tmx")

# Zoom (molette)
ZOOM_MIN = 0.5
ZOOM_MAX = 2.0
ZOOM_PAS = 1.1  # facteur appliqué à chaque cran de molette

# Robot
ROBOT_IMAGE = RACINE / "image" / "image" / "robot.png"

# Météorites (décor)
METEORITE_IMAGE = RACINE / "image" / "image" / "meteroite.png"
METEORITE_DELAI = (4, 10)       # secondes entre deux apparitions (min, max)
METEORITE_VITESSE = (150, 450)    # pixels monde par seconde (min, max)
METEORITE_TAILLE = (0.12, 0.32)  # facteur appliqué à l'image (min, max)
METEORITE_MARGE = 150             # distance hors de la vue où elles apparaissent
METEORITE_MAX = 6               # nombre maximum à l'écran

# Astéroïdes de soufre (des météorites plus rares, plus grosses et plus lentes)
ASTEROIDE_IMAGE = RACINE / "image" / "image" / "asteroide_soufre.png"
ASTEROIDE_CHANCE = 0.10         # probabilité qu'une apparition soit un astéroïde
ASTEROIDE_VITESSE = (100, 250)    # pixels monde par seconde (min, max)
SHARD_IMAGE = RACINE / "image" / "image" / "meteorite_shard.png"
SHARD_CHANCE = 0.1             # probabilité qu'une apparition soit un astéroïde de shard
SHARD_VITESSE = (100, 250)       # pixels monde par seconde (min, max)
SHARD_TAILLE = (0.05, 0.15)       # facteur appliqué à l'image (min, max) ; plus gros = plus de butin
ASTEROIDE_TAILLE = (0.05, 0.15)  # facteur appliqué à l'image (min, max) ; plus gros = plus de butin
URANIUM_IMAGE = RACINE / "image" / "image" / "meteorite_uranium.png"
URANIUM_CHANCE = 0.06            # probabilité qu'une apparition soit un astéroïde d'uranium
URANIUM_VITESSE = (80, 200)      # pixels monde par seconde (min, max)
URANIUM_TAILLE = (0.05, 0.15)    # facteur appliqué à l'image (min, max) ; plus gros = plus de butin

# Décor de l'espace, tiré de la graine du monde (voir monde/debris.py). Pour chaque couche :
# nombre par morceau de 16x16 cases (min, max), part des morceaux qui sont des « champs » (bien
# plus denses) et combien de fois plus, taille à l'écran (pixels, min, max ; les petits sont plus
# fréquents), luminosité (min, max ; les petits sont plus sombres) et profondeur (vitesse de
# défilement par rapport au monde : 1 = avec le monde, plus petit = plus loin derrière).
# Débris de vaisseaux (images du dossier image/image/debris), dans le monde
DEBRIS_DOSSIER = RACINE / "image" / "image" / "debris"
DEBRIS_PAR_CHUNK = (3, 8)
DEBRIS_CHAMP_CHANCE = 0.12
DEBRIS_CHAMP_FACTEUR = 4
DEBRIS_TAILLE = (50, 220)
DEBRIS_LUMIERE = (0.7, 1.0)
DEBRIS_PROFONDEUR = 1.0
# Astéroïdes lointains, loin derrière (ils défilent plus lentement : effet de profondeur)
ASTEROIDES_FOND_IMAGE = RACINE / "image" / "espace" / "asteroide_256x256.png"
ASTEROIDES_FOND_PAR_CHUNK = (14, 30)
ASTEROIDES_FOND_CHAMP_CHANCE = 0.2
ASTEROIDES_FOND_CHAMP_FACTEUR = 3
ASTEROIDES_FOND_TAILLE = (10, 120)
ASTEROIDES_FOND_LUMIERE = (0.22, 0.5)
ASTEROIDES_FOND_PROFONDEUR = 0.4

ROBOT_VITESSE = 600               # pixels monde par seconde
ROBOT_VITESSE_ROTATION = 8        # radians par seconde (il pivote vers là où il va)
ROBOT_RAYON_DETECTION = 900       # distance de sa base à laquelle il repère une météorite
ROBOT_DISTANCE_MAX = 1500         # distance max de sa base : au-delà il abandonne la poursuite
ROBOT_DISTANCE_PRISE = 50         # distance à laquelle il ramasse la météorite

# Vie du héros (points de vie)
VIE_MAX = 100
VIE_POS = (50, 840)               # position du texte à l'écran

# Aliens : ils foncent sur le héros et le blessent au contact (aucune défense pour le moment)
ALIEN_IMAGE = RACINE / "image" / "image" / "alien.png"
ALIEN_TAILLE = (64, 64)           # taille à l'écran (pixels monde)
ALIEN_DELAI = (90, 150)           # secondes entre deux attaques (min, max), tirées au hasard
ALIEN_TROUPE = (1, 10)            # aliens par attaque (min, max), tirés au hasard ; ils arrivent groupés
ALIEN_VITESSE = 250               # pixels monde par seconde
ALIEN_DEGATS = 5                  # HP perdus par seconde et par alien au contact du héros
ALIEN_MARGE = 150                 # distance hors de la vue où ils apparaissent
ALIEN_MAX = 20                    # nombre maximum en même temps (pas de nouvelle attaque au-delà)

VAISSEAU_DELAI = (180, 500)      # secondes entre deux vaisseaux ennemis (min, max)
VAISSEAU_MAX = 3                 # nombre maximum en même temps
VAISSEAU_HP = 25                  # tirs de tourelle qu'il faut pour le détruire
VAISSEAU_IMAGE = RACINE / "image" / "image" / "vaisseau.png"  # le nez pointe vers le haut
VAISSEAU_TAILLE = 220             # plus grande dimension de l'image à l'écran (pixels monde)
VAISSEAU_VITESSE = 220            # pixels monde par seconde
VAISSEAU_DISTANCE = 400           # distance à laquelle il tourne autour du héros
VAISSEAU_CADENCE = 1.2            # secondes entre deux tirs
VAISSEAU_BALLE_VITESSE = 550      # pixels monde par seconde (on peut l'esquiver)
VAISSEAU_BALLE_DEGATS = 10        # HP perdus par tir qui touche le héros
VAISSEAU_CHANCE_BASE = 0.6        # part de ses tirs qui visent une fondation plutôt que le héros
VAISSEAU_PORTEE_BASE = 900        # distance max à laquelle il vise une fondation (pixels monde)
VAISSEAU_COUPS_BASE = 5           # tirs qu'il faut pour détruire une fondation (et tout ce qu'il y a dessus)
VAISSEAU_MARGE = 250             # distance hors de la vue où il apparaît
ALIEN_HP = 5                     # coups qu'il faut pour tuer un alien (1 HP par coup de tourelle)

# Trou noir africain : il dérive dans l'espace, attire le héros et avale les météorites
TROU_NOIR_IMAGE = RACINE / "image" / "image" / "trou_afriquain.png"
TROU_NOIR_TAILLE = 180          # diamètre à l'écran (pixels monde)
TROU_NOIR_VITESSE = 40          # pixels monde par seconde (il dérive lentement)
TROU_NOIR_RAYON_AVALEUR = 90    # rayon en pixels pour avaler les météorites
TROU_NOIR_RAYON_GRAVITE = 700   # rayon d'attraction gravitationnelle (pixels monde)
TROU_NOIR_FORCE_GRAVITE = 200   # force d'attraction (accélération en px/s²)
TROU_NOIR_DEGATS = 20           # HP/s perdus dans la zone dangereuse
TROU_NOIR_ZONE_DANGER = 220     # rayon de la zone où le héros prend des dégâts
TROU_NOIR_DELAI = (240, 480)    # secondes avant la prochaine apparition (min, max)
TROU_NOIR_MARGE = 300           # distance hors de la vue où il apparaît

# Tourelles : elles s'orientent vers l'alien le plus proche et lui tirent dessus
TOURELLE_PORTEE = 1200             # distance max de tir (pixels monde)
TOURELLE_CADENCE = 0.75            # secondes entre deux tirs
TOURELLE_ROTATION = 270           # degrés par seconde
TOURELLE_VITESSE_BALLE = 1200     # pixels monde par seconde
TOURELLE_DEGATS = 1               # HP retirés à l'alien par tir
TOURELLE_TIRS_PAR_MUNITION = 10   # tirs que donne une munition chargée dans la tourelle
TOURELLE_STOCK_MAX = 100          # tirs qu'une tourelle peut garder en réserve

# Fermeture du terminal après la fin du jeu
DELAI_FERMETURE = 10          # secondes avant de fermer le terminal
MOT_POUR_GARDER = "caca"      # à taper dans le terminal pour ne pas le fermer

COULEUR_FOND = (0, 0, 0)
COULEUR_TEXTE = (255, 255, 255)
COULEUR_ALERTE = (255, 80, 80)  # texte en rouge (énergie insuffisante)

# Couleurs des barres du HUD
COULEUR_JAUGE_VIE = (220, 50, 50)        # rouge
COULEUR_JAUGE_OXYGENE = (80, 220, 230)   # cyan
COULEUR_JAUGE_EAU = (60, 120, 255)       # bleu
COULEUR_JAUGE_FAIM = (240, 150, 40)      # orange

# Oxygène
OXYGENE_MAX = 100
OXYGENE_PERTE = 0.01  # perte par frame au contact d'une tuile solide
OXYGENE_CONSO_HERO = 1  # oxygène consommé par le héros par seconde
OXYGENE_POS = (50, 1000)  # position du texte à l'écran
ENERGIE_POS = (50, 960)   # position du texte d'énergie (en W)

# Eau
EAU_MAX = 100
EAU_CONSO_HERO = 0.3    # eau consommée par le héros par seconde
EAU_BOUTEILLE = 40      # eau rendue par une bouteille d'eau
EAU_POS = (50, 920)     # position du texte à l'écran

# Faim
FAIM_MAX = 100
FAIM_CONSO_HERO = 0.2   # faim perdue par seconde (la jauge se vide en ~8 min)
FAIM_BAIE = 15          # faim rendue par une baie mangée
FAIM_POS = (50, 880)    # position du texte à l'écran

# Baies produites par les plantes
BAIE_DELAI = 20         # secondes pour qu'une plante alimentée produise une baie
BAIE_STOCK_MAX = 80     # baies qu'une plante peut garder en réserve
FIBRE_DELAI = 30        # secondes pour qu'une plante alimentée produise une fibre
FIBRE_STOCK_MAX = 20    # fibres qu'une plante peut garder en réserve
VIE_KIT = 40            # HP rendus par un kit médical

# Pose de tuiles
CALQUE_BASE = "base"          # calque Tiled des tuiles de base
CALQUE_PLANTES = "sur_fonda"  # calque Tiled des plantes
CALQUE_EPAVES = "vaisseau_casse"        # calque Tiled des navettes échouées (et de quelques astéroïdes)
TILESET_EPAVES = "vaisseau_cassé.tsx"   # tileset des navettes échouées (une navette = 5x5 tuiles)
VIDE_GID = 6           # tuile de vide du calque base (id 5 dans Tiled) : celle qui bloque le héros
VIDE_GIDS = (0, VIDE_GID)  # tuiles du calque base qui sont du vide (rien ou vide de l'espace)
# Planètes : une tuile du tileset PLANETES_TILESET sert de repère dans Tiled ; le jeu dessine à sa place la
# grande image de la planète, centrée sur la tuile (voir monde/planetes.py), aussi sur la grande carte.
MARS_TAILLE = 50   # diamètre de Mars, en cases (1 case = 128 pixels)
SOLEIL_TAILLE = 80   # diamètre du Soleil, en cases
VELMARIS_TAILLE = 60   # diamètre de Velmaris, en cases
TERRE_TAILLE = 60   # diamètre de la Terre, en cases
ETOILE_ROUGE_TAILLE = 65  # diamètre de l'Étoile rouge mourante, en cases
INFERNUS_TAILLE = 42      # diamètre d'Infernus, en cases
PLANETES_TILESET = "planette_spawn.tsx"   # tileset des repères de planètes
# id de la tuile dans ce tileset (comme dans Tiled) -> (image dans image/image/, diamètre en cases, nom,
# carte dans map/ où l'on descend, ou None : on ne peut pas y descendre ; voir monde/orbite.py,
# couleur de sa boule sur la grande carte)
PLANETES = {
    0: ("mars_detoure.png", MARS_TAILLE, "Mars", "mars.tmx", (205, 75, 45)),   # Mars : placée autour du Soleil, boule rouge
    1: ("soleil.png", SOLEIL_TAILLE, "Soleil", None, (255, 215, 60)),          # Soleil : tuile 1 (S1), boule jaune
    2: ("velmaris.png", VELMARIS_TAILLE, "Velmaris", "velmaris.tmx", (140, 70, 230)),  # Velmaris : autour du Soleil, boule violette
    3: ("Soleil_bleu.png", SOLEIL_TAILLE, "Soleil bleu", None, (90, 160, 255)),  # Soleil bleu : tuile 3 (S2), boule bleue
    4: ("terre.png", TERRE_TAILLE, "Terre", "terre.tmx", (50, 130, 220)),       # Terre : autour du Soleil bleu, boule bleue
    5: ("etoile_rouge.png", ETOILE_ROUGE_TAILLE, "Étoile rouge", None, (200, 55, 25)),  # Étoile rouge mourante : loin, boule rouge sombre
    6: ("infernus.png", INFERNUS_TAILLE, "Infernus", "infernus.tmx", (55, 15, 10)),     # Infernus : autour de l'Étoile rouge, boule noire/rouge
}
# Planètes qui tournent autour d'un astre (pas de repère à poser dans Tiled : le repère de l'astre est le
# centre) : id de la planète -> (id de l'astre, distance en cases, direction de départ en degrés (0 = à droite,
# 90 = en bas, 180 = à gauche, 270 = en haut), durée d'un tour complet en secondes de jeu)
MARS_DUREE_ORBITE = 4 * 3600   # Mars fait le tour du Soleil en 4 heures de jeu (très lentement)
VELMARIS_DUREE_ORBITE = 23 * 3600   # plus loin, donc plus lent : 23 heures de jeu (comme les vraies planètes)
TERRE_DUREE_ORBITE = MARS_DUREE_ORBITE // 3   # la Terre tourne 3 fois plus vite que Mars : 80 minutes de jeu
INFERNUS_DUREE_ORBITE = 5400   # 1h30 de jeu : orbite rapide et mortelle autour de l'Étoile rouge
PLANETES_AUTOUR = {
    0: (1, 500, 0, MARS_DUREE_ORBITE),   # Mars : à 500 cases du Soleil, part de sa droite
    2: (1, 1597, 180, VELMARIS_DUREE_ORBITE),   # Velmaris : à 1597 cases du Soleil, part de sa gauche
    4: (3, 750, 90, TERRE_DUREE_ORBITE),   # Terre : à 750 cases du Soleil bleu, part d'en dessous
    6: (5, 450, 135, INFERNUS_DUREE_ORBITE),  # Infernus : à 450 cases de l'Étoile rouge, part en diagonale bas-gauche
}
COULEUR_FOND_PLANETE = (20, 8, 4)   # sur une planète : derrière sa carte (pas de fond étoilé)
SPAWN_PLANETE_RAYON = 300   # en descendant sur une planète, on arrive au hasard à au plus 300 cases de son milieu
# sol des planètes généré au hasard, en biomes : carte dans map/ -> (tileset, liste des biomes, tuiles à
# remplacer). Un biome = {id de tuile dans ce tileset (comme dans Tiled): poids} : ses cases sont tirées parmi
# ces tuiles, les plus lourdes plus souvent. Partout où le premier calque de la carte est vide (hors de ce qui
# est dessiné, et dans ses trous) ou porte une des « tuiles à remplacer », la case prend une tuile de son biome
# (toujours la même pour une case donnée : voir Map.grille). Les biomes sont des zones d'environ BIOME_TAILLE
# cases, aux formes naturelles (voir monde/generation.py). Entre deux biomes, le sol de l'un déborde en douceur
# sur l'autre (celui qui est plus loin dans la liste passe par-dessus : voir Map._dessiner_transitions).
# Les tilesets sont fabriqués par code/outils/generer_tilesets.py : une colonne par biome, 4 variantes en dessous.
BIOME_TAILLE = 40


def _variantes(colonne, poids=(6, 3, 2, 2)):
    """Biome d'une colonne du tileset : ses 4 variantes (une par ligne), la première plus souvent."""
    return {colonne + 10 * ligne: p for ligne, p in enumerate(poids)}


SOLS_ALEATOIRES = {
    "terre.tmx": ("terre-tilset_1.tsx", [
        _variantes(0),   # 0 : prairie
        _variantes(1),   # 1 : sous-bois (herbe sombre, mousse, feuilles mortes)
        _variantes(2),   # 2 : prairie fleurie
        _variantes(3),   # 3 : savane (herbe sèche) : des acacias
        _variantes(4),   # 4 : sable
        _variantes(5),   # 5 : rocaille (beaucoup de minerai de fer et de cuivre)
    ]),
    "mars.tmx": ("mars-tilset.tsx", [
        _variantes(1),   # 0 : poussière rouge
        _variantes(2),   # 1 : basalte (roche sombre)
        _variantes(3),   # 2 : cratères
        _variantes(4),   # 3 : dunes
    ], (0,)),            # (la carte de Mars est dessinée avec la tuile 0 : elle est remplacée par les biomes)
    "velmaris.tmx": ("velmaris-tilset.tsx", [
        _variantes(1),   # 0 : poussière violette
        _variantes(2),   # 1 : obsidienne
        _variantes(3),   # 2 : failles lumineuses
        _variantes(4),   # 3 : champ de cristaux
    ]),
    # Infernus : planète apocalyptique — lave, cendres, feu éternel. 6 biomes Nether+.
    "infernus.tmx": ("infernus-tilset.tsx", [
        _variantes(1, (7, 4, 2, 1)),   # 0 : obsidienne calcinée (sombre, dominante)
        _variantes(2, (8, 5, 3, 1)),   # 1 : cendres de lune (poussière grise pâle)
        _variantes(3, (6, 4, 2, 1)),   # 2 : sol de braises incandescentes
        _variantes(4, (5, 3, 2, 1)),   # 3 : roche de magma (orange vif)
        _variantes(5, (7, 4, 2, 1)),   # 4 : basalte volcanique (colonnes noires)
        _variantes(6, (4, 3, 2, 1)),   # 5 : poussière de soufre (jaune-vert acide)
    ]),
}
# décor des biomes (arbres...) : carte -> {numéro du biome (sa place dans la liste de SOLS_ALEATOIRES):
# [(image dans image/image/, chance par case), ...]}. Seulement hors de ce qui est dessiné dans Tiled ; le
# tronc bloque le héros, qui passe devant ou derrière (voir monde/decors.py)
DECORS_BIOMES = {
    "terre.tmx": {3: [("arbre_savane.png", 0.004)]},   # la savane (biome 3, herbe jaune) : des acacias
}
ECART_DECORS = 4   # deux décors sont au moins à 4 cases l'un de l'autre (dans un même chunk)
# Cristaux lumineux (voir monde/cristaux.py) : tirés avec le sol, comme les décors. Carte -> {biome:
# [(couleur, chance par case), ...]} ; couleurs : "violet", "bleu", "rose" (images image/image/cristal_<couleur>.png).
# Sur une planète, E à côté d'un cristal en détache un shard ; il rétrécit, et disparaît après son dernier shard.
CRISTAUX_BIOMES = {
    "velmaris.tmx": {   # Velmaris : planète des cristaux lumineux
        0: [("violet", 0.004)],
        1: [("violet", 0.006), ("bleu", 0.002)],
        2: [("rose", 0.008), ("violet", 0.004)],
        3: [("bleu", 0.014), ("violet", 0.006)],
    },
    "infernus.tmx": {   # Infernus : cristaux de feu, formés sous la pression du magma
        2: [("rouge", 0.003)],                        # braises : cristaux de feu rouges
        3: [("ambre", 0.004), ("rouge", 0.002)],      # magma : cristaux ambre et rouges
        4: [("rouge", 0.002)],                        # basalte : rares cristaux rouge sombre
    },
}
# Gisements de minerai : tirés avec le sol comme les cristaux, mais sans lumière ; une foreuse posée dessus en
# extrait le minerai (voir structures/foreuses.py). Carte -> {biome: [(minerai, chance par case), ...]} ;
# minerais : "fer", "cuivre", "carbure" (images image/image/minerai_<minerai>.png, ressource extraite : voir
# MINERAIS dans monde/cristaux.py).
MINERAIS_BIOMES = {
    "terre.tmx": {   # la Terre : du fer et du cuivre (ni tungstène ni glace)
        0: [("fer", 0.0015), ("cuivre", 0.001)],   # prairie
        1: [("cuivre", 0.0015), ("fer", 0.001)],   # sous-bois
        2: [("fer", 0.0015), ("cuivre", 0.001)],   # prairie fleurie
        3: [("fer", 0.002), ("cuivre", 0.0015)],   # savane
        4: [("fer", 0.001)],                       # sable
        5: [("fer", 0.006), ("cuivre", 0.004)],    # rocaille : la plus riche
    },
    "mars.tmx": {    # Mars : du carbure de tungstène
        0: [("carbure", 0.001)],    # poussière rouge
        1: [("carbure", 0.004)],    # basalte
        2: [("carbure", 0.005)],    # cratères
        3: [("carbure", 0.0008)],   # dunes
    },
    "infernus.tmx": {   # Infernus : carbure formé sous la pression extrême du magma
        4: [("carbure", 0.003)],    # basalte volcanique : filons de carbure dans la roche noire
        0: [("carbure", 0.001)],    # obsidienne : traces rares de carbure
    },
}
ECART_CRISTAUX = 3         # deux cristaux / gisements (ou avec un arbre) sont au moins à 3 cases l'un de l'autre
ECART_FLUIDES = 6          # deux mares sont au moins à 6 cases l'une de l'autre
FLUIDE_RAYON = (2, 5)      # rayon d'une mare en cases (min, max)

# Fluides procéduraux sur les planètes : mares d'eau, d'acide, de pétrole ou de lave, selon le biome.
# Carte -> {numéro du biome: [(type, chance par case), ...]}
# Types : "eau", "acide", "petrole", "lave"
FLUIDES_BIOMES = {
    "terre.tmx": {
        0: [("eau", 0.0005)],     # prairie : mares
        1: [("eau", 0.0010)],     # sous-bois : marécages
        2: [("eau", 0.0004)],     # prairie fleurie : mares
        4: [("eau", 0.0003)],     # sable : oasis
    },
    "mars.tmx": {
        1: [("acide", 0.0006)],   # basalte : flaques d'acide
        2: [("lave", 0.0012)],    # cratères : lave en fusion
    },
    "velmaris.tmx": {
        0: [("petrole", 0.0007)], # poussière violette : pétrole noir
        2: [("acide", 0.0010)],   # failles lumineuses : acide corrosif
        3: [("petrole", 0.0006)], # champ de cristaux : pétrole
    },
    # Infernus : lave omniprésente, acide corrosif — aucune vie ne peut exister ici
    "infernus.tmx": {
        0: [("lave", 0.0030), ("acide", 0.0010)],   # obsidienne : failles de lave fréquentes
        1: [("lave", 0.0015), ("acide", 0.0006)],   # cendres de lune : mares mortes silencieuses
        2: [("lave", 0.0045), ("acide", 0.0012)],   # braises : lave partout sous les tisons
        3: [("lave", 0.0065)],                        # magma : rivières de lave omniprésentes
        4: [("lave", 0.0022), ("acide", 0.0008)],   # basalte : lave dans les fissures noires
        5: [("acide", 0.0045), ("lave", 0.0010)],   # soufre : lacs d'acide corrosif
    },
}
CRISTAL_SHARDS = (2, 4)    # shards dans un cristal (min, max) : un par appui sur E
MINERAI_QUANTITE = (60, 120)  # morceaux dans un gisement de minerai (min, max) : la foreuse en extrait un à la fois
CRISTAL_PORTEE = 170       # distance (pixels monde) à laquelle le héros peut récolter un cristal
# effet de profondeur : une planète est loin, elle défile moins vite que le monde quand on se déplace
# (1 = avec le monde, 0 = immobile à l'écran) ; elle est pile à sa place quand la caméra est centrée dessus
PLANETES_PROFONDEUR = 0.35
COULEUR_ZONE = (0, 255, 0, 90)  # zone de pose (vert translucide)
COULEUR_ZONE_BORDURE = (0, 255, 0)
COULEUR_DECONSTRUCTION = (255, 150, 0, 90)  # structure qu'on peut enlever (orange translucide)
COULEUR_DECONSTRUCTION_BORDURE = (255, 150, 0)
COULEUR_ZONE_REFUSEE = (255, 0, 0, 90)  # pose impossible (rouge translucide)
COULEUR_ZONE_REFUSEE_BORDURE = (255, 0, 0)
TAILLE_ICONE = (64, 64)  # taille des objets dans les cases de l'inventaire

# Monde procédural (page « Réglages du monde ») : hors de la carte fabriquée à la main,
# le monde est tiré de la graine, morceau de 16x16 cases par morceau
MONDE_DENSITE_VIDE = 0.45      # part des morceaux laissés vides (le vide entre les îles)
MONDE_CHANCE_NAVETTE = 0.03    # chance qu'un morceau ait une navette échouée (avec son butin)
MONDE_DELAI_DEFAUT = 10        # minutes avant les premières attaques (proposé à la création)
MONDE_DELAI_MAX = 60           # minutes (maximum réglable ; 0 = délai normal, aléatoire)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lanceur import lancer

    lancer()
















