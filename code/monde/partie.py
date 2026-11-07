import time

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from joueur.joueur import Joueur
from reseau import protocole

# Secondes pendant lesquelles notre version d'un conteneur auquel on vient de toucher résiste à
# ce que l'hôte envoie. Il faut un aller-retour complet pour que notre changement lui parvienne et
# nous revienne : sans ce délai, son instantané (2 fois par seconde, préparé AVANT de nous avoir
# entendus) remet le conteneur comme il était, et l'objet qu'on vient de prendre se retrouve à la
# fois dans notre inventaire et dans le coffre.
DELAI_VERROU = 1.5

# Les seules directions qu'un boîtier peut donner aux réacteurs. Ce qui vient du réseau est
# comparé à cette liste : une autre valeur ferait planter le dessin du panneau de pilotage.
DIRECTIONS_REACTEURS = {(0, -1), (0, 1), (-1, 0), (1, 0)}

# =============================================
# ==== La partie : le monde partagé (la carte, les ennemis, ce qui est construit) et les
# ==== joueurs qui s'y trouvent. En solo il n'y a qu'un joueur et rien ne voyage ; en
# ==== multijoueur, c'est cet objet qui sait résumer le monde pour l'envoyer (`instantane`)
# ==== et appliquer ce qu'on reçoit (`appliquer_instantane`).
# ====
# ==== Ce qui est dans l'instantané est ce dont l'hôte fait autorité : les ennemis, les
# ==== jauges, les positions des autres joueurs. Ce qui n'y est pas se retrouve autrement :
# ==== la carte par les changements de tuiles (voir Map.prendre_changements) et le contenu
# ==== des conteneurs par le message STRUCTURES, plus rare.
# =============================================


