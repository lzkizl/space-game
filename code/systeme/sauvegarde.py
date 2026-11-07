import json
import re

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structures.building import CONSTRUCTIONS, ENGINS, OUTILS
from construction import coffre as construction_coffre, epave
from systeme.ressources import MINERAIS, OBJETS_FABRIQUES, RESSOURCES, Ressource
from systeme.settings import RACINE

# =============================================
# ==== Sauvegarde des mondes : un fichier saves/<nom>.json par monde
# =============================================
DOSSIER = RACINE / "saves"
VERSION = 1
NOMS_RESERVES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} \
    | {f"LPT{i}" for i in range(1, 10)}


# ---- fichiers ----
def nom_valide(nom):
    """Nom utilisable comme nom de fichier ("" s'il ne reste rien)."""
    nom = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nom).strip().strip(".")[:24].strip()
    return nom + "_" if nom.upper() in NOMS_RESERVES else nom


def _chemin(nom):
    return DOSSIER / f"{nom}.json"


def lister():
    """Mondes sauvegardés, du plus récemment joué au plus ancien : [(nom, date)]."""
    if not DOSSIER.exists():
        return []
    fichiers = sorted(DOSSIER.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [(f.stem, f.stat().st_mtime) for f in fichiers]


def nom_libre(nom):
    """Nom de monde qui n'existe pas encore (« Monde », « Monde 2 », ...)."""
    base = nom_valide(nom) or "Monde"
    candidat, n = base, 1
    while _chemin(candidat).exists():
        n += 1
        candidat = f"{base[:20]} {n}"
    return candidat


def sauver(nom, etat):
    DOSSIER.mkdir(exist_ok=True)
    temporaire = _chemin(nom).with_suffix(".tmp")
    temporaire.write_text(json.dumps(etat, separators=(",", ":")), encoding="utf-8")
    temporaire.replace(_chemin(nom))  # écriture atomique : pas de sauvegarde à moitié écrite


def charger(nom):
    return json.loads(_chemin(nom).read_text(encoding="utf-8"))


def supprimer(nom):
    _chemin(nom).unlink(missing_ok=True)


# ---- état du jeu <-> dictionnaire ----
def _id_objet(objet):
    """Identifiant texte d'un objet d'inventaire (construction, outil ou ressource)."""
    if isinstance(objet, Ressource):
        return "ressource." + objet.nom
    return objet.__name__


def objets_par_id():
    objets = {_id_objet(o): o for o in CONSTRUCTIONS + OUTILS + ENGINS + [epave]}  # (epave : type d'un conteneur sauvé)
    objets.update({_id_objet(r): r for r in RESSOURCES + OBJETS_FABRIQUES + MINERAIS})
    return objets


def ids_objets(cases):
    return [None if objet is None else _id_objet(objet) for objet in cases]


def _exporter_coffres(coffres):
    return [{"tx": c.tx, "ty": c.ty, "type": c.construction.__name__,
             "objets": ids_objets(c.objets), "nombres": c.nombres, "reserve": c.reserve,
             "marche": c.marche, "direction": list(c.direction),  # (boîtier : pilotage des réacteurs)
             "frequence": c.frequence}                            # (boîtier : télescope piloté)
            for c in coffres.coffres.values()]


def _exporter_robots(robots):
    return [{"tx": robot.tx, "ty": robot.ty, "x": robot.pos.x, "y": robot.pos.y,
             "stock": {r.nom: n for r, n in robot.stock.items()},
             "butin": None if robot.butin is None else {r.nom: n for r, n in robot.butin.items()}}
            for robot in robots.robots.values()]


def _appliquer_coffres(donnees, coffres, objets):
    for d in donnees:
        # "type" : coffre ou réacteur (absent des sauvegardes d'avant le réacteur : coffre)
        construction = objets.get(d.get("type", "construction.coffre"), construction_coffre)
        coffre = coffres.ajouter(d["tx"], d["ty"], construction)
        coffre.objets[:] = [objets.get(i) for i in d["objets"]]
        coffre.nombres[:] = d["nombres"]
        coffre.reserve = d.get("reserve", 0.0)  # absent des anciennes sauvegardes
        coffre.marche = d.get("marche", False)
        coffre.direction = tuple(d.get("direction", coffre.direction))
        coffre.frequence = d.get("frequence", coffre.frequence)


def _appliquer_robots(donnees, robots, game_map):
    par_nom = {r.nom: r for r in RESSOURCES}
    for d in donnees:
        robots.ajouter(d["tx"], d["ty"], game_map)
        robot = robots.robots[(d["tx"], d["ty"])]
        robot.pos.update(d["x"], d["y"])
        robot.rect.center = (round(robot.pos.x), round(robot.pos.y))
        for n, q in d["stock"].items():  # (une ressource ajoutée depuis reste à 0)
            robot.stock[par_nom[n]] = q
        if d["butin"] is not None:
            robot.butin = {par_nom[n]: q for n, q in d["butin"].items()}


# ---- les joueurs ----
_DEFAUT = object()  # « prends la valeur du joueur » (voir exporter_joueur)


def exporter_joueur(joueur, engins=None, hero=_DEFAUT, camera=_DEFAUT, pilote=_DEFAUT):
    """Un joueur, sous forme sérialisable. `hero`, `camera` et `pilote` remplacent les siens quand on
    le sauvegarde ailleurs qu'où il est (sur une planète, on l'enregistre remonté en orbite)."""
    hero = joueur.hero if hero is _DEFAUT else hero
    camera = joueur.camera if camera is _DEFAUT else camera
    pilote = joueur.pilote if pilote is _DEFAUT else pilote
    inventaire = joueur.inventaire
    return {
        "pseudo": joueur.pseudo,
        "id": joueur.id,  # son identifiant dans la partie (multijoueur)
        "hero": {"x": hero.x, "y": hero.y, "direction": hero.direction},
        "camera": {"x": camera.x, "y": camera.y, "zoom": camera.zoom},
        "oxygene": joueur.oxygene.value,
        "eau": joueur.eau.value,
        "faim": joueur.faim.value,
        "vie": joueur.vie.value,
        "inventaire": {
            "barre": ids_objets(inventaire.barre), "barre_nb": inventaire.barre_nb,
            "grille": ids_objets(inventaire.grille), "grille_nb": inventaire.grille_nb,
            "selection": inventaire.selected,
        },
        # le vaisseau piloté est repéré par sa place dans la liste des vaisseaux du monde
        "pilote": -1 if engins is None or pilote is None else engins.index(pilote),
    }


def appliquer_joueur(donnees, joueur, engins=None, objets=None):
    """Remet dans `joueur` (déjà créé) ce qu'une sauvegarde contient à son sujet."""
    objets = objets_par_id() if objets is None else objets
    if donnees.get("pseudo"):
        joueur.pseudo = donnees["pseudo"]
    joueur.hero.x, joueur.hero.y = donnees["hero"]["x"], donnees["hero"]["y"]
    joueur.hero.direction = donnees["hero"]["direction"]
    joueur.camera.x, joueur.camera.y = donnees["camera"]["x"], donnees["camera"]["y"]
    joueur.camera.zoom = donnees["camera"]["zoom"]
    joueur.oxygene.value = donnees["oxygene"]
    joueur.eau.value = donnees.get("eau", joueur.eau.value)    # absent des anciennes sauvegardes
    joueur.faim.value = donnees.get("faim", joueur.faim.value)
    joueur.vie.value = donnees.get("vie", joueur.vie.value)

    inv = donnees["inventaire"]
    joueur.inventaire.barre[:] = [objets.get(i) for i in inv["barre"]]
    joueur.inventaire.grille[:] = [objets.get(i) for i in inv["grille"]]
    joueur.inventaire.barre_nb[:] = inv["barre_nb"]
    joueur.inventaire.grille_nb[:] = inv["grille_nb"]
    joueur.inventaire.selected = inv["selection"]
    joueur.pilote = None if engins is None else engins.par_index(donnees.get("pilote", -1))


def joueurs_sauves(etat):
    """Les joueurs d'une sauvegarde, sous forme de dictionnaires. Les sauvegardes d'avant le
    multijoueur rangeaient le joueur unique à la racine : on le relit comme une partie à un joueur."""
    if "joueurs" in etat:
        return etat["joueurs"]
    ancien = {cle: etat[cle] for cle in ("hero", "camera", "oxygene", "eau", "faim", "vie", "inventaire")
              if cle in etat}
    ancien["pilote"] = etat.get("vaisseaux_joueur", {}).get("pilote", -1)
    return [ancien]


def exporter_installations(installations):
    """Ce qui est construit sur une planète (voir structures/installations.py) : les calques de sa carte que
    le jeu modifie et ses constructions, sous forme sérialisable."""
    return {"carte": installations.carte.exporter(),
            "coffres": _exporter_coffres(installations.coffres),
            "plantes": installations.plantes.exporter(),
            "tourelles": installations.tourelles.exporter(),
            "robots": _exporter_robots(installations.robots)}


def appliquer_installations(donnees, installations):
    """Remet sur la carte d'une planète (déjà chargée) ce qui y était construit (voir exporter_installations)."""
    carte = installations.carte
    carte.importer(donnees["carte"])
    installations.tourelles.importer(donnees["tourelles"], carte)
    installations.plantes.importer(donnees["plantes"])
    _appliquer_coffres(donnees["coffres"], installations.coffres, objets_par_id())
    _appliquer_robots(donnees["robots"], installations.robots, carte)


def capturer(game_map, joueurs, robots, plantes, coffres, tourelles,
             grande_carte=None, engins=None, aliens=None, vaisseaux=None, telescopes=None,
             planetes=None, recherches=None, cristaux=None, foreuses=None, constructions_planetes=None):
    """Tout ce qu'il faut pour retrouver le monde tel qu'il est. `joueurs` : la liste des joueurs déjà
    exportés (voir exporter_joueur). `constructions_planetes` : {carte d'une planète: ce qui y est
    construit (voir exporter_installations)}."""
    return {
        "version": VERSION,
        "joueurs": joueurs,
        "constructions_planetes": constructions_planetes or {},
        "foreuses": foreuses.exporter(ids_objets) if foreuses else {},  # foreuses posées sur les planètes (et leur contenu)
        "cristaux": cristaux.exporter() if cristaux else {},  # shards restants des cristaux déjà récoltés (planètes)
        "recherches": recherches.exporter() if recherches else [],  # recherches faites (table de recherche)
        "graine": game_map.graine,  # le terrain hors de la carte fabriquée à la main se retrouve à partir d'elle
        "chrono_aliens": None if aliens is None else aliens.chrono,  # temps restant avant la prochaine attaque
        "chrono_vaisseaux": None if vaisseaux is None else vaisseaux.chrono,
        "carte": game_map.exporter(),
        "exploration": grande_carte.exporter() if grande_carte else {},  # cases vues sur la grande carte
        "plantes": plantes.exporter(),
        "tourelles": tourelles.exporter(),
        "telescopes": telescopes.exporter() if telescopes else [],  # fréquence et pilotage de chaque télescope
        "temps_planetes": planetes.temps if planetes else 0.0,  # où en est Mars dans son tour du Soleil
        "vaisseaux_joueur": engins.exporter(ids_objets) if engins else {},
        "coffres": _exporter_coffres(coffres),
        "robots": _exporter_robots(robots),
    }


def appliquer(etat, game_map, joueurs, robots, plantes, coffres, tourelles,
              grande_carte=None, engins=None, aliens=None, vaisseaux=None, telescopes=None,
              planetes=None, recherches=None, cristaux=None, foreuses=None):
    """Remet dans le jeu (déjà créé) l'état lu dans une sauvegarde. `joueurs` : les joueurs à remplir,
    dans l'ordre de la sauvegarde ; ceux qu'elle ne contient pas gardent leur état de départ."""
    game_map.definir_graine(etat.get("graine"))  # absente des anciennes sauvegardes : pas de terrain généré
    if cristaux is not None:
        cristaux.importer(etat.get("cristaux", {}))  # absent des anciennes sauvegardes : aucun cristal récolté
    if recherches is not None:
        recherches.importer(etat.get("recherches", []))  # absent des anciennes sauvegardes : rien de recherché
    game_map.importer(etat["carte"])
    if aliens is not None and etat.get("chrono_aliens") is not None:
        aliens.chrono = etat["chrono_aliens"]
    if vaisseaux is not None and etat.get("chrono_vaisseaux") is not None:
        vaisseaux.chrono = etat["chrono_vaisseaux"]
    if grande_carte:
        grande_carte.importer(etat.get("exploration", {}))  # absent des anciennes sauvegardes

    objets = objets_par_id()
    if engins:
        engins.importer(etat.get("vaisseaux_joueur", {}), objets)  # absent des anciennes sauvegardes
    # (les joueurs après les vaisseaux : « qui pilote quoi » désigne un vaisseau de la liste)
    for joueur, donnees in zip(joueurs, joueurs_sauves(etat)):
        appliquer_joueur(donnees, joueur, engins, objets)
    if foreuses is not None:
        foreuses.importer(etat.get("foreuses", {}), objets)  # absent des anciennes sauvegardes
    tourelles.importer(etat.get("tourelles", []), game_map)  # (le monde les complète : scan)
    if telescopes:
        telescopes.importer(etat.get("telescopes", []))  # absent des anciennes sauvegardes
    if planetes:
        planetes.temps = etat.get("temps_planetes", 0.0)  # absent des anciennes sauvegardes : Mars au départ
    plantes.importer(etat.get("plantes", []))  # (le monde les complète : voir Plantes.scan)
    _appliquer_coffres(etat.get("coffres", []), coffres, objets)
    _appliquer_robots(etat["robots"], robots, game_map)
