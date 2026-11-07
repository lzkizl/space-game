import math

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import (antenne, base, base_robot, boitier, canon_electromagnetique, coffre, deconstruction, foreuse,
                          four, oxygenateur,
                          panneau, plante, reacteur, reacteur_nucleaire, table_craft, table_recherche, telescope,
                          tourelle, tourelle_plasma, vaisseau_joueur, vaisseau_teleporteur)
from systeme.ressources import CLE_USB
from systeme.settings import (CALQUE_BASE, COULEUR_DECONSTRUCTION, COULEUR_DECONSTRUCTION_BORDURE,
                      COULEUR_ZONE, COULEUR_ZONE_BORDURE, COULEUR_ZONE_REFUSEE,
                      COULEUR_ZONE_REFUSEE_BORDURE, VIDE_GID, VIDE_GIDS)
from monde.planetes import PLANETES_GIDS

# =============================================
# ==== Toutes les constructions du jeu (modules du dossier construction/) :
# ==== ce sont les objets qu'on met dans l'inventaire
# =============================================
CONSTRUCTIONS = [base, plante, panneau, base_robot, table_craft, coffre, reacteur, tourelle, antenne, boitier, four, oxygenateur,
                 reacteur_nucleaire, telescope, table_recherche, canon_electromagnetique, tourelle_plasma]

# Engins : des objets d'inventaire qui se posent dans le monde sans tuile (pas dans CONSTRUCTIONS)
ENGINS = [vaisseau_joueur, vaisseau_teleporteur, foreuse]

# Outils (n'ont pas de tuiles à poser) : mis dans l'inventaire avec les constructions
OUTILS = [deconstruction]


def nombre_pose(game_map, objet):
    """Nombre d'exemplaires de la construction déjà posés sur la carte."""
    return game_map.count_gid(objet.CALQUE, objet.TUILES[0][2])


def mode_pose(inventaire):
    """True si on peut poser quelque chose : l'inventaire (Tab) est fermé et la case
    sélectionnée contient une construction ou un outil (pas une ressource)."""
    objet = inventaire.objet_selectionne
    return (not inventaire.ouvert and objet is not None
            and (hasattr(objet, "TUILES") or est_outil(objet)))


def taille_bloc(bloc):
    """(largeur, hauteur) du bloc, en tuiles."""
    return max(dx for dx, _, _ in bloc) + 1, max(dy for _, dy, _ in bloc) + 1


def coin_bloc(game_map, camera, pos_souris, bloc):
    """Tuile en haut à gauche du bloc, pour qu'il soit centré sur la souris."""
    largeur, hauteur = taille_bloc(bloc)
    monde_x = pos_souris[0] + camera.x
    monde_y = pos_souris[1] + camera.y
    tx = math.floor(monde_x / game_map.tilewidth - largeur / 2 + 0.5)
    ty = math.floor(monde_y / game_map.tileheight - hauteur / 2 + 0.5)
    return tx, ty


def peut_poser(game_map, camera, pos_souris, objet):
    """False si une des tuiles visées ne convient pas :
    - SUPPORT : la construction exige de la base dessous (ex : une plante) ;
    - SOUS_FONDATION (optionnel) : au contraire, elle ne se pose pas sur la plateforme
      mais dans le vide de l'espace, juste sous le bord bas d'une base (case du dessus
      = base) ;
    - LIBRE (optionnel) : la construction exige du vide sur ce calque (ex : la base
      ne se pose pas sur une autre base) ;
    - les structures posées sur la base ne se posent pas sur une autre structure.
    Sur une planète, le sol sert de base (voir _peut_poser_planete)."""
    tx, ty = coin_bloc(game_map, camera, pos_souris, objet.TUILES)
    cases = [(tx + dx, ty + dy) for dx, dy, _ in objet.TUILES]

    if objet.CALQUE != CALQUE_BASE and any(
            game_map.get_layer_gid(objet.CALQUE, x, y) != 0 for x, y in cases):
        return False

    if game_map.planete:
        return _peut_poser_planete(game_map, objet, cases)

    if getattr(objet, "SOUS_FONDATION", False):
        # pas sur la plateforme : dans le vide, juste sous son bord bas
        for x, y in cases:
            if game_map.get_layer_gid(objet.SUPPORT, x, y) not in VIDE_GIDS:
                return False
            if game_map.get_layer_gid(objet.SUPPORT, x, y - 1) in VIDE_GIDS:
                return False
    elif objet.SUPPORT is not None and any(
            game_map.get_layer_gid(objet.SUPPORT, x, y) in VIDE_GIDS for x, y in cases):
        return False

    libre = getattr(objet, "LIBRE", None)
    if libre is not None and any(
            game_map.get_layer_gid(libre, x, y) not in VIDE_GIDS for x, y in cases):
        return False

    return True


