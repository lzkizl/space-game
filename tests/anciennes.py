"""Verifie que les sauvegardes DEJA sur le disque (format d'avant le multijoueur) se rechargent
sans perte : on les charge dans une vraie partie, on compare ce qui est relu a ce que contient le
fichier, puis on re-sauvegarde sous un autre nom et on recharge encore.

Les fichiers d'origine ne sont JAMAIS modifies : on sauvegarde sous un nom temporaire.

Usage : python anciennes.py <dossier_code>
"""
import os
import sys
import traceback

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

DOSSIER_CODE = sys.argv[1]
sys.path.insert(0, DOSSIER_CODE)

import pygame

pygame.init()
pygame.display.set_mode((1280, 720))

from systeme import sauvegarde
from joueur.joueur import Joueur
from monde.map import Map
from monde.grande_carte import GrandeCarte
from monde.plantes import Plantes
from monde.planetes import Planetes
from monde.cristaux import Cristaux
from structures.coffres import Coffres
from structures.foreuses import Foreuses
from structures.robot import Robots
from structures.telescopes import Telescopes
from structures.tourelles import Tourelles
from structures.vaisseaux_joueur import VaisseauxJoueur
from joueur.recherche import Recherche
from ennemis.alien import Aliens
from ennemis.vaisseau import Vaisseaux
from systeme.settings import MAP_PATH


def charger_dans_une_partie(nom):
    """Monte le strict necessaire et applique la sauvegarde `nom`. Renvoie (joueur, objets du monde)."""
    etat = sauvegarde.charger(nom)
    game_map = Map(MAP_PATH)
    moi = Joueur("Joueur", 640, 360, 1280, 720)
    joueurs = [moi]
    monde = dict(
        robots=Robots(), plantes=Plantes(), coffres=Coffres(), tourelles=Tourelles(),
        grande_carte=GrandeCarte(1280, 720), engins=VaisseauxJoueur(joueurs),
        aliens=Aliens(), vaisseaux=Vaisseaux(), telescopes=Telescopes(game_map),
        planetes=Planetes(game_map), recherches=Recherche(1280, 720),
    )
    cristaux = Cristaux()
    monde_complet = dict(monde, cristaux=cristaux, foreuses=Foreuses(cristaux))
    sauvegarde.appliquer(etat, game_map, joueurs, monde["robots"], monde["plantes"],
                         monde["coffres"], monde["tourelles"], monde["grande_carte"],
                         monde["engins"], monde["aliens"], monde["vaisseaux"],
                         monde["telescopes"], monde["planetes"], monde["recherches"],
                         cristaux=cristaux, foreuses=monde_complet["foreuses"])
    return etat, game_map, moi, monde_complet


def nom_objet(o):
    """Nom lisible d'un objet d'inventaire (une Ressource a .nom, une construction est un module)."""
    if o is None:
        return None
    return o.nom if hasattr(o, "nom") else o.__name__


def resume(moi, monde):
    """Ce qu'on compare d'un chargement a l'autre."""
    inv = moi.inventaire
    return {
        "x": round(moi.hero.x, 3), "y": round(moi.hero.y, 3), "direction": moi.hero.direction,
        "zoom": moi.camera.zoom, "cam": (round(moi.camera.x, 3), round(moi.camera.y, 3)),
        "oxygene": moi.oxygene.value, "eau": moi.eau.value,
        "faim": moi.faim.value, "vie": moi.vie.value,
        "barre": [nom_objet(o) for o in inv.barre],
        "barre_nb": list(inv.barre_nb),
        "grille": [nom_objet(o) for o in inv.grille],
        "grille_nb": list(inv.grille_nb),
        "selection": inv.selected,
        "pilote": monde["engins"].index(moi.pilote),
        "nb_vaisseaux": len(monde["engins"].liste),
        "nb_coffres": len(monde["coffres"].coffres),
        "nb_robots": len(monde["robots"].robots),
    }


TEMPORAIRE = "__relu__"
code = 0
try:
    noms = [n for n, _ in sauvegarde.lister() if n != TEMPORAIRE]
    if not noms:
        print("aucune sauvegarde a verifier")
    for nom in noms:
        etat, game_map, moi, monde = charger_dans_une_partie(nom)
        avant = resume(moi, monde)
        formate = "multijoueur" if "joueurs" in etat else "ancien (solo)"
        print(f"-- {nom} : format {formate}")

        # verification directe contre le contenu brut du fichier
        brut = etat["joueurs"][0] if "joueurs" in etat else etat
        assert avant["x"] == round(brut["hero"]["x"], 3), f"{nom} : x du heros perdu"
        assert avant["y"] == round(brut["hero"]["y"], 3), f"{nom} : y du heros perdu"
        assert avant["oxygene"] == brut["oxygene"], f"{nom} : oxygene perdu"
        assert avant["selection"] == brut["inventaire"]["selection"], f"{nom} : selection perdue"
        attendu_pilote = brut.get("pilote", etat.get("vaisseaux_joueur", {}).get("pilote", -1))
        assert avant["pilote"] == attendu_pilote, f"{nom} : vaisseau pilote perdu"

        # aller-retour : on re-sauvegarde au nouveau format et on relit
        exportes = [sauvegarde.exporter_joueur(moi, monde["engins"])]
        sauvegarde.sauver(TEMPORAIRE, sauvegarde.capturer(
            game_map, exportes, monde["robots"], monde["plantes"], monde["coffres"],
            monde["tourelles"], monde["grande_carte"], monde["engins"], monde["aliens"],
            monde["vaisseaux"], monde["telescopes"], monde["planetes"], monde["recherches"],
            cristaux=monde["cristaux"], foreuses=monde["foreuses"]))
        _, _, moi2, monde2 = charger_dans_une_partie(TEMPORAIRE)
        apres = resume(moi2, monde2)
        for cle in avant:
            assert avant[cle] == apres[cle], f"{nom} : '{cle}' change ({avant[cle]!r} -> {apres[cle]!r})"
        print(f"   OK : relu a l'identique ({avant['nb_coffres']} coffres, "
              f"{avant['nb_robots']} robots, {avant['nb_vaisseaux']} vaisseaux)")
    print("OK : anciennes sauvegardes relues sans perte")
except Exception:
    traceback.print_exc()
    code = 1
finally:
    sauvegarde.supprimer(TEMPORAIRE)

sys.exit(code)
