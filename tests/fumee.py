"""Test de fumee : cree un monde neuf, fait tourner la vraie boucle de jeu quelques images
sans fenetre (SDL dummy), puis sauvegarde, recharge et retourne quelques images de plus.

Usage : python fumee.py <dossier_code> [nb_images]
Sort en code 0 si tout s'est bien passe.
"""
import os
import sys
import traceback

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

DOSSIER_CODE = sys.argv[1]
IMAGES = int(sys.argv[2]) if len(sys.argv) > 2 else 60
sys.path.insert(0, DOSSIER_CODE)

import pygame

pygame.init()

import main
from systeme import ecran as mod_ecran
from systeme import sauvegarde

screen = mod_ecran.creer()  # comme main.main() : c'est lui qui ouvre la fenetre (voir systeme/ecran.py)

MONDE = "__fumee__"

vrai_event_get = pygame.event.get
restant = {"n": 0}


def event_get_limite(*args, **kwargs):
    """Rend la main au bout de `restant` images en simulant la fermeture de la fenetre."""
    restant["n"] -= 1
    if restant["n"] <= 0:
        return [pygame.event.Event(pygame.QUIT)]
    return vrai_event_get(*args, **kwargs)


pygame.event.get = event_get_limite


def tourner(nouveau, images):
    # `quitter()` appelle pygame.quit() : on remonte un affichage a chaque passage
    pygame.init()
    mod_ecran._ecran = None  # (pygame.quit() a detruit la fenetre : on la fait rouvrir)
    ecran = mod_ecran.creer()
    pygame.event.get = event_get_limite
    restant["n"] = images
    reglages = {"graine": 424242, "delai": 5} if nouveau else None
    try:
        main.jouer(ecran, MONDE, nouveau, reglages)
    except SystemExit:
        pass  # fermeture normale : `quitter()` leve SystemExit apres avoir sauvegarde


code = 0
try:
    print(f"-- monde neuf, {IMAGES} images")
    tourner(True, IMAGES)
    etat = sauvegarde.charger(MONDE)
    assert "joueurs" in etat or "hero" in etat, "la sauvegarde ne contient pas de joueur"
    print(f"-- rechargement, {IMAGES} images")
    tourner(False, IMAGES)
    print("OK : boucle de jeu, sauvegarde et rechargement")
except Exception:
    traceback.print_exc()
    code = 1
finally:
    sauvegarde.supprimer(MONDE)

sys.exit(code)
