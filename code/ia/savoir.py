"""Connaissances fixes que l'IA lit ici plutôt que de les deviner mot par mot.

Un vaisseau qui porte le nom d'une constellation (Orion) sait quelles étoiles en font partie.
Pour ajouter une constellation : une entrée de plus dans CONSTELLATIONS.
Ce module n'a pas besoin de torch : il répond avant le modèle, et seulement si la question est précise.
"""
import re
import unicodedata

# clé (en minuscules, sans accents) -> nom affiché et membres : (nom, façons de l'écrire, description)
CONSTELLATIONS = {
    "orion": {
        "nom": "Orion",
        "membres": [
            ("Bételgeuse", ("betelgeuse", "alpha orionis"), "supergéante rouge, située à l'épaule du chasseur"),
            ("Rigel", ("rigel", "beta orionis"), "supergéante bleue, située au pied du chasseur"),
            ("Bellatrix", ("bellatrix", "gamma orionis"), "étoile bleue, à l'autre épaule"),
            ("Saïph", ("saiph", "kappa orionis"), "étoile bleue, au genou du chasseur"),
            ("Alnitak", ("alnitak", "zeta orionis"), "étoile de la ceinture, la plus à l'est"),
            ("Alnilam", ("alnilam", "epsilon orionis"), "étoile du milieu de la ceinture"),
            ("Mintaka", ("mintaka", "delta orionis"), "étoile de la ceinture, la plus à l'ouest"),
            ("Méissa", ("meissa", "lambda orionis"), "étoile qui marque la tête du chasseur"),
            ("Nébuleuse d'Orion", ("nebuleuse d orion", "m42"), "nuage de gaz où naissent de nouvelles étoiles"),
        ],
    },
}

# mots qui demandent la liste complète des membres
MOTS_LISTE = ("membres", "membre", "constellation", "etoiles", "composent", "compose", "composee", "liste")


def _normaliser(texte):
    """Minuscules, sans accents, ponctuation remplacée par des espaces."""
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", texte))


def _encadrer(texte):
    """« rigel » -> « rigel » entouré d'espaces, pour ne chercher que des mots entiers."""
    return f" {_normaliser(texte)} "


def _constellation_de(station):
    """Clé de la constellation portée par le nom du vaisseau (« Orion » -> « orion »), ou None."""
    if not station:
        return None
    return next((cle for cle in CONSTELLATIONS if f" {cle} " in _encadrer(station)), None)


def repondre(question, station=None):
    """Réponse exacte si la question porte sur une constellation connue, sinon None.

    station : nom du vaisseau qui reçoit le message (« Orion »). Sans lui, la question doit nommer la
    constellation elle-même (« les membres d'Orion »)."""
    q = _encadrer(question)
    cle = _constellation_de(station) or next((c for c in CONSTELLATIONS if f" {c} " in q), None)
    if cle is None:
        return None
    constellation = CONSTELLATIONS[cle]
    nom, membres = constellation["nom"], constellation["membres"]

    # une étoile nommée dans une question sur la constellation : on dit si elle en fait partie
    for etoile, facons, description in membres:
        if any(f" {f} " in q for f in facons):
            return f"Oui, {etoile} fait partie de la constellation {nom} : {description}."

    if any(f" {mot} " in q for mot in MOTS_LISTE):
        return f"La constellation {nom} compte : " + ", ".join(e for e, _, _ in membres) + "."
    return None
