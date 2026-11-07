import time

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reseau import protocole
from reseau.transport import PORT_DEFAUT, Salon, adresse_locale
from systeme import sauvegarde

# =============================================
# ==== L'hôte : il héberge la partie ET y joue (modèle non dédié, comme ARK).
# ====
# ==== Une fois par image, `tourner(dt)` fait trois choses : accueillir ceux qui arrivent,
# ==== lire ce que les autres annoncent, et renvoyer à chacun ce qu'il doit savoir.
# ==== Rien ne bloque : tout passe par les files de transport.py.
# =============================================


class Hote:
    """Côté hôte d'une partie en réseau. `partie` est la Partie en cours ; `exporter_monde`
    renvoie le monde entier (ce que la sauvegarde écrit) pour l'envoyer à un nouvel arrivant."""

    hote = True

    def __init__(self, partie, exporter_monde, ids, depart, port=PORT_DEFAUT):
        self.partie = partie
        self.exporter_monde = exporter_monde
        self.ids = ids                      # sauvegarde.ids_objets : objets -> identifiants texte
        self.objets = sauvegarde.objets_par_id()
        self.depart = depart                # où apparaît un joueur qui n'a jamais joué ici
        self.salon = Salon(port)
        self.port = self.salon.port
        self.adresse = adresse_locale()
        self.en_attente = []                # connectés, pas encore présentés (pas de BONJOUR)
        self.refus_en_attente = []           # refusés : on garde la socket ouverte pour livrer REFUS
        self.messages = []                  # nouvelles à afficher au joueur ("Bob est arrivé")
        self.disparus = []                  # conteneurs démolis par un client : le jeu referme
        self._depuis_instantane = 0.0       # les panneaux ouverts dessus
        self._depuis_structures = 0.0

    # ---- boucle ----
    def tourner(self, dt):
        self._accueillir()
        self._recevoir()
        self._diffuser(dt)

    def connectes(self):
        return [j for j in self.partie.joueurs if j.connexion is not None]

    def _dire(self, texte):
        self.messages.append(texte)

    # ---- arrivées ----
    def _accueillir(self):
        maintenant = time.monotonic()
        for connexion, expiration in list(self.refus_en_attente):
            if not connexion.vivante or maintenant >= expiration:
                connexion.fermer()
                self.refus_en_attente.remove((connexion, expiration))
        self.en_attente.extend(self.salon.nouvelles())
        for connexion in list(self.en_attente):
            if not connexion.vivante:
                self.en_attente.remove(connexion)
                continue
            for message in connexion.messages():
                if message.get("t") != protocole.BONJOUR:
                    continue  # on n'écoute rien d'autre tant qu'il ne s'est pas présenté
                self.en_attente.remove(connexion)
                self._presenter(connexion, message)
                break

    def _presenter(self, connexion, message):
        """Un nouveau venu s'annonce : on vérifie, on lui fabrique un joueur, on lui envoie le monde."""
        if message.get("version") != protocole.VERSION:
            self._refuser(connexion, "Ce n'est pas la même version du jeu des deux côtés.")
            return

        if len(self.connectes()) + 2 > protocole.JOUEURS_MAX:  # les connectés, l'hôte, et le nouveau
            self._refuser(connexion, "La partie est pleine.")
            return

        pseudo = str(message.get("pseudo") or "Joueur")[:24]
        # Il revient peut-être alors qu'on croit encore l'ancienne session en vie (coupure brutale,
        # ou déconnexion / reconnexion assez rapide pour tomber dans la même image). On ferme la
        # session fantôme d'abord : sans ça, `accueillir` lui ferait un héros tout neuf au point de
        # départ, et il réapparaîtrait dans le vide sans son vaisseau ni ses affaires.
        fantome = self.partie.par_pseudo(pseudo)
        if fantome is not None and fantome is not self.partie.moi and fantome.connexion is not None:
            self._congedier(fantome)
        joueur = self.partie.accueillir(pseudo, self.depart)
        joueur.connexion = connexion
        joueur.derniere_nouvelle = time.monotonic()
        connexion.envoyer({"t": protocole.BIENVENUE, "id": joueur.id,
                           "monde": self.exporter_monde()})
        self._dire(f"{joueur.pseudo} a rejoint la partie")

    def _refuser(self, connexion, raison):
        connexion.envoyer({"t": protocole.REFUS, "raison": raison})
        self.refus_en_attente.append((connexion, time.monotonic() + 5.0))

    # ---- ce que les joueurs annoncent ----
    def _recevoir(self):
        maintenant = time.monotonic()
        transmettre = []  # [(expéditeur, tuiles)] : à faire suivre aux autres
        for joueur in self.connectes():
            connexion = joueur.connexion
            recus = connexion.messages()
            if recus:
                joueur.derniere_nouvelle = maintenant
            for message in recus:
                type_message = message.get("t")
                if type_message == protocole.MOUVEMENT:
                    self._appliquer_mouvement(joueur, message)
                elif type_message == protocole.TUILES:
                    tuiles = message.get("l") or []
                    self.partie.game_map.appliquer_changements(tuiles)
                    self.disparus += self.partie.scanner_structures(supprimer_absents=True)
                    transmettre.append((joueur, tuiles))
                elif type_message == protocole.STRUCTURES_CLIENT:
                    self.partie.appliquer_inventaires(message.get("d"), self.objets)
                elif type_message == protocole.AU_REVOIR:
                    connexion.fermer()
            if not connexion.vivante or maintenant - joueur.derniere_nouvelle > protocole.DELAI_SILENCE:
                self._congedier(joueur)

        for expediteur, tuiles in transmettre:
            for autre in self.connectes():
                if autre is not expediteur:
                    autre.connexion.envoyer({"t": protocole.TUILES, "l": tuiles})

    def _appliquer_mouvement(self, joueur, message):
        """Chaque joueur fait autorité sur sa propre position : on la recopie telle quelle.
        On refuse seulement les valeurs absurdes, qui ne viendraient pas d'un jeu en état de marche."""
        try:
            x, y = float(message["x"]), float(message["y"])
        except (KeyError, TypeError, ValueError):
            return
        if not (abs(x) < 1e9 and abs(y) < 1e9):
            return
        joueur.hero.x, joueur.hero.y = x, y
        # Sa caméra suit son héros : c'est elle qui dit ce qu'il peut voir, donc ce qu'on lui
        # envoie (voir protocole.dans_la_vue). Sans ça on continuerait à ne lui envoyer que ce qui
        # était visible de l'endroit où il s'est connecté — et plus rien dès qu'il s'en éloigne.
        camera = joueur.camera
        zoom = message.get("z")
        if isinstance(zoom, (int, float)) and not isinstance(zoom, bool):
            camera.zoom = max(camera.zoom_min, min(camera.zoom_max, float(zoom)))
        camera.x = x - camera.screen_width / 2
        camera.y = y - camera.screen_height / 2
        # direction / action / numéro d'image vont ensemble : c'est Hero qui les vérifie, sinon un
        # numéro d'image qui ne va pas avec la direction fait planter le dessin de ce joueur
        joueur.hero.regler_animation(message.get("a", joueur.hero.action),
                                     message.get("d", joueur.hero.direction),
                                     message.get("n", 0))
        pilote = message.get("pi", -1)
        joueur.pilote = self.partie.engins.par_index(pilote)
        if joueur.pilote is not None:
            joueur.pilote.x, joueur.pilote.y = x, y  # le vaisseau est là où est son pilote

    def _congedier(self, joueur):
        joueur.connexion.fermer()
        joueur.connexion = None
        self._dire(f"{joueur.pseudo} a quitté la partie")
        self.partie.absenter(joueur)

    # ---- ce que l'hôte renvoie ----
    def _diffuser(self, dt):
        clients = self.connectes()
        if not clients:
            self.partie.game_map.prendre_changements()  # personne à prévenir : on ne garde rien
            return

        tuiles = self.partie.game_map.prendre_changements()
        if tuiles:
            # ce que l'hôte a changé lui-même : construction, démolition, base poussée par
            # ses réacteurs, fondation détruite par un vaisseau ennemi
            for joueur in clients:
                joueur.connexion.envoyer({"t": protocole.TUILES, "l": tuiles})

        self._depuis_instantane += dt
        if self._depuis_instantane >= 1.0 / protocole.HERTZ_INSTANTANE:
            self._depuis_instantane = 0.0
            for joueur in clients:
                joueur.connexion.envoyer(self.partie.instantane(joueur))
                joueur.poussee[0] = joueur.poussee[1] = 0.0  # signalée : on repart de zéro

        self._depuis_structures += dt
        if self._depuis_structures >= 1.0 / protocole.HERTZ_STRUCTURES:
            self._depuis_structures = 0.0
            structures = self.partie.exporter_structures(self.ids)
            for joueur in clients:
                joueur.connexion.envoyer(structures)

    # ---- fin ----
    def fermer(self, raison="L'hôte a quitté la partie."):
        for joueur in self.connectes():
            joueur.connexion.envoyer({"t": protocole.FIN, "raison": raison})
            joueur.connexion.fermer()
            joueur.connexion = None
        for connexion in self.en_attente:
            connexion.fermer()
        for connexion, _ in self.refus_en_attente:
            connexion.fermer()
        self.salon.fermer()


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
