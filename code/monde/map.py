import math
import os
import random
import xml.etree.ElementTree as ET
from collections import Counter

import pygame

from monde.generation import biome_de, morceau, morceaux_de_terrain, navette
from monde.planetes import PLANETES_GIDS, enregistrer as enregistrer_planetes
from systeme.settings import (BIOME_TAILLE, CALQUE_BASE, CALQUE_EPAVES, CALQUE_PLANTES, CRISTAUX_BIOMES,
                              DECORS_BIOMES, ECART_CRISTAUX, ECART_DECORS, ECART_FLUIDES, FLUIDE_RAYON,
                              FLUIDES_BIOMES, MAP_PATH, MINERAIS_BIOMES,
                              MONDE_CHANCE_NAVETTE, SOLS_ALEATOIRES, TILESET_EPAVES)

# calques que le jeu modifie (constructions, bases poussées...) : seuls ceux-là sont sauvegardés
CALQUES_SAUVES = (CALQUE_BASE, CALQUE_PLANTES)

# Les 3 bits de poids fort d'un gid encodent les flips (horizontal/vertical/
# diagonal) appliqués à la tuile dans Tiled. On les masque pour retrouver
# l'identifiant réel de la tuile dans le tileset.
GID_FLIP_MASK = 0x1FFFFFFF

# Tuiles qui bloquent le héros : seulement la tuile de vide (id 5 dans Tiled = gid 6)
SOLID_GIDS = {6}
# tronc d'un décor (arbre) : rectangle qui bloque le héros, en pixels, centré en bas de sa case
TRONC_LARGEUR = 40
TRONC_HAUTEUR = 24

# Transitions entre biomes : le sol du voisin déborde sur la case, avec un bord qui ondule
VOISINS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))
TRANSITION_LARGEUR = 0.45   # jusqu'où le voisin déborde, en part de la case
TRANSITION_ONDULATION = 0.2   # de combien ce bord ondule (en part de la case)
TRANSITION_DOUCEUR = 0.12   # largeur du fondu (en part de la case)
TRANSITION_CREUX = 1.75     # coin rentrant (deux côtés touchent l'autre biome) : arrondi, ce rayon fois plus grand
TRANSITION_VARIANTES = 3    # formes de bord différentes (tirées case par case : pas de motif répété)
TAILLE_MASQUE = 64          # les masques sont calculés à cette taille puis agrandis (plus rapide, plus doux)
_masques = {}               # (direction, variante, taille) -> masque


def _masque_transition(direction, variante, taille, creux=False):
    """Masque (blanc, alpha = 255 au bord touché, 0 plus loin) du sol d'un voisin qui déborde sur une case.
    `direction` = (dx, dy) du voisin : un côté (le bord entier) ou un coin (diagonale ; `creux` : coin rentrant,
    qui arrondit l'angle laissé par les deux côtés). Le bord ondule, mais pas aux extrémités : deux cases
    voisines se raccordent quelle que soit leur variante."""
    cle = (direction, variante, taille, creux)
    if cle not in _masques:
        tirage = random.Random(f"transition:{variante}")
        harmoniques = [(k, tirage.uniform(-1, 1) / k) for k in (1, 2, 3, 4)]
        plus_grande = max(abs(sum(a * math.sin(math.pi * k * i / 32) for k, a in harmoniques)) for i in range(33))
        harmoniques = [(k, a / plus_grande) for k, a in harmoniques]  # (l'ondulation va de -1 à 1)
        rayon = TRANSITION_CREUX if creux else 1
        n = TAILLE_MASQUE
        petit = pygame.Surface((n, n), pygame.SRCALPHA)
        dx, dy = direction
        coin = ((dx + 1) / 2 * n, (dy + 1) / 2 * n)
        for y in range(n):
            for x in range(n):
                px, py = x + 0.5, y + 0.5
                if dx and dy:   # coin : distance au coin, l'ondulation suit l'angle
                    distance = math.hypot(px - coin[0], py - coin[1])
                    t = math.atan2(abs(py - coin[1]), abs(px - coin[0])) / (math.pi / 2)
                elif dx:        # côté gauche ou droit
                    distance, t = abs(px - coin[0]), py / n
                else:           # côté haut ou bas
                    distance, t = abs(py - coin[1]), px / n
                ondulation = sum(a * math.sin(math.pi * k * t) for k, a in harmoniques)
                limite = (TRANSITION_LARGEUR * rayon + TRANSITION_ONDULATION * ondulation) * n
                v = min(1.0, max(0.0, (limite - distance) / (TRANSITION_DOUCEUR * n) + 0.5))
                petit.set_at((x, y), (255, 255, 255, round(255 * v * v * (3 - 2 * v))))
        _masques[cle] = pygame.transform.smoothscale(petit, (taille, taille))
    return _masques[cle]


