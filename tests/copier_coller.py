"""Verifie le copier-coller de l'adresse de l'hote dans le menu « Rejoindre une partie » :
Ctrl+C, Ctrl+X et Ctrl+V dans les deux champs, le nettoyage de ce qu'on colle, et le fait qu'un
Ctrl+touche n'ecrive jamais de caractere parasite dans le champ.

Le presse-papiers du systeme n'existe pas sans fenetre : on en simule un (c'est la logique de
saisie qu'on teste). Avec une vraie fenetre, un dernier aller-retour utilise le vrai.

Usage : python copier_coller.py <dossier_code>
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

DOSSIER_CODE = sys.argv[1]
sys.path.insert(0, DOSSIER_CODE)

import pygame

pygame.init()
pygame.display.set_mode((800, 600))

from interface import accueil as mod_accueil
from interface.accueil import Accueil, decouper_adresse, nettoyer_saisie

ECHECS = []


def verifier(condition, message):
    print(("   ok   " if condition else "   ECHEC ") + message)
    if not condition:
        ECHECS.append(message)


def touche(key, mod=0, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode=unicode)


CTRL = pygame.KMOD_LCTRL

# ---- presse-papiers simule (il n'y en a pas de vrai sans fenetre) ----
PRESSE_PAPIERS = {"texte": ""}
mod_accueil._presse_papiers_lire = lambda: PRESSE_PAPIERS["texte"]


def _ecrire(texte):
    PRESSE_PAPIERS["texte"] = texte
    return True


mod_accueil._presse_papiers_ecrire = _ecrire

menu = Accueil(1600, 900)

print("-- ce qu'on colle est nettoye")
verifier(nettoyer_saisie(" 192.168.1.12:50000 \r\n", "adresse") == "192.168.1.12:50000",
         "une adresse collee perd espaces et retours a la ligne")
verifier(nettoyer_saisie("Jean Neige\n", "pseudo") == "Jean Neige",
         "un pseudo colle garde ses espaces mais perd le retour a la ligne")
verifier(decouper_adresse("192.168.1.12:50001") == ("192.168.1.12", 50001),
         "l'adresse collee se decoupe en ip + port")

print("-- on arrive directement dans le champ adresse")
menu.pseudo = "Tim"
menu._aller("rejoindre")
verifier(menu.champ == "adresse", f"le champ adresse a le focus ({menu.champ})")

print("-- Ctrl+V colle dans l'adresse")
menu.adresse = ""
PRESSE_PAPIERS["texte"] = "192.168.1.42:50000"
menu._evenement_rejoindre(touche(pygame.K_v, CTRL, "\x16"))
verifier(menu.adresse == "192.168.1.42:50000", f"adresse = {menu.adresse!r}")

print("-- Ctrl+C copie, Ctrl+X coupe")
menu.adresse = "10.0.0.7"
PRESSE_PAPIERS["texte"] = "autre chose"
menu._evenement_rejoindre(touche(pygame.K_c, CTRL, "\x03"))
verifier(PRESSE_PAPIERS["texte"] == "10.0.0.7", f"Ctrl+C a copie {PRESSE_PAPIERS['texte']!r}")
menu._evenement_rejoindre(touche(pygame.K_x, CTRL, "\x18"))
verifier(menu.adresse == "", f"Ctrl+X a vide le champ ({menu.adresse!r})")
menu._evenement_rejoindre(touche(pygame.K_v, CTRL, "\x16"))
verifier(menu.adresse == "10.0.0.7", "Ctrl+V recolle ce qui a ete coupe")

print("-- ca marche aussi dans le champ pseudo")
menu.champ = "pseudo"
menu.pseudo = ""
PRESSE_PAPIERS["texte"] = "Capitaine"
menu._evenement_rejoindre(touche(pygame.K_v, CTRL, "\x16"))
verifier(menu.pseudo == "Capitaine", f"pseudo = {menu.pseudo!r}")

print("-- Ctrl+V sans avoir clique dans un champ vise l'adresse")
menu.champ = None
menu.adresse = ""
PRESSE_PAPIERS["texte"] = "172.16.0.9"
menu._evenement_rejoindre(touche(pygame.K_v, CTRL, "\x16"))
verifier(menu.adresse == "172.16.0.9", f"adresse = {menu.adresse!r}")

print("-- Ctrl+touche n'ecrit pas de caractere parasite")
menu.champ = "adresse"
menu.adresse = "1.2.3.4"
menu._evenement_rejoindre(touche(pygame.K_a, CTRL, "\x01"))
verifier(menu.adresse == "1.2.3.4", f"Ctrl+A ne change rien ({menu.adresse!r})")

print("-- on colle a la suite de ce qui est deja tape, sans depasser la longueur maximale")
menu.adresse = "192.168."
PRESSE_PAPIERS["texte"] = "1.12"
menu._evenement_rejoindre(touche(pygame.K_v, CTRL, "\x16"))
verifier(menu.adresse == "192.168.1.12", f"adresse = {menu.adresse!r}")
menu.adresse = ""
PRESSE_PAPIERS["texte"] = "x" * 300
menu._evenement_rejoindre(touche(pygame.K_v, CTRL, "\x16"))
verifier(len(menu.adresse) == mod_accueil.TAILLE_MAX_ADRESSE, f"longueur = {len(menu.adresse)}")

print("-- avec un vrai presse-papiers (ignore sans fenetre)")
try:
    pygame.scrap.init()
    disponible = True
except (pygame.error, AttributeError):
    disponible = False
if not disponible:
    print("   (pas de presse-papiers sans fenetre : partie ignoree)")
else:
    verifier(mod_accueil.__dict__["_presse_papiers_ecrire"] is _ecrire, "le test a bien son faux presse-papiers")
    # on remet les vraies fonctions pour un aller-retour complet
    import importlib

    vrai = importlib.reload(mod_accueil)
    verifier(vrai._presse_papiers_ecrire("10.11.12.13"), "le texte part dans le presse-papiers")
    verifier(vrai._presse_papiers_lire() == "10.11.12.13",
             f"et on le relit tel quel ({vrai._presse_papiers_lire()!r})")

print()
if ECHECS:
    print(f"{len(ECHECS)} ECHEC(S)")
    sys.exit(1)
print("OK : le copier-coller de l'adresse fonctionne")
