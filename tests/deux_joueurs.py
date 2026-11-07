"""Verifie que le monde sait deja gerer PLUSIEURS joueurs : les ennemis choisissent leur cible,
les degats vont au bon joueur, un vaisseau ne se pilote qu'a une personne, et la sauvegarde
relit tout le monde.

Usage : python deux_joueurs.py <dossier_code>
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

from ennemis.alien import Alien, Aliens
from ennemis.trou_noir import TrousNoirs, TrouNoir
from ennemis.meteroite import Meteorites
from ennemis.vaisseau import Vaisseaux, Tir
from joueur.joueur import Joueur, plus_proche
from monde.map import Map
from structures.vaisseaux_joueur import VaisseauJoueur, VaisseauxJoueur
from systeme import sauvegarde
from systeme.settings import MAP_PATH, VIE_MAX

ECHECS = []


def verifier(condition, message):
    if condition:
        print(f"   ok   {message}")
    else:
        print(f"   ECHEC {message}")
        ECHECS.append(message)


def deux():
    """Deux joueurs eloignes l'un de l'autre, chacun avec sa camera posee sur lui."""
    a = Joueur("Alice", 0, 0, 1280, 720)
    b = Joueur("Bob", 100000, 100000, 1280, 720)
    for j in (a, b):
        j.camera.x, j.camera.y = j.hero.x, j.hero.y
    return a, b


print("-- la cible la plus proche")
a, b = deux()
verifier(plus_proche([a, b], 10, 10) is a, "le point pres d'Alice designe Alice")
verifier(plus_proche([a, b], 99000, 99000) is b, "le point pres de Bob designe Bob")
verifier(plus_proche([], 0, 0) is None, "aucun joueur : aucune cible")

print("-- les aliens mordent le joueur qu'ils touchent")
a, b = deux()
aliens = Aliens(premiere_attaque=0)
aliens.liste.append(Alien(b.hero.x + 20, b.hero.y + 40))  # colle a Bob
for _ in range(10):
    aliens.update(0.1, [a, b])
verifier(b.vie.value < VIE_MAX, f"Bob perd de la vie ({b.vie.value:.1f}/{VIE_MAX})")
verifier(a.vie.value == VIE_MAX, "Alice, a l'autre bout du monde, est intacte")
verifier(len(aliens.liste) > 1, f"une troupe est apparue pres d'un joueur ({len(aliens.liste)} aliens)")

print("-- l'alien poursuit celui qui s'approche")
a, b = deux()
alien = Alien(500, 500)
Aliens(premiere_attaque=9999).liste  # (pas d'apparition parasite)
avant = (alien.x, alien.y)
alien.update(0.5, [a, b])          # Alice est en (0,0), Bob tres loin
verifier(alien.x < avant[0] and alien.y < avant[1], "il va vers Alice, la plus proche")
alien2 = Alien(99500, 99500)
alien2.update(0.5, [a, b])
verifier(alien2.x > 99500 and alien2.y > 99500, "l'autre va vers Bob, le plus proche de lui")

print("-- les balles ennemies touchent le joueur vise")
a, b = deux()
ennemis = Vaisseaux(premiere_attaque=9999)
cible = b.hero.hitbox(b.hero.x, b.hero.y).center
ennemis.tirs.append(Tir(cible[0], cible[1], 0.0))
ennemis.update(0.016, [a, b], Map(MAP_PATH))
verifier(b.vie.value < VIE_MAX, f"Bob est touche ({b.vie.value:.1f}/{VIE_MAX})")
verifier(a.vie.value == VIE_MAX, "Alice n'est pas touchee")

print("-- changer gauche/droite ne depasse pas les images disponibles")
hero = a.hero
touches = [0] * 512
touches[pygame.K_d] = 1
for _ in range(3):
    hero.update(0.15, touches)
touches[pygame.K_d] = 0
touches[pygame.K_q] = 1
hero.update(0.01, touches)
hero.draw(pygame.Surface((1280, 720)))
verifier(hero.direction == "gauche" and hero.numero_image < 2,
         "l'animation gauche repart sur un indice valide")

print("-- le trou noir attire tout le monde, pas seulement un")
a, b = deux()
trous = TrousNoirs()
trous.chrono = 9999
image = pygame.Surface((10, 10), pygame.SRCALPHA)
# un trou noir pile entre les deux (chacun a 100 px du centre, bien dans le rayon de gravite)
trous.liste.append(TrouNoir(a.hero.x + 100, a.hero.y + 100, 0, 0, image))
trous.liste.append(TrouNoir(b.hero.x + 100, b.hero.y + 100, 0, 0, image))
depart = ((a.hero.x, a.hero.y), (b.hero.x, b.hero.y))
trous.update(0.1, [a, b], Meteorites())
verifier((a.hero.x, a.hero.y) != depart[0], "Alice est aspiree")
verifier((b.hero.x, b.hero.y) != depart[1], "Bob est aspire aussi")

print("-- un vaisseau ne se pilote qu'a une personne")
a, b = deux()
b.hero.x, b.hero.y = a.hero.x, a.hero.y  # Bob rejoint Alice
engins = VaisseauxJoueur([a, b])
carte = Map(MAP_PATH)
# (on pose le vaisseau directement : `poser` refuserait, nos joueurs flottent dans le vide)
vaisseau = VaisseauJoueur(a.hero.x + 10, a.hero.y + 10)
engins.liste.append(vaisseau)
verifier(engins.monter(vaisseau, a) is True, "Alice monte dedans")
verifier(engins.monter(vaisseau, b) is False, "Bob ne peut pas monter dans le meme")
verifier(b.pilote is None and a.pilote is vaisseau, "seul le pilote d'Alice est renseigne")
verifier(engins.enlever(vaisseau.x + 5, vaisseau.y + 5, b, b.inventaire) is None,
         "Bob ne peut pas deconstruire un vaisseau occupe")
verifier(engins.descendre(b, carte) is False, "Bob, a pied, ne descend de rien")
# (Alice descend sur une carte factice qui n'a pas de vide sous elle)
class SolPlein:
    def collides(self, rect):
        return False
verifier(engins.descendre(a, SolPlein()) is True, "Alice descend")
verifier(a.pilote is None, "Alice n'est plus aux commandes")

print("-- la sauvegarde contient les deux joueurs")
a, b = deux()
engins = VaisseauxJoueur([a, b])
engins.liste.append(VaisseauJoueur(b.hero.x + 10, b.hero.y + 10))
engins.monter(engins.liste[0], b)  # c'est Bob qui pilote
exportes = [sauvegarde.exporter_joueur(j, engins) for j in (a, b)]
verifier([d["pseudo"] for d in exportes] == ["Alice", "Bob"], "les deux pseudos sont ecrits")
verifier(exportes[0]["pilote"] == -1 and exportes[1]["pilote"] == 0,
         "seul Bob est note comme pilote")

a2, b2 = deux()
engins2 = VaisseauxJoueur([a2, b2])
engins2.importer(engins.exporter(lambda cases: [None] * len(cases)), {})
for joueur, donnees in zip((a2, b2), exportes):
    sauvegarde.appliquer_joueur(donnees, joueur, engins2)
verifier((a2.pseudo, b2.pseudo) == ("Alice", "Bob"), "les pseudos sont relus")
verifier(a2.pilote is None and b2.pilote is engins2.liste[0], "Bob est toujours le pilote apres relecture")
verifier(round(a2.hero.x) == round(a.hero.x) and round(b2.hero.x) == round(b.hero.x),
         "chacun retrouve sa position")

print()
if ECHECS:
    print(f"{len(ECHECS)} ECHEC(S)")
    sys.exit(1)
print("OK : le monde gere deja deux joueurs")
