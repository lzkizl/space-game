import sys
from pathlib import Path
from types import SimpleNamespace

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import boitier, epave, telescope
from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, VIDE_GID, VIDE_GIDS

# =============================================
# ==== Propulsion : un réacteur alimenté en oxygène ET en hydrogène pousse toute la base à
# ==== laquelle il est accroché, d'une tuile à la fois. Il faut qu'un boîtier de cette base ait un
# ==== processeur, une RAM et une clé USB réacteurs : c'est lui qui les met en marche et choisit
# ==== la direction (haut, bas,
# ==== gauche, droite) ; sans boîtier piloté (ou à l'arrêt), les réacteurs ne poussent pas.
# ==== "La base" = tout ce qui se touche (même en diagonale) à partir du réacteur : tuiles de
# ==== base, constructions posées dessus ou accrochées dessous. Les robots, tourelles, plantes,
# ==== coffres et le héros (s'il est sur la base) suivent. Une épave en travers du chemin bloque
# ==== la poussée (rien n'est consommé). (Une autre base qui touche la structure en fait partie.)
# ==== Un télescope (posé dans le vide) ne fait jamais partie de la base, même s'il la touche : il
# ==== reste où il est, et bloque la base comme une épave s'il est sur son chemin.
# =============================================
MAX_CASES = 5000      # au-delà, la structure est trop grosse pour être poussée
GID_BOITIER = boitier.TUILES[0][2]
GIDS_TELESCOPE = {gid for _, _, gid in telescope.TUILES}


def _telescope(game_map, x, y):
    """True si la case porte un morceau de télescope."""
    return game_map.get_layer_gid(telescope.CALQUE, x, y) in GIDS_TELESCOPE


def _membre(game_map, x, y):
    """True si la case porte de la base ou une construction (sauf un télescope)."""
    if game_map.get_layer_gid(CALQUE_BASE, x, y) not in VIDE_GIDS:
        return True
    return game_map.get_layer_gid(CALQUE_PLANTES, x, y) != 0 and not _telescope(game_map, x, y)


def structure_liee(game_map, depart):
    """Ensemble des cases (tx, ty) de la structure qui contient `depart` (None si trop grosse)."""
    vus = {depart}
    pile = [depart]
    while pile:
        x, y = pile.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                voisin = (x + dx, y + dy)
                if voisin not in vus and _membre(game_map, *voisin):
                    vus.add(voisin)
                    pile.append(voisin)
                    if len(vus) > MAX_CASES:
                        return None
    return vus


def structure_sous(game_map, case):
    """Cases de la structure (base et ce qui est dessus) qui contient `case`, ou None si la case est
    vide (ou la structure trop grosse)."""
    return structure_liee(game_map, case) if _membre(game_map, *case) else None


def bloquee(game_map, cases, dx, dy):
    """True si la structure ne peut pas avancer de (dx, dy) : une autre base, une épave ou un
    télescope est en travers."""
    for x, y in cases:
        arrivee = (x + dx, y + dy)
        if arrivee not in cases and (_membre(game_map, *arrivee) or _telescope(game_map, *arrivee)
                                     or game_map.get_layer_gid(epave.CALQUE, *arrivee) != 0):
            return True
    return False


def boitier_pilote(game_map, coffres, cases):
    """Le boîtier de la structure qui peut piloter les réacteurs (processeur, RAM et clé USB
    réacteurs dedans), ou None s'il n'y en a pas."""
    for case in cases:
        if game_map.get_layer_gid(boitier.CALQUE, *case) == GID_BOITIER:
            contenu = coffres.coffres.get(case)
            if contenu is not None and boitier.pilote_reacteurs(contenu):
                return contenu
    return None


def deplacer(game_map, cases, dx, dy):
    """Décale les tuiles de la structure. Renvoie {ancienne case: nouvelle case}."""
    base = {c: g for c in cases if (g := game_map.get_layer_gid(CALQUE_BASE, *c)) not in VIDE_GIDS}
    dessus = {c: g for c in cases if (g := game_map.get_layer_gid(CALQUE_PLANTES, *c))}
    for x, y in base:
        game_map.set_gid(x, y, VIDE_GID, CALQUE_BASE)
    for x, y in dessus:
        game_map.set_gid(x, y, 0, CALQUE_PLANTES)
    for (x, y), gid in base.items():
        game_map.set_gid(x + dx, y + dy, gid, CALQUE_BASE)
    for (x, y), gid in dessus.items():
        game_map.set_gid(x + dx, y + dy, gid, CALQUE_PLANTES)
    return {(x, y): (x + dx, y + dy) for x, y in cases}


class Glissement:
    """Une base qui vient de sauter d'une tuile et qu'on redessine en train de rejoindre sa place.

    `cases` : où elle est maintenant. `decalage` : de combien de pixels on la dessine en arrière
    (il fond vers zéro). `passagers` : les joueurs qui étaient dessus et qui glissent avec elle.
    """

    def __init__(self, cases):
        self.cases = frozenset(cases)
        self.decalage = [0.0, 0.0]
        self.passagers = set()
        self.moteurs = 0      # réacteurs qui la poussent en ce moment (plus il y en a, plus ça glisse vite)
        self.delai = 1.0      # secondes entre deux tuiles pour ces réacteurs

    def offset(self, camera_offset):
        """Décalage de caméra à utiliser pour dessiner ce qui est porté par cette base."""
        return camera_offset[0] - self.decalage[0], camera_offset[1] - self.decalage[1]


