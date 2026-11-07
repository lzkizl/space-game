import time

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reseau import protocole, transport

# =============================================
# ==== Le client : il rejoint la partie de quelqu'un d'autre.
# ====
# ==== Il ne simule rien du monde partagé (ennemis, production, propulsion) : tout ça lui
# ==== arrive de l'hôte. Il garde la main sur une seule chose, la position de son propre
# ==== héros, qu'il calcule chez lui et annonce 20 fois par seconde : c'est ce qui fait que
# ==== ses déplacements répondent instantanément malgré la latence.
# =============================================


class ErreurReseau(Exception):
    """Impossible de rejoindre la partie (hôte injoignable, refus, version différente)."""


def rejoindre(ip, port, pseudo, delai=10.0):
    """Se connecte, se présente, et attend le monde. Renvoie (connexion, mon_id, monde).

    C'est le seul moment où l'on a le droit d'attendre le réseau : on n'est pas encore en jeu.
    """
    try:
        connexion = transport.connecter(ip, port, delai=min(delai, 8.0))
    except OSError as erreur:
        raise ErreurReseau(f"Impossible de joindre {ip} : {erreur}") from erreur

    connexion.envoyer({"t": protocole.BONJOUR, "pseudo": pseudo, "version": protocole.VERSION})
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        message = connexion.attendre(0.25)
        if message is None:
            if not connexion.vivante:
                connexion.fermer()
                raise ErreurReseau("L'hôte a fermé la connexion.")
            continue
        type_message = message.get("t")
        if type_message == protocole.BIENVENUE:
            return connexion, message["id"], message["monde"]
        if type_message == protocole.REFUS:
            connexion.fermer()
            raise ErreurReseau(message.get("raison", "Entrée refusée."))
    connexion.fermer()
    raise ErreurReseau("L'hôte ne répond pas.")


class Client:
    """Côté client d'une partie en réseau. `tourner(dt)` à chaque image."""

    hote = False

    def __init__(self, connexion, partie, objets, ressources_par_nom):
        self.connexion = connexion
        self.partie = partie
        self.objets = objets                      # identifiant texte -> objet d'inventaire
        self.ids = {objet: identifiant for identifiant, objet in objets.items()}
        self.ressources_par_nom = ressources_par_nom
        self.fini = ""                            # rempli quand la partie se termine pour nous
        self.messages = []
        self.disparus = []                        # conteneurs enlevés par quelqu'un d'autre : le
        self._depuis_mouvement = 0.0              # jeu referme les panneaux ouverts dessus
        self._derniere_nouvelle = time.monotonic()

    def tourner(self, dt):
        self._recevoir()
        self._envoyer(dt)

    # ---- ce que l'hôte nous dit ----
    def _recevoir(self):
        recus = self.connexion.messages()
        if recus:
            self._derniere_nouvelle = time.monotonic()
        for message in recus:
            type_message = message.get("t")
            if type_message == protocole.INSTANTANE:
                self.partie.appliquer_instantane(message)
            elif type_message == protocole.TUILES:
                self.partie.game_map.appliquer_changements(message.get("l") or [])
                self.disparus += self.partie.scanner_structures()
            elif type_message == protocole.STRUCTURES:
                self.disparus += self.partie.appliquer_structures(
                    message, self.objets, self.ressources_par_nom)
            elif type_message in (protocole.FIN, protocole.REFUS):
                self.fini = message.get("raison", "La partie est terminée.")
        if not self.connexion.vivante and not self.fini:
            self.fini = "La connexion avec l'hôte est perdue."
        elif time.monotonic() - self._derniere_nouvelle > protocole.DELAI_SILENCE and not self.fini:
            self.fini = "L'hôte ne répond plus."

    # ---- ce qu'on annonce ----
    def _envoyer(self, dt):
        # ce qu'on a construit ou démoli part tout de suite : c'est rare et ça se voit
        tuiles = self.partie.game_map.prendre_changements()
        if tuiles:
            self.connexion.envoyer({"t": protocole.TUILES, "l": tuiles})

        self._depuis_mouvement += dt
        if self._depuis_mouvement < 1.0 / protocole.HERTZ_INSTANTANE:
            return
        self._depuis_mouvement = 0.0
        moi = self.partie.moi
        self.connexion.envoyer({
            "t": protocole.MOUVEMENT,
            "x": round(moi.hero.x, 1), "y": round(moi.hero.y, 1),
            "d": moi.hero.direction, "a": moi.hero.action, "n": moi.hero.numero_image,
            "pi": self.partie.engins.index(moi.pilote) if moi.pilote is not None else -1,
            # notre zoom : avec lui, l'hôte sait quelle largeur de monde on a sous les yeux et
            # ne nous prive pas de ce qu'on voit quand on dézoome (voir MARGE_INTERET)
            "z": round(moi.camera.zoom, 3),
        })

    def signaler_structures(self, cible=None):
        """Envoie à l'hôte le conteneur qu'on vient de modifier (`cible`), et garde notre version
        un court instant le temps que ça nous revienne (voir monde/partie.py).

        On n'envoie que celui-là : lui renvoyer tout le monde écraserait chez lui ce que les autres
        joueurs ont fait pendant la demi-seconde écoulée. Sans `cible` (ou pour un conteneur qui ne
        voyage pas encore, comme ceux posés sur une planète), on n'envoie rien."""
        cle = self.partie.verrouiller(cible)
        if cle is None:
            return
        donnees = self.partie.exporter_structures(
            lambda cases: [None if objet is None else self.ids[objet] for objet in cases], {cle})
        self.connexion.envoyer({"t": protocole.STRUCTURES_CLIENT, "d": donnees})

    def fermer(self):
        self.connexion.envoyer({"t": protocole.AU_REVOIR})
        self.connexion.fermer()


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