# =============================================
# ==== Tileset : découpe l'image en tuiles individuelles
# =============================================
class Tileset:
    def __init__(self, firstgid, tsx_path):
        self.firstgid = firstgid
        self.nom = os.path.basename(tsx_path)  # nom du fichier .tsx (ex : "vaisseau_cassé.tsx")

        root = ET.parse(tsx_path).getroot()
        self.tilewidth = int(root.get("tilewidth"))
        self.tileheight = int(root.get("tileheight"))
        self.columns = int(root.get("columns"))
        self.tilecount = int(root.get("tilecount"))

        image_path = os.path.join(os.path.dirname(tsx_path), root.find("image").get("source"))
        self.image = pygame.image.load(image_path).convert_alpha()

        self._tiles = {}

    def get_tile(self, gid):
        local_id = gid - self.firstgid
        if local_id < 0 or local_id >= self.tilecount:
            return None

        if local_id not in self._tiles:
            col = local_id % self.columns
            row = local_id // self.columns
            rect = pygame.Rect(col * self.tilewidth, row * self.tileheight, self.tilewidth, self.tileheight)
            self._tiles[local_id] = self.image.subsurface(rect)

        return self._tiles[local_id]


# =============================================
# ==== Map : charge une carte Tiled "infinite" et ne garde en
# ==== mémoire que les chunks proches de la caméra (monde immense)
# =============================================
class Map:
    def __init__(self, tmx_path, cache_radius=2, planete=False):
        """`planete` : carte d'une planète (on y descend, voir orbite.py) : pas de repères de planètes dedans, même
        si son tileset y est (sinon ses gids seraient pris pour des repères partout, dans l'espace aussi)."""
        self.cache_radius = cache_radius
        self.tmx_path = tmx_path
        self.graine = None         # monde procédural (voir definir_graine) ; None = vide hors de la carte
        self._generes = {}         # chunk -> morceau généré à partir de la graine (partagé, non modifiable)
        self._morceaux_terrain = None  # morceaux de la carte qui servent au monde généré (voir morceaux_terrain)
        self._navettes = {}        # chunk -> calque des épaves généré (une navette échouée, ou vide)
        self._visibles = {}        # gid -> True si sa tuile n'est pas toute transparente
        self._opaques = {}         # gid -> True si sa tuile n'a aucun pixel transparent

        root = ET.parse(tmx_path).getroot()
        base_dir = os.path.dirname(tmx_path)

        self.tilewidth = int(root.get("tilewidth"))
        self.tileheight = int(root.get("tileheight"))

        self.planete = planete
        self.tilesets = []
        decalage = 0  # ajouté aux gids de la carte d'une planète (voir plus bas)
        if planete:
            # les constructions (tables de craft, coffres...) se posent aussi sur une planète : elle a le tileset
            # de l'espace (le premier de sa carte), avec les mêmes gids que là-haut, et ses propres tilesets
            # sont décalés juste après
            espace = ET.parse(MAP_PATH).getroot().find("tileset")
            tileset = Tileset(int(espace.get("firstgid")),
                              os.path.join(os.path.dirname(MAP_PATH), espace.get("source")))
            self.tilesets.append(tileset)
            decalage = tileset.firstgid + tileset.tilecount - 1
        for ts_node in root.findall("tileset"):
            firstgid = int(ts_node.get("firstgid")) + decalage
            tsx_path = os.path.join(base_dir, ts_node.get("source"))
            self.tilesets.append(Tileset(firstgid, tsx_path))
        self.tilesets.sort(key=lambda t: t.firstgid, reverse=True)
        self._gids_planetes = {} if planete else PLANETES_GIDS  # (repères dessinés à part : voir _render_chunk)
        # tuiles qui bloquent le héros (et lui font perdre de l'oxygène) : le vide de l'espace, pas sur une planète
        # (là, le gid 6 est une tuile de sol comme une autre : la rocaille de la Terre...)
        self._gids_solides = set() if planete else SOLID_GIDS
        self.obstacles = []        # rectangles (pixels monde) qui bloquent aussi le héros : socles des foreuses...
        if not planete:
            enregistrer_planetes(self)  # (les gids des repères de planètes dépendent des tilesets de la carte)

        # calques de tuiles : {nom_calque: {(chunk_x, chunk_y): [[gid,...],...]}}
        self.layers = {}
        self.chunk_size = 16  # taille par défaut des chunks Tiled

        for layer_node in root.findall("layer"):
            self.layers[layer_node.get("name")] = self._parse_layer(layer_node, decalage)
        # calques du sol d'une planète (dessinés dans Tiled) : les constructions se posent dessus
        self.calques_sol = set(self.layers) if planete else set()

        # sol généré au hasard, en biomes (carte d'une planète, voir SOLS_ALEATOIRES) : sur le premier calque,
        # les cases vides reçoivent une tuile de leur biome
        self.calque_sol = None
        self._biomes = []          # [(gids, poids), ...] : les tuiles de chaque biome
        self._remplacables = set() # gids dessinés dans la carte qui sont remplacés par le sol des biomes
        self._biome_de_gid = {}    # gid -> biome (aussi pour les tuiles dessinées : transitions avec leurs voisines)
        self._sols = {}            # chunk -> grille du premier calque, cases vides remplies (voir _sol)
        self._cases_biomes = {}    # chunk -> biome de chaque case (None : tuile dessinée d'aucun biome)
        self._decors_biomes = DECORS_BIOMES.get(os.path.basename(tmx_path), {})  # biome -> [(image, chance)]
        self._decors = {}          # chunk -> [(tx, ty, image), ...] : les décors (arbres) posés (voir _sol)
        # biome -> [(couleur ou minerai, chance)] : les cristaux lumineux, puis les gisements de minerai
        self._cristaux_biomes = {}
        for table in (CRISTAUX_BIOMES, MINERAIS_BIOMES):
            for biome, liste in table.get(os.path.basename(tmx_path), {}).items():
                self._cristaux_biomes.setdefault(biome, []).extend(liste)
        # chunk -> [(tx, ty, couleur ou minerai), ...] : les cristaux et les gisements (voir monde/cristaux.py)
        self._cristaux = {}
        # fluides procéduraux (eau, acide, pétrole, lave) : biome -> [(type, chance)] ; chunk -> [(tx,ty,type,rayon)]
        self._fluides_biomes = FLUIDES_BIOMES.get(os.path.basename(tmx_path), {})
        self._fluides = {}
        self._transitions = {}     # (biome, direction, variante) -> sol du biome découpé par son masque
        sol = SOLS_ALEATOIRES.get(os.path.basename(tmx_path))
        if sol is not None and self.layers:
            tileset, biomes, *remplacables = sol
            gids = self.gids_tileset(tileset)
            for tuiles in biomes:
                tuiles = {i: poids for i, poids in tuiles.items() if i < len(gids)}
                if tuiles:
                    self._biomes.append((tuple(gids[i] for i in tuiles), tuple(tuiles.values())))
            self._remplacables = {gids[i] for i in (remplacables[0] if remplacables else ()) if i < len(gids)}
            for biome, (gids_biome, _) in enumerate(self._biomes):
                for gid in gids_biome:
                    self._biome_de_gid.setdefault(gid, biome)
            if self._biomes:
                self.calque_sol = next(iter(self.layers))
        for nom in CALQUES_SAUVES:
            self.layers.setdefault(nom, {})  # (carte d'une planète : le jeu compte sur ces calques, même vides)
        self._vide = [[0] * self.chunk_size for _ in range(self.chunk_size)]  # chunk vide partagé (lecture seule)
        # chunks de la carte fabriquée à la main : aucune navette n'y est générée (elle a les siennes)
        self._carte_fabriquee = set().union(*(chunks.keys() for chunks in self.layers.values()))

        # surfaces déjà construites, indexées par (nom_calque, chunk_x, chunk_y)
        self._surfaces = {}

        # cases dessinées à part, avec un décalage en pixels (des bases poussées qui glissent : voir
        # animer). Plusieurs bases peuvent glisser en même temps, chacune avec son propre décalage.
        self.groupes = []            # [(cases, (dx, dy))], une entrée par base qui glisse
        self.masque = frozenset()    # toutes les cases de ces groupes réunies
        self._surfaces_masque = {}   # cases -> (surface, case du coin), voir _rendre_masque

        # multijoueur : les tuiles modifiées depuis le dernier envoi, [[calque, tx, ty, gid], ...]
        self.changements = []
        self._note_les_changements = True  # mis à False pendant qu'on applique ceux des autres

        # nombre de tuiles de chaque gid par calque : {nom_calque: Counter({gid: n})},
        # tenu à jour par set_gid (sert à compter les panneaux solaires...)
        self._counts = {}
        for name, chunks in self.layers.items():
            self._counts[name] = Counter(
                gid for grid in chunks.values() for row in grid for gid in row if gid
            )

    # ---- chargement ----
    def _parse_layer(self, layer_node, decalage=0):
        """`decalage` : ajouté à chaque gid (pas aux cases vides), voir les tilesets d'une planète."""
        chunks = {}
        data_node = layer_node.find("data")

        for chunk_node in data_node.findall("chunk"):
            cx = int(chunk_node.get("x"))
            cy = int(chunk_node.get("y"))
            self.chunk_size = int(chunk_node.get("width"))

            grid = []
            for row in chunk_node.text.strip().splitlines():
                row = row.strip().strip(",")
                if row:
                    gids = (int(v) & GID_FLIP_MASK for v in row.split(","))
                    grid.append([gid + decalage if gid else 0 for gid in gids])

            chunks[(cx // self.chunk_size, cy // self.chunk_size)] = grid

        return chunks

    def _get_tile_image(self, gid):
        if gid == 0:
            return None
        for tileset in self.tilesets:
            if gid >= tileset.firstgid:
                return tileset.get_tile(gid)
        return None

    def gids_tileset(self, nom):
        """gids des tuiles du tileset `nom` (nom du fichier .tsx) ; vide s'il n'est pas dans la carte."""
        for tileset in self.tilesets:
            if tileset.nom == nom:
                return range(tileset.firstgid, tileset.firstgid + tileset.tilecount)
        return range(0)

    def colonnes_tileset(self, nom):
        """Nombre de colonnes du tileset `nom` (nom du fichier .tsx) ; 1 s'il n'est pas dans la carte."""
        return next((t.columns for t in self.tilesets if t.nom == nom), 1)

    def tile_image(self, gid):
        """Image de la tuile gid (None pour 0 ou un gid inconnu)."""
        return self._get_tile_image(gid)

    def definir_graine(self, graine):
        """Monde procédural : les chunks absents de la carte Tiled sont tirés de la graine
        (None : rien à générer, le vide comme avant)."""
        self.graine = graine
        self._generes.clear()
        self._navettes.clear()
        self._surfaces.clear()

    def grille(self, layer_name, chunk_coord):
        """Grille de gids du chunk : celle de la carte, sinon celle générée à partir de la graine (le
        terrain sur le calque base, des navettes échouées sur celui des épaves ; vide hors graine).
        Ne pas la modifier : passer par set_gid."""
        grid = self.layers[layer_name].get(chunk_coord)
        if layer_name == self.calque_sol:
            return self._sol(chunk_coord, grid)
        if grid is not None:
            return grid
        if self.graine is None:
            return self._vide
        if layer_name == CALQUE_BASE:
            if chunk_coord not in self._generes:
                tire = morceau(self.graine, chunk_coord, self.morceaux_terrain())
                self._generes[chunk_coord] = self._vide if tire is None else tire
            return self._generes[chunk_coord]
        if layer_name == CALQUE_EPAVES and chunk_coord not in self._carte_fabriquee:
            if chunk_coord not in self._navettes:
                self._navettes[chunk_coord] = self._generer_navette(chunk_coord) or self._vide
            return self._navettes[chunk_coord]
        return self._vide

    def morceaux_terrain(self):
        """Les morceaux de la carte dessinée dont le monde généré est fait : ceux qui portent au moins
        une tuile qui SE VOIT vraiment.

        Sans ce tri, le monde généré était vide à l'écran : sur les 2013 chunks du calque de base de
        map_1.tmx, un seul contient une tuile visible — tout le reste n'est que du vide et des tuiles
        transparentes du tileset. Les chunks tirés étaient donc bien posés, mais ne dessinaient rien
        (_render_chunk les jetait, voir son test sur le masque). On pioche aussi dans le calque des
        épaves, où sont les astéroïdes et les vaisseaux cassés : c'est là qu'est le décor de l'espace.
        Les morceaux qui portent un repère de planète sont écartés : la graine sèmerait sinon des
        copies du Soleil dans tout le monde."""
        if self._morceaux_terrain is None:
            candidats = morceaux_de_terrain(self.tmx_path, (CALQUE_BASE, CALQUE_EPAVES))
            self._morceaux_terrain = [
                m for m in candidats
                if any(self.tuile_visible(gid) for ligne in m for gid in ligne)
                and not any(gid in self._gids_planetes for ligne in m for gid in ligne)]
        return self._morceaux_terrain

    def _sol(self, chunk_coord, grid):
        """Grille du chunk sur le calque du sol : celle de la carte (ou vide), où chaque case vide reçoit une
        tuile tirée au hasard parmi celles de son biome. Le tirage dépend seulement de la carte et du chunk :
        une case a toujours la même tuile, même quand son chunk est déchargé puis redessiné. Hors de la carte
        dessinée, les décors du biome (DECORS_BIOMES : arbres...) sont tirés en même temps (voir decors), et
        partout où le sol est tiré, les cristaux lumineux et les gisements de minerai (CRISTAUX_BIOMES et
        MINERAIS_BIOMES, voir cristaux)."""
        if chunk_coord not in self._sols:
            nom = os.path.basename(self.tmx_path)
            hasard = random.Random(f"{nom}:{chunk_coord[0]}:{chunk_coord[1]}")
            hasard_decors = random.Random(f"decor:{nom}:{chunk_coord[0]}:{chunk_coord[1]}")
            hasard_cristaux = random.Random(f"cristal:{nom}:{chunk_coord[0]}:{chunk_coord[1]}")
            hasard_fluides = random.Random(f"fluide:{nom}:{chunk_coord[0]}:{chunk_coord[1]}")
            x0, y0 = chunk_coord[0] * self.chunk_size, chunk_coord[1] * self.chunk_size
            remplie, biomes, decors, cristaux, fluides = [], [], [], [], []
            pousses = self._decors_biomes if grid is None else {}  # (rien ne pousse dans la carte dessinée)

            def libre(x, y, objets, ecart):
                return all(max(abs(tx - x), abs(ty - y)) >= ecart for tx, ty, _ in objets)

            for ly, ligne in enumerate(grid or self._vide):
                remplie.append([])
                biomes.append([])
                for lx, gid in enumerate(ligne):
                    biome = self._biome_de_gid.get(gid)
                    if not gid or gid in self._remplacables:
                        x, y = x0 + lx, y0 + ly
                        biome = biome_de(nom, x, y, len(self._biomes), BIOME_TAILLE)
                        gids, poids = self._biomes[biome]
                        gid = hasard.choices(gids, poids)[0]
                        arbre = False
                        for image, chance in pousses.get(biome, ()):
                            if hasard_decors.random() < chance and libre(x, y, decors, ECART_DECORS):
                                decors.append((x, y, image))
                                arbre = True
                                break
                        cristal_pose = False
                        for couleur, chance in () if arbre else self._cristaux_biomes.get(biome, ()):
                            if (hasard_cristaux.random() < chance and libre(x, y, cristaux, ECART_CRISTAUX)
                                    and libre(x, y, decors, ECART_CRISTAUX)):
                                cristaux.append((x, y, couleur))
                                cristal_pose = True
                                break
                        for type_fluide, chance in () if (arbre or cristal_pose) else self._fluides_biomes.get(biome, ()):
                            if (hasard_fluides.random() < chance
                                    and libre(x, y, fluides, ECART_FLUIDES)
                                    and libre(x, y, cristaux, ECART_FLUIDES)
                                    and libre(x, y, decors, ECART_FLUIDES)):
                                rayon = hasard_fluides.randint(*FLUIDE_RAYON)
                                fluides.append((x, y, (type_fluide, rayon)))
                                break
                    remplie[-1].append(gid)
                    biomes[-1].append(biome)
            self._sols[chunk_coord] = remplie
            self._cases_biomes[chunk_coord] = biomes
            self._decors[chunk_coord] = decors
            self._cristaux[chunk_coord] = cristaux
            self._fluides[chunk_coord] = [(tx, ty, tf, r) for tx, ty, (tf, r) in fluides]
        return self._sols[chunk_coord]

    def decors(self, chunk_coord):
        """[(tx, ty, image), ...] : les décors (arbres...) du chunk, posés en bas au milieu de leur case."""
        if self.calque_sol is None or not self._decors_biomes:
            return ()
        self.grille(self.calque_sol, chunk_coord)  # (les décors sont tirés avec le sol)
        return self._decors[chunk_coord]

    def cristaux(self, chunk_coord):
        """[(tx, ty, couleur), ...] : les cristaux lumineux du chunk (même ceux déjà récoltés : voir
        monde/cristaux.py), posés en bas au milieu de leur case."""
        if self.calque_sol is None or not self._cristaux_biomes:
            return ()
        self.grille(self.calque_sol, chunk_coord)  # (les cristaux sont tirés avec le sol)
        return self._cristaux[chunk_coord]

    def fluides(self, chunk_coord):
        """[(tx, ty, type_fluide, rayon), ...] : les mares du chunk (eau, acide, pétrole, lave),
        voir monde/fluides.py. Rayon en cases : la mare s'étend sur 2*rayon × rayon cases."""
        if self.calque_sol is None or not self._fluides_biomes:
            return ()
        self.grille(self.calque_sol, chunk_coord)  # (les fluides sont tirés avec le sol)
        return self._fluides[chunk_coord]

    @property
    def nom(self):
        """Nom du fichier de la carte (ex : "velmaris.tmx")."""
        return os.path.basename(self.tmx_path)

    # ---- transitions entre biomes ----
    def _biome_case(self, tx, ty):
        cx, lx = divmod(tx, self.chunk_size)
        cy, ly = divmod(ty, self.chunk_size)
        self.grille(self.calque_sol, (cx, cy))
        return self._cases_biomes[(cx, cy)][ly][lx]

    def _tuile_transition(self, biome, direction, variante, creux=False):
        """Le sol principal du biome, découpé par le masque du bord (voir _masque_transition)."""
        cle = (biome, direction, variante, creux)
        if cle not in self._transitions:
            tuile = self._get_tile_image(self._biomes[biome][0][0]).copy()
            tuile.blit(_masque_transition(direction, variante, tuile.get_width(), creux), (0, 0),
                       special_flags=pygame.BLEND_RGBA_MULT)
            self._transitions[cle] = tuile
        return self._transitions[cle]

    def _dessiner_transitions(self, surface, chunk_coord):
        """Sur le chunk du sol déjà dessiné : là où deux biomes se touchent, le sol de celui qui est le plus loin
        dans la liste (SOLS_ALEATOIRES) déborde en douceur sur l'autre, avec un bord qui ondule."""
        taille, tw, th = self.chunk_size, self.tilewidth, self.tileheight
        x0, y0 = chunk_coord[0] * taille, chunk_coord[1] * taille
        biomes = self._cases_biomes[chunk_coord]

        def biome(lx, ly):
            if 0 <= lx < taille and 0 <= ly < taille:
                return biomes[ly][lx]
            return self._biome_case(x0 + lx, y0 + ly)  # (dans le chunk voisin)

        for ly in range(taille):
            for lx in range(taille):
                ici = biomes[ly][lx]
                if ici is None:
                    continue
                autour = {d: biome(lx + d[0], ly + d[1]) for d in VOISINS}
                for b in sorted({v for v in autour.values() if v is not None and v > ici}):
                    for (dx, dy), v in autour.items():
                        creux = False
                        if dx and dy:
                            cotes = (autour[(dx, 0)] == b) + (autour[(0, dy)] == b)
                            if cotes == 1:
                                continue  # (un coin dont un seul côté déborde : déjà couvert par ce côté)
                            creux = cotes == 2  # (deux côtés : leur angle est arrondi, même sans le coin)
                        if v != b and not creux:
                            continue
                        variante = (x0 + lx) * 7 + (y0 + ly) * 13 + dx * 3 + dy * 5
                        surface.blit(self._tuile_transition(b, (dx, dy), variante % TRANSITION_VARIANTES, creux),
                                     (lx * tw, ly * th))

    def bloque(self, rect):
        """True si le héros ne peut pas aller là : une tuile solide (voir collides) ou le tronc d'un arbre."""
        if self.collides(rect) or rect.collidelist(self.obstacles) != -1:
            return True
        if not self._decors_biomes:
            return False
        taille = self.chunk_size * self.tilewidth
        for cy in range(rect.top // taille, (rect.bottom - 1) // taille + 1):
            for cx in range(rect.left // taille, (rect.right - 1) // taille + 1):
                for tx, ty, _ in self.decors((cx, cy)):
                    tronc = pygame.Rect(0, 0, TRONC_LARGEUR, TRONC_HAUTEUR)
                    tronc.midbottom = ((tx + 0.5) * self.tilewidth, (ty + 1) * self.tileheight)
                    if tronc.colliderect(rect):
                        return True
        return False

    def _generer_navette(self, chunk_coord):
        """Calque des épaves du chunk tiré de la graine : une navette échouée, ou None. Elle n'est
        jamais posée sur du terrain visible du calque base."""
        tileset = next((t for t in self.tilesets if t.nom == TILESET_EPAVES), None)
        if tileset is None:
            return None
        base = self.grille(CALQUE_BASE, chunk_coord)
        return navette(self.graine, chunk_coord, lambda x, y: not self.tuile_visible(base[y][x]),
                       tileset.firstgid, tileset.columns, MONDE_CHANCE_NAVETTE, self.chunk_size)

    def tuile_visible(self, gid):
        """True si la tuile gid se voit (le vide de l'espace et les tuiles vides du tileset, non)."""
        if gid not in self._visibles:
            tuile = self._get_tile_image(gid)
            self._visibles[gid] = tuile is not None and pygame.mask.from_surface(tuile, 1).count() > 0
        return self._visibles[gid]

    def _render_chunk(self, layer_name, chunk_coord):
        grid = self.grille(layer_name, chunk_coord)
        if not any(gid for row in grid for gid in row):
            return None  # chunk vide : rien à dessiner (et pas de surface de 2048x2048 en mémoire)

        size_px_w = self.chunk_size * self.tilewidth
        size_px_h = self.chunk_size * self.tileheight
        # chunk entièrement couvert de tuiles opaques (le sol d'une planète) : surface sans transparence,
        # bien plus rapide à dessiner, et rien à vérifier ensuite
        opaque = not self.masque and all(gid not in self._gids_planetes and self._tuile_opaque(gid)
                                         for row in grid for gid in row)
        if opaque:
            surface = pygame.Surface((size_px_w, size_px_h)).convert()
        else:
            surface = pygame.Surface((size_px_w, size_px_h), pygame.SRCALPHA)
        for ty, row in enumerate(grid):
            for tx, gid in enumerate(row):
                if self.masque and (chunk_coord[0] * self.chunk_size + tx,
                                    chunk_coord[1] * self.chunk_size + ty) in self.masque:
                    continue  # dessinée à part, avec son décalage (voir draw)
                if gid in self._gids_planetes:
                    continue  # une planète : sa grande image est dessinée à part (voir monde/planetes.py)
                tile = self._get_tile_image(gid)
                if tile is not None:
                    surface.blit(tile, (tx * self.tilewidth, ty * self.tileheight))
        if layer_name == self.calque_sol and not self.masque:
            self._dessiner_transitions(surface, chunk_coord)  # (sol d'une planète : les biomes se fondent)

        # tuiles toutes transparentes (espace vide) : inutile de blitter 2048x2048 pixels
        # invisibles à chaque image (très coûteux quand on dézoome)
        if not opaque and pygame.mask.from_surface(surface, 1).count() == 0:
            return None
        return surface

    def _tuile_opaque(self, gid):
        """True si la tuile gid n'a aucun pixel transparent."""
        if gid not in self._opaques:
            tuile = self._get_tile_image(gid)
            self._opaques[gid] = (tuile is not None and tuile.get_size() == (self.tilewidth, self.tileheight)
                                  and pygame.mask.from_surface(tuile, 254).count() == self.tilewidth * self.tileheight)
        return self._opaques[gid]

    def _get_chunk_surface(self, layer_name, chunk_coord):
        key = (layer_name, chunk_coord)
        if key not in self._surfaces:
            self._surfaces[key] = self._render_chunk(layer_name, chunk_coord)
        return self._surfaces[key]

    # ---- collisions ----
    def get_gid(self, tx, ty):
        """gid de la tuile (tx, ty) (coordonnées en tuiles) sur tous les calques :
        renvoie le premier gid solide trouvé, sinon 0."""
        cx, local_x = divmod(tx, self.chunk_size)
        cy, local_y = divmod(ty, self.chunk_size)
        for layer_name in self.layers:
            gid = self.grille(layer_name, (cx, cy))[local_y][local_x]
            if gid in self._gids_solides:
                return gid
        return 0

    def get_layer_gid(self, layer_name, tx, ty):
        """gid de la tuile (tx, ty) sur un calque précis (0 si vide)."""
        grid = self.grille(layer_name, (tx // self.chunk_size, ty // self.chunk_size))
        return grid[ty % self.chunk_size][tx % self.chunk_size]

    def count_gid(self, layer_name, gid):
        """Nombre de tuiles gid présentes sur un calque."""
        return self._counts[layer_name][gid]

    # ---- modification ----
    def set_gid(self, tx, ty, gid, layer_name=None):
        """Pose la tuile gid en (tx, ty) (coordonnées en tuiles) sur un calque
        (le premier par défaut), en créant le chunk s'il n'existe pas encore."""
        if layer_name is None:
            layer_name = next(iter(self.layers))
        if self._note_les_changements:
            # en multijoueur, c'est par ici que passe TOUT ce qui modifie la carte (construction,
            # déconstruction, destruction par un vaisseau ennemi, base poussée par ses réacteurs) :
            # on note le changement, le réseau l'enverra aux autres joueurs (voir reseau/).
            self.changements.append([layer_name, tx, ty, gid])
        layer_chunks = self.layers[layer_name]

        coord = (tx // self.chunk_size, ty // self.chunk_size)
        grid = layer_chunks.get(coord)
        if grid is None:
            # chunk de la carte ou généré : on en fait une copie modifiable, qui sera sauvegardée
            grid = layer_chunks[coord] = [list(ligne) for ligne in self.grille(layer_name, coord)]
            self._counts[layer_name].update(gid for ligne in grid for gid in ligne if gid)
        row = grid[ty % self.chunk_size]
        ancien = row[tx % self.chunk_size]
        row[tx % self.chunk_size] = gid

        counts = self._counts[layer_name]
        if ancien:
            counts[ancien] -= 1
        if gid:
            counts[gid] += 1

        # le chunk a changé : on force son redessin
        self._surfaces.pop((layer_name, coord), None)
        self._sols.pop(coord, None)
        if (tx, ty) in self.masque:
            self._surfaces_masque.clear()  # une base qui glisse a changé : on la redessine

    # ---- multijoueur ----
    def prendre_changements(self):
        """Les tuiles modifiées depuis le dernier appel, et remet le compteur à zéro."""
        if not self.changements:
            return []
        changements, self.changements = self.changements, []
        return changements

    def appliquer_changements(self, changements):
        """Pose les tuiles modifiées par quelqu'un d'autre, SANS les renoter : sinon on les
        renverrait à celui qui vient de nous les envoyer, et ainsi de suite sans fin."""
        self._note_les_changements = False
        try:
            for calque, tx, ty, gid in changements:
                if calque in self.layers:
                    self.set_gid(tx, ty, gid, calque)
        finally:
            self._note_les_changements = True

    def animer(self, groupes):
        """Dessine à part des groupes de cases, chacun décalé de ses propres pixels :
        `groupes` = [(cases, (dx, dy)), ...] (liste vide : plus rien à part). Ne redessine les
        chunks que quand l'ensemble des cases mises à part change."""
        groupes = [(frozenset(cases), (d[0], d[1])) for cases, d in groupes if cases]
        union = frozenset().union(*(cases for cases, _ in groupes)) if groupes else frozenset()
        if union != self.masque:
            for x, y in union | self.masque:
                coord = (x // self.chunk_size, y // self.chunk_size)
                for nom in self.layers:
                    self._surfaces.pop((nom, coord), None)
            self.masque = union
            self._surfaces_masque = {cases: surface for cases, surface in self._surfaces_masque.items()
                                     if any(cases == c for c, _ in groupes)}
        self.groupes = groupes

    def image_masque(self, cases=None):
        """(surface, case du coin) : toutes les couches de ces cases (par défaut, toutes celles
        mises à part par animer() réunies)."""
        cases = self.masque if cases is None else frozenset(cases)
        if cases not in self._surfaces_masque:
            self._surfaces_masque[cases] = self._rendre_masque(cases)
        return self._surfaces_masque[cases]

    def _rendre_masque(self, cases):
        """Toutes les couches des cases qui glissent, dessinées une fois dans une seule surface
        (au lieu de les blitter tuile par tuile à chaque image). Renvoie (surface, case du coin)."""
        x0 = min(x for x, _ in cases)
        y0 = min(y for _, y in cases)
        largeur = (max(x for x, _ in cases) - x0 + 1) * self.tilewidth
        hauteur = (max(y for _, y in cases) - y0 + 1) * self.tileheight
        surface = pygame.Surface((largeur, hauteur), pygame.SRCALPHA)
        for layer_name in self.layers:
            for x, y in cases:
                tile = self._get_tile_image(self.get_layer_gid(layer_name, x, y))
                if tile is not None:
                    surface.blit(tile, ((x - x0) * self.tilewidth, (y - y0) * self.tileheight))
        return surface, (x0, y0)

    def collides(self, rect):
        """True si le rect (en pixels monde) touche une tuile solide (le vide, gid 6)."""
        first_tx = rect.left // self.tilewidth
        last_tx = (rect.right - 1) // self.tilewidth
        first_ty = rect.top // self.tileheight
        last_ty = (rect.bottom - 1) // self.tileheight

        for ty in range(first_ty, last_ty + 1):
            for tx in range(first_tx, last_tx + 1):
                if self.get_gid(tx, ty):
                    return True
        return False

    # ---- sauvegarde ----
    def exporter(self):
        """Les calques que le jeu modifie, sous forme sérialisable : {calque: [[cx, cy, grille], ...]}."""
        return {nom: [[cx, cy, grille] for (cx, cy), grille in chunks.items()]
                for nom, chunks in self.layers.items() if nom in CALQUES_SAUVES}

    def importer(self, donnees):
        """Remplace les calques que le jeu modifie par ceux d'une sauvegarde (voir exporter). Les autres
        (décor dessiné dans Tiled : planètes, navettes...) restent ceux de la carte, pour qu'un changement
        fait dans Tiled se voie aussi dans les mondes déjà sauvegardés."""
        for nom, chunks in donnees.items():
            if nom in self.layers and nom in CALQUES_SAUVES:
                self.layers[nom] = {(cx, cy): grille for cx, cy, grille in chunks}
        self._surfaces.clear()
        for nom, chunks in self.layers.items():
            self._counts[nom] = Counter(
                gid for grid in chunks.values() for row in grid for gid in row if gid
            )

    # ---- streaming ----
    def update(self, camera):
        """Décharge les chunks trop loin de la caméra pour ne pas saturer la mémoire.
        On garde tous les chunks visibles (même très dézoomé) plus une marge de
        `cache_radius` : sinon ils seraient déchargés puis redessinés à chaque image."""
        size_px_w = self.chunk_size * self.tilewidth
        size_px_h = self.chunk_size * self.tileheight
        cam_x, cam_y = int(camera.x), int(camera.y)
        marge = self.cache_radius - 1  # draw() affiche déjà 1 chunk autour de la vue
        min_cx = cam_x // size_px_w - 1 - marge
        max_cx = (cam_x + camera.screen_width) // size_px_w + 1 + marge
        min_cy = cam_y // size_px_h - 1 - marge
        max_cy = (cam_y + camera.screen_height) // size_px_h + 1 + marge

        for key in list(self._surfaces):
            _, (cx, cy) = key
            if not (min_cx <= cx <= max_cx and min_cy <= cy <= max_cy):
                del self._surfaces[key]

    # ---- affichage ----
    def draw(self, screen, camera):
        size_px_w = self.chunk_size * self.tilewidth
        size_px_h = self.chunk_size * self.tileheight
        cam_x, cam_y = int(camera.x), int(camera.y)

        first_cx = cam_x // size_px_w - 1
        last_cx = (cam_x + camera.screen_width) // size_px_w + 1
        first_cy = cam_y // size_px_h - 1
        last_cy = (cam_y + camera.screen_height) // size_px_h + 1

        for layer_name in self.layers:
            for cy in range(first_cy, last_cy + 1):
                for cx in range(first_cx, last_cx + 1):
                    chunk_surface = self._get_chunk_surface(layer_name, (cx, cy))
                    if chunk_surface is None:
                        continue  # chunk vide
                    screen.blit(chunk_surface, (cx * size_px_w - cam_x, cy * size_px_h - cam_y))

        # les bases qui glissent (voir animer), par-dessus, chacune à son décalage
        for cases, decalage in self.groupes:
            surface, (x0, y0) = self.image_masque(cases)
            screen.blit(surface, (x0 * self.tilewidth - cam_x + round(decalage[0]),
                                  y0 * self.tileheight - cam_y + round(decalage[1])))


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lanceur import lancer

    lancer()