class Propulsion:
    """Les réacteurs poussent leur base. Côté jeu, la base saute d'une tuile d'un coup (collisions,
    constructions...) ; côté dessin, un Glissement la ramène depuis son ancienne place : la carte
    (voir Map.animer) et ce qui est dessus sont dessinés avec son décalage.

    Plusieurs bases peuvent être poussées en même temps, chacune avec ses propres passagers : en
    multijoueur, deux joueurs peuvent voyager sur deux plateformes différentes.
    """

    def __init__(self):
        self.glissements = []  # une entrée par base en train de glisser

    def _glissement_sur(self, case):
        """Le glissement de la base qui porte cette case, ou None."""
        return next((g for g in self.glissements if case in g.cases), None)

    def _glissement_de(self, joueur):
        """Le glissement de la base qui porte ce joueur, ou None."""
        return next((g for g in self.glissements if joueur in g.passagers), None)

    def offset_de(self, camera_offset, case):
        """Décalage de caméra à utiliser pour dessiner ce qui est sur `case`."""
        glissement = self._glissement_sur(case)
        return camera_offset if glissement is None else glissement.offset(camera_offset)

    def offset_hero(self, camera_offset, joueur):
        """Décalage de caméra pour dessiner ce joueur (il glisse avec la base qui le porte)."""
        glissement = self._glissement_de(joueur)
        return camera_offset if glissement is None else glissement.offset(camera_offset)

    def cible_camera(self, joueur):
        """Ce que la caméra suit : le héros tel qu'on le voit (il glisse avec sa base)."""
        glissement = self._glissement_de(joueur)
        if glissement is None:
            return joueur.hero
        return SimpleNamespace(x=joueur.hero.x + glissement.decalage[0],
                               y=joueur.hero.y + glissement.decalage[1])

    def update(self, dt, game_map, coffres, robots, plantes, tourelles, joueurs):
        """Chaque réacteur qui a de quoi brûler et dont la base est pilotée (boîtier avec clé USB
        réacteurs, en marche) pousse sa base d'une tuile toutes les DELAI_PAS secondes, dans la
        direction choisie sur le boîtier. Les joueurs posés dessus voyagent avec elle."""
        for glissement in self.glissements:
            glissement.moteurs = 0
        for coffre in list(coffres.coffres.values()):
            c = coffre.construction
            if not hasattr(c, "COUT_PAS"):
                continue  # pas un réacteur (surtout ne pas toucher à `progres` : le four s'en sert)
            if not coffre.peut_payer(c.COUT_PAS):
                coffre.progres = 0.0
                coffre.pousse = False
                continue
            if coffre.pousse:
                glissement = self._glissement_sur((coffre.tx, coffre.ty))
                if glissement is not None:
                    glissement.moteurs += 1
                    glissement.delai = c.DELAI_PAS
            coffre.progres += dt
            if coffre.progres < c.DELAI_PAS:
                continue
            coffre.progres = 0.0
            # (la structure et son pilote ne sont cherchés qu'à chaque pas, pas à chaque image)
            cases = structure_liee(game_map, (coffre.tx, coffre.ty))
            pilote = boitier_pilote(game_map, coffres, cases) if cases is not None else None
            coffre.pousse = pilote is not None and pilote.marche
            if not coffre.pousse:
                continue
            dx, dy = pilote.direction
            if bloquee(game_map, cases, dx, dy) or not coffre.payer(c.COUT_PAS):
                continue
            # les joueurs sur la base montent avec elle (sinon ils se retrouveraient dans le vide solide)
            portes = []
            for joueur in joueurs:
                boite = joueur.hero.hitbox(joueur.hero.x, joueur.hero.y)
                if (boite.centerx // game_map.tilewidth, boite.centery // game_map.tileheight) in cases:
                    portes.append(joueur)
            trajet = deplacer(game_map, cases, dx, dy)
            for joueur in portes:
                joueur.hero.x += dx * game_map.tilewidth
                joueur.hero.y += dy * game_map.tileheight
            pixels = (dx * game_map.tilewidth, dy * game_map.tileheight)
            coffres.deplacer(trajet)
            robots.deplacer(trajet, pixels)
            plantes.deplacer(trajet)
            tourelles.deplacer(trajet, pixels)
            # la base est déjà à sa nouvelle place : on la dessine encore à l'ancienne, puis elle glisse
            anciennes = frozenset(trajet)
            glissement = next((g for g in self.glissements if g.cases == anciennes), None)
            if glissement is None:
                glissement = Glissement(trajet.values())
                glissement.delai = c.DELAI_PAS
                glissement.moteurs = 1
                self.glissements.append(glissement)
            else:
                glissement.cases = frozenset(trajet.values())
            glissement.passagers = set(portes)
            glissement.decalage[0] -= dx * game_map.tilewidth
            glissement.decalage[1] -= dy * game_map.tileheight

        # chaque décalage fond vers 0 à la vitesse de la poussée (plus de réacteurs : plus vite)
        for glissement in self.glissements:
            for axe, taille in ((0, game_map.tilewidth), (1, game_map.tileheight)):
                pas = taille / glissement.delai * max(1, glissement.moteurs) * dt
                reste = glissement.decalage[axe]
                glissement.decalage[axe] = max(0.0, reste - pas) if reste > 0 else min(0.0, reste + pas)
        # (tant qu'un réacteur pousse encore, on garde la base : sinon elle serait redessinée à chaque pas)
        self.glissements = [g for g in self.glissements if g.moteurs or any(g.decalage)]
        game_map.animer([(g.cases, g.decalage) for g in self.glissements])


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
