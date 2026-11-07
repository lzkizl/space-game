"""Chaque mot de mots_francais.json reçoit une fréquence radio entre 200 et 800 MHz.

Le numéro du mot est étalé régulièrement sur la bande: le mot 0 est à 200 MHz, le dernier à 800 MHz.
Un vaisseau envoie une phrase comme une suite de fréquences, l'autre vaisseau les retransforme en mots.

Usage: python radio.py "bonjour vaisseau"
"""
import json
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
F_MIN, F_MAX = 200.0, 800.0   # MHz

with open(os.path.join(DIR, "donnees", "mots_francais.json"), encoding="utf-8") as f:
    NUMERO = json.load(f)
MOTS = {n: m for m, n in NUMERO.items()}
# La bande est découpée pour 2 097 152 mots (21 bits): ainsi la fréquence d'un mot ne change JAMAIS
# quand le dictionnaire grandit (tant qu'il reste sous cette limite). Écart entre deux mots: 0,29 kHz.
CAPACITE = 2_097_152
DERNIER = CAPACITE - 1
PAS = (F_MAX - F_MIN) / DERNIER


def mot_vers_freq(mot):
    """Fréquence en MHz d'un mot, ou None si le mot est inconnu."""
    n = NUMERO.get(mot.lower())
    return None if n is None else round(F_MIN + n * PAS, 6)


def freq_vers_mot(freq):
    """Mot correspondant à la fréquence reçue (le plus proche, même si le signal est un peu bruité)."""
    if not F_MIN - PAS <= freq <= F_MAX + PAS:
        return None
    n = round((freq - F_MIN) / PAS)
    return MOTS.get(min(max(n, 0), DERNIER))


def emettre(phrase):
    """Phrase -> liste de fréquences (MHz). Les mots inconnus sont ignorés."""
    freqs = (mot_vers_freq(m) for m in phrase.split())
    return [f for f in freqs if f is not None]


def recevoir(freqs):
    """Liste de fréquences -> phrase."""
    mots = (freq_vers_mot(f) for f in freqs)
    return " ".join(m for m in mots if m)


if __name__ == "__main__":
    phrase = " ".join(sys.argv[1:]) or "bonjour vaisseau"
    for m in phrase.split():
        f = mot_vers_freq(m)
        print(f"{m:15}", f"{f:10.4f} MHz" if f else "mot inconnu (ignoré)")
    print("reçu :", recevoir(emettre(phrase)))