class Partie:
    """Le monde et ses joueurs. `moi` est celui de cette machine."""

    def __init__(self, nom, game_map, joueurs, moi, engins, aliens, vaisseaux, trous_noirs,
                 coffres, robots, largeur, hauteur, plantes=None, tourelles=None):
        self.nom = nom
        self.game_map = game_map
        self.joueurs = joueurs
        self.moi = moi
        self.engins = engins
        self.aliens = aliens
        self.vaisseaux = vaisseaux
        self.trous_noirs = trous_noirs
        self.coffres = coffres
        self.robots = robots
        self.plantes = plantes
        self.tourelles = tourelles
        self.largeur = largeur
        self.hauteur = hauteur
        self._prochain_id = max((j.id for j in joueurs), default=0) + 1
        self.verrous = {}  # clé de conteneur -> jusqu'à quand notre version fait foi (voir DELAI_VERROU)

    # ---- conteneurs : à qui appartient la vérité, et pour combien de temps ----
    def cle_conteneur(self, objet):
        """Clé réseau d'un conteneur (coffre, réacteur, vaisseau, robot, plante, tourelle), ou None
        s'il ne voyage pas : une installation posée sur une planète, par exemple, n'est pas encore
        partagée entre les joueurs."""
        if objet is None:
            return None
        for i, vaisseau in enumerate(self.engins.liste):
            if objet is vaisseau or objet is vaisseau.coffre:
                return ("va", i)
        tx, ty = getattr(objet, "tx", None), getattr(objet, "ty", None)
        if tx is None or ty is None:
            return None
        tables = (("co", self.coffres.coffres), ("ro", self.robots.robots),
                  ("pl", None if self.plantes is None else self.plantes.plantes),
                  ("to", None if self.tourelles is None else self.tourelles.tourelles))
        for prefixe, table in tables:
            if table is not None and table.get((tx, ty)) is objet:
                return (prefixe, tx, ty)
        return None

    def verrouiller(self, objet):
        """On vient de toucher à ce conteneur : notre version l'emporte pendant DELAI_VERROU.
        Renvoie sa clé (None s'il ne voyage pas)."""
        cle = self.cle_conteneur(objet)
        if cle is not None:
            self.verrous[cle] = time.monotonic() + DELAI_VERROU
        return cle

    def _verrouille(self, cle):
        fin = self.verrous.get(cle)
        if fin is None:
            return False
        if time.monotonic() < fin:
            return True
        del self.verrous[cle]
        return False

    # ---- les joueurs ----
    def par_id(self, identifiant):
        return next((j for j in self.joueurs if j.id == identifiant), None)

    def par_pseudo(self, pseudo):
        return next((j for j in self.joueurs if j.pseudo == pseudo), None)

    def presents(self):
        """Les joueurs effectivement là (un déconnecté reste dans la partie pour la sauvegarde,
        mais il n'est plus dans le monde)."""
        return [j for j in self.joueurs if j.present]

    def accueillir(self, pseudo, depart):
        """Le joueur `pseudo` arrive. S'il a déjà joué dans ce monde (même pseudo), il retrouve son
        héros, ses affaires, le vaisseau qu'il pilotait et l'endroit où il s'était arrêté ; sinon on
        lui en crée de nouveaux à `depart`. Renvoie son Joueur.

        On le reconnaît même s'il est encore marqué « présent » : quand la connexion précédente est
        tombée sans prévenir, l'hôte peut ne pas l'avoir encore constaté (voir DELAI_SILENCE), et il
        ne faut surtout pas fabriquer un joueur tout neuf au point de départ — c'est ce qui faisait
        réapparaître dans le vide, sans vaisseau ni affaires, quand on se reconnectait vite."""
        ancien = self.par_pseudo(pseudo)
        if ancien is not None and ancien is not self.moi and ancien.connexion is None:
            ancien.present = True
            return ancien
        joueur = Joueur(pseudo, *depart, self.largeur, self.hauteur)
        joueur.id = self._prochain_id
        self._prochain_id += 1
        self.joueurs.append(joueur)
        return joueur

    def absenter(self, joueur):
        """Le joueur se déconnecte : son héros quitte le monde, mais il reste dans la partie
        pour être sauvegardé et retrouver ses affaires en revenant."""
        if joueur is not self.moi:
            joueur.present = False

    # ---- instantané : ce que l'hôte envoie 20 fois par seconde ----
    def _joueur_resume(self, joueur, pour):
        resume = {
            "i": joueur.id, "p": joueur.pseudo,
            "x": round(joueur.hero.x, 1), "y": round(joueur.hero.y, 1),
            "d": joueur.hero.direction, "a": joueur.hero.action, "n": joueur.hero.numero_image,
            "v": round(joueur.vie.value, 2), "o": round(joueur.oxygene.value, 2),
            "e": round(joueur.eau.value, 2), "f": round(joueur.faim.value, 2),
            "pi": self.engins.index(joueur.pilote) if joueur.pilote is not None else -1,
            "c": joueur.carte,
        }
        if joueur is pour and any(joueur.poussee):
            # seulement pour le destinataire : c'est lui qui doit l'appliquer à son héros
            resume["ps"] = [round(joueur.poussee[0], 2), round(joueur.poussee[1], 2)]
        return resume

    def instantane(self, pour):
        """Le monde vu par le joueur `pour` : tous les joueurs, et seulement les ennemis qu'il
        peut voir (au-delà, les lui envoyer serait du débit perdu — voir MARGE_INTERET)."""
        camera = pour.camera
        visible = lambda x, y: protocole.dans_la_vue(camera, x, y)
        return {
            "t": protocole.INSTANTANE,
            "j": [self._joueur_resume(j, pour) for j in self.presents()],
            "al": [[round(a.x, 1), round(a.y, 1), round(a.hp, 1)]
                   for a in self.aliens.liste if visible(a.x, a.y)],
            "ve": [[round(v.x, 1), round(v.y, 1), round(v.angle, 3)]
                   for v in self.vaisseaux.liste if visible(v.x, v.y)],
            "ti": [[round(t.x, 1), round(t.y, 1)]
                   for t in self.vaisseaux.tirs if visible(t.x, t.y)],
            "tn": [[round(n.x, 1), round(n.y, 1), round(n.vx, 1), round(n.vy, 1), round(n.angle, 1)]
                   for n in self.trous_noirs.liste if visible(n.x, n.y)],
            # Les robots bougent vite (600 px/s) : comme les aliens et les vaisseaux, leur
            # position voyage ici, 20 fois par seconde. Leur stock, lui, change rarement et reste
            # dans STRUCTURES. Les attendre tous les deux faisait sauter le robot de 300 pixels
            # d'un coup chez les autres joueurs. Repéré par la case de sa base.
            "ro": [[r.tx, r.ty, round(r.pos.x, 1), round(r.pos.y, 1), round(r.angle, 3)]
                   for r in self.robots.robots.values() if visible(r.pos.x, r.pos.y)],
        }

    def appliquer_instantane(self, donnees):
        """Côté client : on recopie ce que l'hôte dit du monde. Une seule chose lui échappe :
        la position de NOTRE héros, dont nous faisons autorité (on applique seulement la
        poussée qu'il nous signale)."""
        vus = set()
        for resume in donnees.get("j", []):
            vus.add(resume["i"])
            joueur = self.par_id(resume["i"])
            if joueur is None:
                joueur = Joueur(resume["p"], resume["x"], resume["y"], self.largeur, self.hauteur)
                joueur.id = resume["i"]
                self.joueurs.append(joueur)
            joueur.pseudo = resume["p"]
            joueur.present = True
            joueur.carte = resume.get("c")
            if joueur is self.moi:
                # notre position reste la nôtre ; seules les jauges et la poussée viennent de l'hôte
                poussee = resume.get("ps")
                if poussee:
                    joueur.hero.x += poussee[0]
                    joueur.hero.y += poussee[1]
            else:
                joueur.pilote = self.engins.par_index(resume.get("pi", -1))
                joueur.hero.x, joueur.hero.y = resume["x"], resume["y"]
                joueur.hero.regler_animation(resume.get("a"), resume.get("d"), resume.get("n", 0))
            joueur.vie.value = resume["v"]
            joueur.oxygene.value = resume["o"]
            joueur.eau.value = resume["e"]
            joueur.faim.value = resume["f"]
        for joueur in [j for j in self.joueurs if j.id not in vus and j is not self.moi]:
            self.joueurs.remove(joueur)

        # Les robots qu'on peut voir : on note où l'hôte les dit, ils s'y rendent tout seuls
        # (voir structures/robot.py). Ceux dont la base n'est pas encore arrivée avec les tuiles
        # sont ignorés : on les retrouvera au prochain instantané.
        for tx, ty, x, y, angle in donnees.get("ro", []):
            robot = self.robots.robots.get((tx, ty))
            if robot is not None:
                robot.viser(x, y, angle)

        self._appliquer_ennemis(donnees)

    def _appliquer_ennemis(self, donnees):
        """Les ennemis sont entièrement à l'hôte : on remplace les nôtres par les siens."""
        from ennemis.alien import Alien
        from ennemis.trou_noir import TrouNoir
        from ennemis.vaisseau import Tir, Vaisseau

        self.aliens.liste = []
        for x, y, hp in donnees.get("al", []):
            alien = Alien(x, y)
            alien.hp = hp
            self.aliens.liste.append(alien)

        self.vaisseaux.liste = []
        for x, y, angle in donnees.get("ve", []):
            vaisseau = Vaisseau(x, y)
            vaisseau.angle = angle
            self.vaisseaux.liste.append(vaisseau)
        # (les tirs ne servent qu'à être dessinés : leur direction n'a pas à voyager)
        self.vaisseaux.tirs = [Tir(x, y, 0.0) for x, y in donnees.get("ti", [])]

        image = self.trous_noirs.image()
        self.trous_noirs.liste = []
        for x, y, vx, vy, angle in donnees.get("tn", []):
            trou = TrouNoir(x, y, vx, vy, image)
            trou.angle = angle
            self.trous_noirs.liste.append(trou)

    # ---- structures : plus lourd, donc envoyé plus rarement ----
    def exporter_structures(self, ids, cibles=None):
        """Contenu des conteneurs, vaisseaux posés et robots : ce qui change moins souvent que
        les positions, mais qu'il faut quand même partager (un four qui cuit, un coffre qu'on
        remplit, un vaisseau qu'on pose).

        `cibles` : ensemble de clés (voir cle_conteneur) à inclure, le reste étant laissé de côté.
        Un client s'en sert pour n'annoncer QUE le conteneur auquel il vient de toucher : renvoyer
        tout le monde écraserait chez l'hôte ce que les autres joueurs ont fait pendant ce temps.
        Les vaisseaux gardent leur place dans la liste (les autres valent None) : c'est elle qui
        les identifie."""
        def garder(prefixe, entrees):
            if cibles is None:
                return entrees
            return [d for d in entrees if (prefixe, d.get("tx"), d.get("ty")) in cibles]

        vaisseaux = self.engins.exporter(ids)
        if cibles is not None:
            vaisseaux = {"liste": [d if ("va", i) in cibles else None
                                   for i, d in enumerate(vaisseaux["liste"])]}
        return {
            "t": protocole.STRUCTURES,
            "co": garder("co", [{"tx": c.tx, "ty": c.ty, "ty_pe": c.construction.__name__,
                                 "o": ids(c.objets), "n": list(c.nombres), "r": c.reserve,
                                 "m": c.marche, "di": list(c.direction), "fr": c.frequence,
                                 "pr": getattr(c, "progres", 0.0)}
                                for c in self.coffres.coffres.values()]),
            "va": vaisseaux,
            "ro": garder("ro", [{"tx": r.tx, "ty": r.ty, "x": round(r.pos.x, 1), "y": round(r.pos.y, 1),
                                 "a": round(r.angle, 3), "s": {res.nom: n for res, n in r.stock.items() if n}}
                                for r in self.robots.robots.values()]),
            "pl": [] if self.plantes is None else garder("pl", [
                {"tx": p.tx, "ty": p.ty, "s": {res.nom: n for res, n in p.stock.items()}}
                for p in self.plantes.plantes.values()]),
            "to": [] if self.tourelles is None else garder("to", self.tourelles.exporter()),
        }

    def scanner_structures(self, supprimer_absents=False):
        """Crée les structures dont les tuiles viennent d'arriver du réseau. Renvoie les conteneurs
        qui ont disparu au passage (tuile démolie par quelqu'un d'autre), pour que le jeu referme
        les panneaux d'inventaire ouverts dessus."""
        disparus = self.coffres.scan(self.game_map, supprimer_absents=supprimer_absents)
        self.robots.scan(self.game_map)
        if self.plantes is not None:
            self.plantes.scan(self.game_map)
        if self.tourelles is not None:
            self.tourelles.scan(self.game_map)
        return disparus

    def appliquer_inventaires(self, donnees, objets):
        """Applique les inventaires envoyés par un client sans remplacer les objets en place."""
        if not isinstance(donnees, dict):
            return

        for data in donnees.get("co", []):
            tx, ty = data.get("tx"), data.get("ty")
            if type(tx) is not int or type(ty) is not int:
                continue
            coffre = self.coffres.coffres.get((tx, ty))
            if coffre is None:
                continue
            objets_ids, nombres = data.get("o"), data.get("n")
            if not isinstance(objets_ids, list) or not isinstance(nombres, list):
                continue
            if len(objets_ids) != len(coffre.objets) or len(nombres) != len(coffre.nombres):
                continue
            nouveaux = [None if identifiant is None else objets.get(identifiant)
                        for identifiant in objets_ids]
            if any(identifiant is not None and objet is None
                   for identifiant, objet in zip(objets_ids, nouveaux)):
                continue
            if any(type(n) is not int or n < 0 for n in nombres):
                continue
            coffre.objets[:] = nouveaux
            coffre.nombres[:] = nombres
            # Les réglages d'un boîtier (marche/arrêt et direction des réacteurs, fréquence du
            # télescope piloté) appartiennent au conteneur au même titre que son contenu : sans ça,
            # un client qui clique les flèches gauche / droite voit son choix écrasé par l'hôte.
            if type(data.get("m")) is bool:
                coffre.marche = data["m"]
            direction = data.get("di")
            if isinstance(direction, list) and tuple(direction) in DIRECTIONS_REACTEURS:
                coffre.direction = tuple(direction)
            frequence = data.get("fr")
            if isinstance(frequence, (int, float)) and not isinstance(frequence, bool):
                coffre.frequence = float(frequence)

        vaisseaux = donnees.get("va", {}).get("liste", [])
        if isinstance(vaisseaux, list):
            for vaisseau, data in zip(self.engins.liste, vaisseaux):
                if not isinstance(data, dict):
                    continue  # (envoi ciblé : les vaisseaux non concernés valent None)
                objets_ids, nombres = data.get("objets"), data.get("nombres")
                if not isinstance(objets_ids, list) or not isinstance(nombres, list):
                    continue
                if len(objets_ids) != len(vaisseau.coffre.objets) or len(nombres) != len(vaisseau.coffre.nombres):
                    continue
                nouveaux = [None if identifiant is None else objets.get(identifiant)
                            for identifiant in objets_ids]
                reserves = data.get("reserves", vaisseau.reserves)
                if any(identifiant is not None and objet is None
                       for identifiant, objet in zip(objets_ids, nouveaux)):
                    continue
                if any(type(n) is not int or n < 0 for n in nombres):
                    continue
                if not isinstance(reserves, list) or len(reserves) != len(vaisseau.reserves):
                    continue
                if any(not isinstance(r, (int, float)) or r < 0 for r in reserves):
                    continue
                vaisseau.coffre.objets[:] = nouveaux
                vaisseau.coffre.nombres[:] = nombres
                vaisseau.reserves[:] = reserves

        for data in donnees.get("ro", []):
            tx, ty = data.get("tx"), data.get("ty")
            if type(tx) is not int or type(ty) is not int:
                continue
            robot = self.robots.robots.get((tx, ty))
            stock = data.get("s")
            if robot is None or not isinstance(stock, dict):
                continue
            if any(type(n) is not int or n < 0 for n in stock.values()):
                continue
            for ressource in robot.stock:
                robot.stock[ressource] = stock.get(ressource.nom, 0)

        if self.plantes is not None:
            for data in donnees.get("pl", []):
                tx, ty = data.get("tx"), data.get("ty")
                if type(tx) is not int or type(ty) is not int:
                    continue
                plante = self.plantes.plantes.get((tx, ty))
                stock = data.get("s")
                if plante is None or not isinstance(stock, dict):
                    continue
                if any(type(n) is not int or n < 0 for n in stock.values()):
                    continue
                for ressource in plante.stock:
                    plante.stock[ressource] = stock.get(ressource.nom, 0)

        if self.tourelles is not None:
            for data in donnees.get("to", []):
                tx, ty, tirs = data.get("tx"), data.get("ty"), data.get("tirs")
                if type(tx) is not int or type(ty) is not int or type(tirs) is not int or tirs < 0:
                    continue
                tourelle = self.tourelles.tourelles.get((tx, ty))
                if tourelle is not None:
                    tourelle.tirs = tirs

    def appliquer_structures(self, donnees, objets, ressources_par_nom):
        """Côté client : on recopie le contenu des conteneurs, les vaisseaux et les robots.
        On met à jour les objets EN PLACE quand ils existent déjà, pour ne pas casser un
        panneau de coffre ouvert qui pointe dessus.

        Un conteneur auquel on vient de toucher est laissé tranquille le temps que notre
        changement fasse l'aller-retour (voir DELAI_VERROU) : sinon l'hôte, qui a préparé son envoi
        avant de nous entendre, le remettrait comme il était.

        Renvoie les conteneurs qui ont disparu du monde, pour refermer les panneaux ouverts dessus.
        """
        disparus = []
        presents = set()
        for d in donnees.get("co", []):
            case = (d["tx"], d["ty"])
            presents.add(case)
            if self._verrouille(("co", *case)):
                continue
            coffre = self.coffres.coffres.get(case)
            if coffre is None:
                construction = objets.get(d["ty_pe"])
                if construction is None:
                    continue
                coffre = self.coffres.ajouter(d["tx"], d["ty"], construction)
            coffre.objets[:] = [objets.get(i) for i in d["o"]]
            coffre.nombres[:] = d["n"]
            coffre.reserve = d["r"]
            coffre.marche = d["m"]
            coffre.direction = tuple(d["di"])
            coffre.frequence = d["fr"]
            coffre.progres = d.get("pr", 0.0)
        for case in [c for c in self.coffres.coffres if c not in presents]:
            if self._verrouille(("co", *case)):
                continue  # posé à l'instant : l'hôte ne le connaît pas encore, on le garde
            disparus.append(self.coffres.coffres.pop(case))

        ignorer = {i for i in range(len(self.engins.liste)) if self._verrouille(("va", i))}
        self.engins.importer_reseau(donnees.get("va", {}), objets, ignorer)

        for d in donnees.get("ro", []):
            robot = self.robots.robots.get((d["tx"], d["ty"]))
            if robot is None or self._verrouille(("ro", d["tx"], d["ty"])):
                continue  # sa base arrivera avec les tuiles ; on le reverra au prochain envoi
            # (position : il s'y rend tout seul, voir Robot.suivre ; elle arrive aussi, et plus
            # souvent, dans l'instantané — ici c'est surtout pour les robots hors de la vue)
            robot.viser(d["x"], d["y"], d["a"])
            stock = d.get("s", {})
            for ressource in robot.stock:
                robot.stock[ressource] = stock.get(ressource.nom, 0)

        if self.plantes is not None:
            for data in donnees.get("pl", []):
                plante = self.plantes.plantes.get((data["tx"], data["ty"]))
                if plante is not None and not self._verrouille(("pl", data["tx"], data["ty"])):
                    stock = data.get("s", {})
                    for ressource in plante.stock:
                        plante.stock[ressource] = stock.get(ressource.nom, 0)

        if self.tourelles is not None:
            for data in donnees.get("to", []):
                tourelle = self.tourelles.tourelles.get((data["tx"], data["ty"]))
                if tourelle is not None and not self._verrouille(("to", data["tx"], data["ty"])):
                    tourelle.tirs = data["tirs"]
        return disparus


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