def _peut_poser_planete(game_map, objet, cases):
    """Sur une planète, pas besoin de base : la construction se pose sur le sol (là où la carte en a), mais pas
    sur un arbre, un cristal ou une foreuse. Ce qui ne sert que dans l'espace (réacteur sous le bord d'une base,
    télescope : ESPACE_SEULEMENT) ne s'y pose pas."""
    if getattr(objet, "SOUS_FONDATION", False) or getattr(objet, "ESPACE_SEULEMENT", False):
        return False
    libre = getattr(objet, "LIBRE", None)
    for x, y in cases:
        if not any(game_map.get_layer_gid(nom, x, y) for nom in game_map.calques_sol):
            return False  # (hors du sol de la carte)
        if libre is not None and game_map.get_layer_gid(libre, x, y) not in VIDE_GIDS:
            return False
        case = pygame.Rect(x * game_map.tilewidth, y * game_map.tileheight, game_map.tilewidth, game_map.tileheight)
        if case.collidelist(game_map.obstacles) != -1:
            return False  # une foreuse
        chunk = (x // game_map.chunk_size, y // game_map.chunk_size)
        if any((cx, cy) == (x, y) for cx, cy, _ in (*game_map.decors(chunk), *game_map.cristaux(chunk))):
            return False  # un arbre ou un cristal
    return True


def poser_bloc(game_map, camera, pos_souris, objet):
    """Pose les tuiles de la construction, centrées sur la position de la souris.
    Renvoie la case (tx, ty) en haut à gauche du bloc posé, ou None si c'est refusé."""
    if not peut_poser(game_map, camera, pos_souris, objet):
        return None
    tx, ty = coin_bloc(game_map, camera, pos_souris, objet.TUILES)
    for dx, dy, gid in objet.TUILES:
        game_map.set_gid(tx + dx, ty + dy, gid, objet.CALQUE)
    return tx, ty


def dessiner_zone(screen, game_map, camera, pos_souris, objet):
    """Zone translucide montrant où le bloc sera posé : verte si c'est possible,
    rouge sinon."""
    bloc = objet.TUILES
    largeur, hauteur = taille_bloc(bloc)
    tx, ty = coin_bloc(game_map, camera, pos_souris, bloc)
    if peut_poser(game_map, camera, pos_souris, objet):
        couleur, bordure = COULEUR_ZONE, COULEUR_ZONE_BORDURE
    else:
        couleur, bordure = COULEUR_ZONE_REFUSEE, COULEUR_ZONE_REFUSEE_BORDURE
    _dessiner_rect(screen, game_map, camera, tx, ty, largeur, hauteur, couleur, bordure)


def _dessiner_rect(screen, game_map, camera, tx, ty, largeur, hauteur, couleur, bordure):
    """Rectangle translucide sur les cases (tx, ty) -> (tx + largeur, ty + hauteur)."""
    zone = pygame.Rect(
        tx * game_map.tilewidth - int(camera.x),
        ty * game_map.tileheight - int(camera.y),
        largeur * game_map.tilewidth,
        hauteur * game_map.tileheight,
    )
    surface = pygame.Surface(zone.size, pygame.SRCALPHA)
    surface.fill(couleur)
    screen.blit(surface, zone)
    pygame.draw.rect(screen, bordure, zone, 3)


# =============================================
# ==== Déconstruction : enlever une structure posée
# =============================================
def est_outil(objet):
    """True pour un outil (ex : déconstruction) et non une construction à poser."""
    return getattr(objet, "OUTIL", False)


def case_sous_souris(game_map, camera, pos_souris):
    """Case (tx, ty) sous la souris."""
    return (math.floor((pos_souris[0] + camera.x) / game_map.tilewidth),
            math.floor((pos_souris[1] + camera.y) / game_map.tileheight))


def table_craft_sous_souris(game_map, camera, pos_souris):
    """True si la case sous la souris porte une table de craft."""
    tx, ty = case_sous_souris(game_map, camera, pos_souris)
    return game_map.get_layer_gid(table_craft.CALQUE, tx, ty) == table_craft.TUILES[0][2]


def table_recherche_sous_souris(game_map, camera, pos_souris):
    """True si la case sous la souris porte une table de recherche."""
    tx, ty = case_sous_souris(game_map, camera, pos_souris)
    return game_map.get_layer_gid(table_recherche.CALQUE, tx, ty) == table_recherche.TUILES[0][2]


def antenne_sous_souris(game_map, camera, pos_souris):
    """True si la case sous la souris fait partie d'une antenne posée."""
    structure = trouver_structure(game_map, *case_sous_souris(game_map, camera, pos_souris))
    return structure is not None and structure[0] is antenne


def cle_a_cote(game_map, camera, pos_souris, coffres, cle):
    """True si l'antenne sous la souris a un boîtier collé contre elle (à gauche ou à droite,
    à n'importe quelle hauteur du mât) avec la clé USB `cle` dedans."""
    structure = trouver_structure(game_map, *case_sous_souris(game_map, camera, pos_souris))
    if structure is None or structure[0] is not antenne:
        return False
    ox, oy = structure[1]
    gid = boitier.TUILES[0][2]
    for dx in (-1, 1):
        for dy in range(taille_bloc(antenne.TUILES)[1]):
            if game_map.get_layer_gid(boitier.CALQUE, ox + dx, oy + dy) == gid:
                contenu = coffres.coffres.get((ox + dx, oy + dy))
                if contenu is not None and contenu.objets[boitier.CASE_CLE_USB] is cle:
                    return True
    return False


def decodeur_a_cote(game_map, camera, pos_souris, coffres):
    """Clé USB à côté de l'antenne : la radio traduit les bits en lettres."""
    return cle_a_cote(game_map, camera, pos_souris, coffres, CLE_USB)


def trouver_structure(game_map, tx, ty):
    """(construction, (ox, oy)) de la structure posée sur la case (tx, ty), où
    (ox, oy) est la case en haut à gauche de la structure. None s'il n'y en a pas.
    Les structures posées sur la base (plantes...) sont cherchées avant la base."""
    for objet in sorted(CONSTRUCTIONS, key=lambda o: o.SUPPORT is None):
        for dx, dy, gid in objet.TUILES:
            if game_map.get_layer_gid(objet.CALQUE, tx, ty) != gid:
                continue
            ox, oy = tx - dx, ty - dy
            if all(game_map.get_layer_gid(objet.CALQUE, ox + ddx, oy + ddy) == g
                   for ddx, ddy, g in objet.TUILES):
                return objet, (ox, oy)
    return None


def _gid_vide(tx, ty):
    """Tuile de vide remise à la place d'une base enlevée."""
    return VIDE_GID


def cible_deconstruction(game_map, camera, pos_souris, hitbox_hero, coffres=None):
    """(structure, peut) pour la case sous la souris :
    structure = (construction, (ox, oy)) ou None s'il n'y a rien à enlever ;
    peut = False si on ne peut pas l'enlever maintenant : une base sur laquelle il y a
    encore une structure, sous le héros (il serait coincé dans le vide), ou un coffre
    qui n'est pas vide."""
    tx, ty = case_sous_souris(game_map, camera, pos_souris)
    structure = trouver_structure(game_map, tx, ty)
    if structure is None:
        return None, False

    objet, (ox, oy) = structure
    if getattr(objet, "COFFRE", False) and coffres is not None and not coffres.est_vide(ox, oy):
        return structure, False
    if objet.CALQUE == CALQUE_BASE:
        cases = [(ox + dx, oy + dy) for dx, dy, _ in objet.TUILES]
        if any(game_map.get_layer_gid(nom, x, y) != 0
               for nom in game_map.layers if nom != objet.CALQUE and nom not in game_map.calques_sol
               for x, y in cases):
            return structure, False
        largeur, hauteur = taille_bloc(objet.TUILES)
        zone = pygame.Rect(ox * game_map.tilewidth, oy * game_map.tileheight,
                           largeur * game_map.tilewidth, hauteur * game_map.tileheight)
        if hitbox_hero.colliderect(zone):
            return structure, False
    return structure, True


def deconstruire(game_map, camera, pos_souris, hitbox_hero, inventaire, coffres=None):
    """Enlève la structure sous la souris (une base redevient du vide) et en rend un
    exemplaire à l'inventaire ; rien n'est enlevé s'il n'y a plus de place.
    Renvoie (construction, (ox, oy)) de ce qui a été enlevé, ou None."""
    structure, peut = cible_deconstruction(game_map, camera, pos_souris, hitbox_hero, coffres)
    if structure is None or not peut:
        return None
    objet, (ox, oy) = structure
    if inventaire.place_pour(objet) < 1:
        return None
    inventaire.ajouter_objet(objet)
    for dx, dy, _ in objet.TUILES:
        x, y = ox + dx, oy + dy
        # (une base enlevée redevient du vide de l'espace ; sur une planète, le sol réapparaît)
        gid = _gid_vide(x, y) if objet.CALQUE == CALQUE_BASE and not game_map.planete else 0
        game_map.set_gid(x, y, gid, objet.CALQUE)
    return structure


def base_proche(game_map, x, y, rayon):
    """Case (tx, ty) de base la plus proche du point (x, y) en pixels monde, dans le rayon
    donné (None s'il n'y en a pas). Une case de base = tuile du calque base qui n'est pas du vide."""
    taille = game_map.chunk_size
    pas_x, pas_y = taille * game_map.tilewidth, taille * game_map.tileheight
    meilleure, distance_min = None, rayon
    for (cx, cy), grille in game_map.layers[CALQUE_BASE].items():
        if (cx + 1) * pas_x < x - rayon or cx * pas_x > x + rayon:
            continue
        if (cy + 1) * pas_y < y - rayon or cy * pas_y > y + rayon:
            continue
        for ly, ligne in enumerate(grille):
            for lx, gid in enumerate(ligne):
                if gid in VIDE_GIDS:
                    continue
                tx, ty = cx * taille + lx, cy * taille + ly
                distance = math.hypot((tx + 0.5) * game_map.tilewidth - x,
                                      (ty + 0.5) * game_map.tileheight - y)
                if distance <= distance_min:
                    meilleure, distance_min = (tx, ty), distance
    return meilleure


def reapparition(game_map, hero, defaut):
    """Position (x, y) du héros quand il réapparaît après sa mort : sur la case de base (plateforme
    visible : posée par le joueur ou dessinée dans la carte) la plus proche de là où il est mort, où
    il a la place de se tenir. `defaut` s'il n'y a aucune base."""
    taille = game_map.chunk_size
    mort_x, mort_y = hero.hitbox(hero.x, hero.y).center
    cases = []
    for (cx, cy), grille in game_map.layers[CALQUE_BASE].items():
        gids = set()
        for ligne in grille:
            gids.update(ligne)
        if not any(gid not in VIDE_GIDS and gid not in PLANETES_GIDS and game_map.tuile_visible(gid) for gid in gids):
            continue  # (presque tous les chunks : pas de plateforme, on ne regarde pas case par case)
        for ly, ligne in enumerate(grille):
            for lx, gid in enumerate(ligne):
                if gid not in VIDE_GIDS and gid not in PLANETES_GIDS and game_map.tuile_visible(gid):
                    cases.append((cx * taille + lx, cy * taille + ly))
    centre = hero.hitbox(0, 0).center  # (le héros est placé pour que sa hitbox soit au milieu de la case)

    def distance(case):
        return math.hypot((case[0] + 0.5) * game_map.tilewidth - mort_x, (case[1] + 0.5) * game_map.tileheight - mort_y)

    for tx, ty in sorted(cases, key=distance):
        x = (tx + 0.5) * game_map.tilewidth - centre[0]
        y = (ty + 0.5) * game_map.tileheight - centre[1]
        if not game_map.collides(hero.hitbox(x, y)):
            return x, y
    return defaut


def bloc_base(game_map, tx, ty):
    """(cases, origine) du bloc de base qui contient la case (tx, ty) : les 4 cases d'une base
    posée par le joueur, ou la case seule si c'est une autre tuile de plateforme."""
    for dx, dy, gid in base.TUILES:
        if game_map.get_layer_gid(CALQUE_BASE, tx, ty) != gid:
            continue
        ox, oy = tx - dx, ty - dy
        if all(game_map.get_layer_gid(CALQUE_BASE, ox + ddx, oy + ddy) == g for ddx, ddy, g in base.TUILES):
            return [(ox + ddx, oy + ddy) for ddx, ddy, _ in base.TUILES], (ox, oy)
    return [(tx, ty)], (tx, ty)


def detruire_cases(game_map, cases):
    """Détruit des cases de base : elles redeviennent du vide et tout ce qui était posé
    dessus (ou accroché dessous) est cassé, sans rien rendre. Renvoie la liste des
    structures cassées, [(construction, (ox, oy)), ...], pour que le jeu retire aussi leurs
    robots, coffres, tourelles..."""
    casses = []

    def casser(structure):
        objet, (ox, oy) = structure
        for dx, dy, _ in objet.TUILES:
            game_map.set_gid(ox + dx, oy + dy, 0, objet.CALQUE)
        casses.append(structure)

    for x, y in cases:
        game_map.set_gid(x, y, VIDE_GID, CALQUE_BASE)
    for x, y in cases:
        while any(game_map.get_layer_gid(nom, x, y) != 0 for nom in game_map.layers if nom != CALQUE_BASE):
            structure = trouver_structure(game_map, x, y)
            if structure is None or structure[0].CALQUE == CALQUE_BASE:
                for nom in game_map.layers:  # tuile sans structure connue : on l'efface seule
                    if nom != CALQUE_BASE:
                        game_map.set_gid(x, y, 0, nom)
                break
            casser(structure)
    for x, y in cases:
        structure = trouver_structure(game_map, x, y + 1)  # accroché sous le bord bas : plus de support
        if structure is not None and getattr(structure[0], "SOUS_FONDATION", False):
            ox, oy = structure[1]
            if any(game_map.get_layer_gid(CALQUE_BASE, ox + dx, oy + dy - 1) in VIDE_GIDS
                   for dx, dy, _ in structure[0].TUILES):
                casser(structure)
    return casses


def dessiner_zone_deconstruction(screen, game_map, camera, pos_souris, hitbox_hero, coffres=None):
    """Entoure la structure visée : orange si on peut l'enlever, rouge sinon."""
    structure, peut = cible_deconstruction(game_map, camera, pos_souris, hitbox_hero, coffres)
    if structure is None:
        return
    objet, (ox, oy) = structure
    largeur, hauteur = taille_bloc(objet.TUILES)
    if peut:
        couleur, bordure = COULEUR_DECONSTRUCTION, COULEUR_DECONSTRUCTION_BORDURE
    else:
        couleur, bordure = COULEUR_ZONE_REFUSEE, COULEUR_ZONE_REFUSEE_BORDURE
    _dessiner_rect(screen, game_map, camera, ox, oy, largeur, hauteur, couleur, bordure)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
