"""Verifie la propulsion reecrite : plusieurs bases peuvent etre poussees en meme temps, chacune
emmene SES passagers, et la carte les dessine chacune avec son propre decalage.

Usage : python propulsion_test.py <dossier_code>
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

DOSSIER_CODE = sys.argv[1]
sys.path.insert(0, DOSSIER_CODE)

import pygame

pygame.init()
pygame.display.set_mode((1280, 720))

from construction import boitier as mod_boitier, reacteur as mod_reacteur
from joueur.joueur import Joueur
from monde.map import Map
from monde.plantes import Plantes
from structures.coffres import Coffres
from structures.propulsion import Propulsion, structure_liee
from structures.robot import Robots
from structures.tourelles import Tourelles
from systeme.ressources import CLE_USB_REACTEUR, HYDROGENE, OXYGENE, PROCESSEUR, RAM
from systeme.settings import CALQUE_BASE, CALQUE_PLANTES, MAP_PATH

GID_BASE = 3        # une tuile de base (voir construction/base.py)
GID_REACTEUR = mod_reacteur.TUILES[0][2]
GID_BOITIER = mod_boitier.TUILES[0][2]

ECHECS = []


def verifier(condition, message):
    if condition:
        print(f"   ok   {message}")
    else:
        print(f"   ECHEC {message}")
        ECHECS.append(message)


def batir(carte, coffres, tx, ty, direction):
    """Une plateforme 3x3 en (tx, ty) avec un boitier pilote et un reacteur sous son bord bas.
    Renvoie (cases de la base, le Coffre du reacteur)."""
    cases = [(tx + dx, ty + dy) for dx in range(3) for dy in range(3)]
    for x, y in cases:
        carte.set_gid(x, y, GID_BASE, CALQUE_BASE)

    # le boitier, sur la base, avec de quoi piloter les reacteurs
    carte.set_gid(tx, ty, GID_BOITIER, CALQUE_PLANTES)
    boite = coffres.ajouter(tx, ty, mod_boitier)
    boite.objets[:] = [PROCESSEUR, RAM, CLE_USB_REACTEUR]
    boite.nombres[:] = [1, 1, 1]
    boite.marche = True
    boite.direction = direction

    # le reacteur, dans le vide juste sous le bord bas, plein d'oxygene et d'hydrogene
    rx, ry = tx + 1, ty + 3
    carte.set_gid(rx, ry, GID_REACTEUR, CALQUE_PLANTES)
    reacteur = coffres.ajouter(rx, ry, mod_reacteur)
    reacteur.objets[:] = [OXYGENE, HYDROGENE]
    reacteur.nombres[:] = [50, 50]
    reacteur.pousse = True
    return cases, reacteur


def poser_joueur(joueur, carte, tx, ty):
    """Plante le joueur au milieu de la case (tx, ty)."""
    milieu = joueur.hero.hitbox(0, 0)
    joueur.hero.x = (tx + 0.5) * carte.tilewidth - (milieu.centerx)
    joueur.hero.y = (ty + 0.5) * carte.tileheight - (milieu.centery)


carte = Map(MAP_PATH)
carte.definir_graine(None)  # pas de terrain genere : on ne batit que ce qu'on pose
coffres, robots, plantes, tourelles = Coffres(), Robots(), Plantes(), Tourelles()
propulsion = Propulsion()

# deux plateformes tres eloignees, poussees dans deux directions differentes
CASES_A, reacteur_a = batir(carte, coffres, 1000, 1000, (1, 0))    # vers la droite
CASES_B, reacteur_b = batir(carte, coffres, 5000, 5000, (0, -1))   # vers le haut

alice = Joueur("Alice", 0, 0, 1280, 720)
bob = Joueur("Bob", 0, 0, 1280, 720)
charlie = Joueur("Charlie", 0, 0, 1280, 720)  # celui-la reste dans le vide, il ne voyage pas
poser_joueur(alice, carte, 1001, 1001)   # au milieu de la plateforme A
poser_joueur(bob, carte, 5001, 5001)     # au milieu de la plateforme B
poser_joueur(charlie, carte, 9000, 9000)
joueurs = [alice, bob, charlie]
depart = {j.pseudo: (j.hero.x, j.hero.y) for j in joueurs}

print("-- un pas de chaque plateforme")
# les deux reacteurs sont pile a l'instant de leur pas ; on avance d'un tout petit dt pour que le
# glissement n'ait pas le temps de se resorber dans le meme appel (il fond d'une tuile par DELAI_PAS)
for coffre in (reacteur_a, reacteur_b):
    coffre.progres = mod_reacteur.DELAI_PAS
DT = 0.01
propulsion.update(DT, carte, coffres, robots, plantes, tourelles, joueurs)

tw, th = carte.tilewidth, carte.tileheight
fondu = tw / mod_reacteur.DELAI_PAS * DT  # ce que le glissement a deja rattrape
verifier(alice.hero.x == depart["Alice"][0] + tw and alice.hero.y == depart["Alice"][1],
         "Alice a avance d'une tuile vers la droite, avec sa plateforme")
verifier(bob.hero.y == depart["Bob"][1] - th and bob.hero.x == depart["Bob"][0],
         "Bob a avance d'une tuile vers le haut, avec la sienne")
verifier((charlie.hero.x, charlie.hero.y) == depart["Charlie"],
         "Charlie, qui n'est sur aucune base, n'a pas bouge")

verifier(len(propulsion.glissements) == 2, f"deux bases glissent en meme temps ({len(propulsion.glissements)})")
ga = propulsion._glissement_de(alice)
gb = propulsion._glissement_de(bob)
verifier(ga is not None and gb is not None and ga is not gb,
         "Alice et Bob sont passagers de deux glissements differents")
verifier(propulsion._glissement_de(charlie) is None, "Charlie n'est passager de rien")
verifier(ga.decalage == [-(tw - fondu), 0.0], f"le decalage d'Alice est horizontal ({ga.decalage})")
verifier(gb.decalage == [0.0, th - fondu], f"celui de Bob est vertical ({gb.decalage})")

print("-- la carte dessine les deux, chacune a son decalage")
verifier(len(carte.groupes) == 2, f"la carte a deux groupes animes ({len(carte.groupes)})")
decalages = sorted(tuple(d) for _, d in carte.groupes)
verifier(decalages == sorted([(-(tw - fondu), 0.0), (0.0, th - fondu)]),
         f"les deux decalages sont distincts et corrects ({decalages})")
verifier(len(carte.masque) == len(CASES_A) + len(CASES_B) + 2,
         "le masque reunit les cases des deux plateformes (reacteurs compris)")
surfaces = {cases: carte.image_masque(cases)[1] for cases, _ in carte.groupes}
verifier(len(set(surfaces.values())) == 2, "chaque plateforme a sa propre image, a son propre coin")

print("-- les decalages de camera sont propres a chaque joueur")
offset = (0.0, 0.0)
verifier(propulsion.offset_hero(offset, alice) == (tw - fondu, 0.0), "Alice est dessinee decalee a gauche")
verifier(propulsion.offset_hero(offset, bob) == (0.0, -(th - fondu)), "Bob est dessine decale en bas")
verifier(propulsion.offset_hero(offset, charlie) == offset, "Charlie est dessine sans decalage")
verifier(propulsion.cible_camera(charlie) is charlie.hero, "la camera de Charlie suit son heros tel quel")
suivi = propulsion.cible_camera(alice)
verifier(suivi.x == alice.hero.x - (tw - fondu), "la camera d'Alice suit son heros en train de glisser")

print("-- le glissement fond puis disparait")
for coffre in (reacteur_a, reacteur_b):
    coffre.objets[:] = [None, None]   # plus de carburant : plus de poussee
    coffre.nombres[:] = [0, 0]
    coffre.reserve = 0.0
for _ in range(60):
    propulsion.update(0.05, carte, coffres, robots, plantes, tourelles, joueurs)
verifier(propulsion.glissements == [], "plus rien ne glisse une fois les reacteurs a sec")
verifier(carte.groupes == [] and carte.masque == frozenset(), "la carte ne met plus rien a part")

print("-- la structure a bien bouge sur la carte")
apres_a = structure_liee(carte, (1001 + 1, 1001))
verifier(apres_a is not None and (1003, 1000) in apres_a,
         "la plateforme A occupe desormais la colonne de droite")

print()
if ECHECS:
    print(f"{len(ECHECS)} ECHEC(S)")
    sys.exit(1)
print("OK : la propulsion gere plusieurs bases et plusieurs passagers")
