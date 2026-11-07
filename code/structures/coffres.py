import math
import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structures.building import CONSTRUCTIONS, case_sous_souris, trouver_structure
from systeme import ecran
from construction import coffre as construction_coffre, epave
from systeme.ressources import BUTIN_EPAVE, BUTIN_RARE_EPAVE
from interface.radio_menu import F_MAX, F_MIN, PAS_FREQUENCE, nombre
from interface.ui import dessiner_bouton, dessiner_panneau
from structures.telescopes import DEMI_ANGLE_VUE, direction_vue
from joueur.inventory import (COLONNES, COULEUR_BORDURE, COULEUR_FOND, COULEUR_NUMERO,
                       COULEUR_SURVOL, ESPACE, HAUTEUR_TITRE, MARGE_PANNEAU, TAILLE_CASE,
                       Inventory)

COULEUR_BARRE_NUCLEAIRE = (90, 220, 110)  # jauge de la barre nucléaire qui brûle

# pilotage des réacteurs (boîtier avec une clé USB réacteurs)
HAUTEUR_PILOTAGE = 150     # place ajoutée sous les cases du boîtier
TAILLE_FLECHE = 40         # boutons de direction
ESPACE_FLECHE = 5
COULEUR_MARCHE = (40, 120, 60)
COULEUR_MARCHE_BORDURE = (110, 230, 130)
COULEUR_ARRET = (110, 40, 40)
COULEUR_ARRET_BORDURE = (230, 110, 110)
DIRECTIONS = {(0, -1): "haut", (0, 1): "bas", (-1, 0): "gauche", (1, 0): "droite"}

# pilotage d'un télescope (boîtier avec une clé USB satellite)
HAUTEUR_SATELLITE = 250    # place ajoutée sous les cases du boîtier
TAILLE_APERCU = 150        # côté de l'aperçu rond de l'angle du télescope
COULEUR_FOND_APERCU = (12, 16, 30)
COULEUR_RECEPTION = (140, 230, 160)
COULEUR_CONE = (140, 230, 160, 70)


def remplir_epave(coffre):
    """Le butin d'une navette échouée : processeurs et RAM, et très rarement des shards ou une clé USB."""
    for objet, (mini, maxi) in BUTIN_EPAVE.items():
        coffre.ajouter_objet(objet, random.randint(mini, maxi))
    for objet, (chance, mini, maxi) in BUTIN_RARE_EPAVE.items():
        if random.random() < chance:
            coffre.ajouter_objet(objet, random.randint(mini, maxi))


class Coffre:
    """Un conteneur posé (coffre : 25 cases, réacteur : 2 cases...) : chaque case a un
    objet et une quantité (mêmes règles de pile que l'inventaire du joueur).
    `construction` est son module de construction/ (TITRE, NB_CASES, ICONE...)."""

    def __init__(self, tx, ty, construction=construction_coffre):
        self.tx = tx
        self.ty = ty
        self.construction = construction
        self.objets = [None] * construction.NB_CASES
        self.nombres = [0] * construction.NB_CASES
        self.progres = 0.0  # secondes de cuisson de l'exemplaire en cours (four)
        self.reserve = 0.0  # oxygène (unités de jauge) déjà tiré de l'objet en cours (oxygénateur)
        self.marche = False        # boîtier avec clé USB réacteurs : les réacteurs de sa plateforme poussent
        self.direction = (0, -1)   # boîtier : par où ils poussent la plateforme (dx, dy) ; vers le haut
        self.frequence = 433.5     # boîtier avec clé USB satellite : fréquence du télescope piloté (MHz)
        self.pousse = False        # réacteur : il poussait à la dernière vérification (voir propulsion.py)

    def souffler(self, dt, manque):
        """Oxygénateur : rend au héros jusqu'à `manque` d'oxygène (au plus OXYGENE_PAR_SEC
        par seconde), en entamant un nouvel objet Oxygène quand la réserve est vide.
        Renvoie la quantité rendue."""
        c = self.construction
        rendu = min(c.OXYGENE_PAR_SEC * dt, manque)
        if rendu <= 0:
            return 0.0
        if self.reserve < rendu and self.objets[0] is not None:
            self.reserve += c.UNITES_PAR_OBJET
            self.nombres[0] -= 1
            if self.nombres[0] <= 0:
                self.objets[0], self.nombres[0] = None, 0
        rendu = min(rendu, self.reserve)
        self.reserve -= rendu
        return rendu

    def bruler(self, dt):
        """Réacteur nucléaire : la barre en cours brûle (reserve = secondes restantes) ; quand elle
        est finie, il en entame une nouvelle s'il en a. Renvoie True s'il produit de l'énergie."""
        if self.reserve <= 0 and self.objets[0] is not None:
            self.reserve += self.construction.DUREE_BARRE
            self.nombres[0] -= 1
            if self.nombres[0] <= 0:
                self.objets[0], self.nombres[0] = None, 0
        if self.reserve <= 0:
            return False
        self.reserve = max(0.0, self.reserve - dt)
        return True

    @property
    def alimente(self):
        """Réacteur nucléaire : True si une barre brûle (ou peut être entamée)."""
        return self.reserve > 0 or self.objets[0] is not None

    def peut_payer(self, cout):
        """Réacteur : True s'il reste assez de poussée en réserve, ou une paire oxygène + hydrogène à brûler."""
        return self.reserve >= cout or (self.objets[0] is not None and self.objets[1] is not None)

    def payer(self, cout):
        """Réacteur : dépense `cout` de poussée, en brûlant une paire oxygène + hydrogène quand la
        réserve ne suffit pas. Renvoie False (sans rien changer) s'il n'y a pas de quoi payer."""
        if not self.peut_payer(cout):
            return False
        if self.reserve < cout:
            for i in (0, 1):
                self.nombres[i] -= 1
                if self.nombres[i] <= 0:
                    self.objets[i], self.nombres[i] = None, 0
            self.reserve += self.construction.UNITES_PAR_OBJET
        self.reserve -= cout
        return True

    def cuire(self, dt):
        """Four : cuit un exemplaire d'une case d'entrée toutes les DELAI secondes et le range
        dans une case de sortie (la cuisson attend s'il n'y a plus de place pour le résultat)."""
        for i in self.construction.CASES_ENTREE:
            resultats = self.construction.RECETTES.get(self.objets[i])  # [(objet, quantité), ...]
            if resultats is not None and self._ranger_sortie(resultats, essai=True):
                self.progres += dt
                if self.progres >= self.construction.DELAI:
                    self.progres = 0.0
                    self._ranger_sortie(resultats)
                    self.nombres[i] -= 1
                    if self.nombres[i] <= 0:
                        self.objets[i], self.nombres[i] = None, 0
                return
        self.progres = 0.0

    def avancer_cuisson(self, dt):
        """Multijoueur, côté client : fait avancer la barre de cuisson entre deux nouvelles de
        l'hôte, sans jamais rien produire — c'est lui qui cuit pour de vrai, et qui dira quand
        l'exemplaire est sorti.

        Sans ça, la flèche du four n'avance que quand l'hôte parle, soit 2 fois par seconde pour
        une cuisson de 5 secondes : elle saute de 10 % en 10 % au lieu de glisser."""
        c = self.construction
        if not hasattr(c, "RECETTES"):
            return  # (pas un four)
        for i in c.CASES_ENTREE:
            resultats = c.RECETTES.get(self.objets[i])
            if resultats is not None and self._ranger_sortie(resultats, essai=True):
                self.progres = min(self.progres + dt, c.DELAI)
                return
        self.progres = 0.0  # plus rien à cuire (ou plus de place en sortie) : la barre retombe

    def _ranger_sortie(self, resultats, essai=False):
        """Range les résultats dans les cases de sortie. Avec essai=True, ne change rien et
        dit seulement s'il y a assez de place pour tout."""
        sorties = self.construction.CASES_SORTIE
        objets = {i: self.objets[i] for i in sorties}
        nombres = {i: self.nombres[i] for i in sorties}
        for objet, quantite in resultats:
            maxi = Inventory.pile_max(objet)
            for libre in (False, True):  # d'abord les piles de cet objet, puis les cases vides
                for i in sorties:
                    if quantite and (objets[i] is None) == libre and (libre or objets[i] is objet):
                        mis = min(quantite, maxi - nombres[i])
                        objets[i] = objet
                        nombres[i] += mis
                        quantite -= mis
            if quantite:
                return False
        if not essai:
            for i in sorties:
                self.objets[i], self.nombres[i] = objets[i], nombres[i]
        return True

    @property
    def titre(self):
        return self.construction.TITRE

    @property
    def vide(self):
        return all(objet is None for objet in self.objets)

    def ajouter_objet(self, objet, quantite=1):
        """Range la quantité dans les piles existantes puis les cases libres. Renvoie ce
        qui n'a pas pu rentrer (0 si tout est rangé)."""
        maxi = min(Inventory.pile_max(objet), getattr(self.construction, "PILE_MAX", Inventory.pile_max(objet)))
        # four : on ne range que dans l'entrée, les cases de sortie ne servent qu'à prendre
        permises = getattr(self.construction, "CASES_ENTREE", range(len(self.objets)))
        case_objet = getattr(self.construction, "CASE_OBJET", None)  # vaisseau : une case par carburant
        if case_objet is not None:
            if objet not in case_objet:
                return quantite
            permises = (case_objet[objet],)
        if objet not in getattr(self.construction, "ACCEPTE", (objet,)):
            return quantite  # oxygénateur : que de l'oxygène
        for i, case in enumerate(self.objets):
            if case is objet and quantite and i in permises:
                mis = min(quantite, maxi - self.nombres[i])
                self.nombres[i] += mis
                quantite -= mis
        for i, case in enumerate(self.objets):
            if case is None and quantite and i in permises:
                mis = min(quantite, maxi)
                self.objets[i] = objet
                self.nombres[i] = mis
                quantite -= mis
        return quantite


class Coffres:
    """Les conteneurs du monde : un `Coffre` par tuile de coffre ou de réacteur posée
    (la tuile est dessinée par la carte, comme les autres)."""

    def __init__(self):
        self.coffres = {}  # (tx, ty) -> Coffre
        self.zones = {}    # (tx, ty) d'une tuile de navette échouée -> (tx, ty) de son conteneur

    def _scan_epaves(self, game_map):
        """Une navette échouée (groupe de tuiles voisines du calque de epave) = un conteneur
        de butin, rangé sous la tuile en haut à gauche du groupe. Un conteneur déjà là (chargé
        d'une sauvegarde, peut-être déjà pillé) n'est pas recréé. Seules les tuiles du tileset
        des navettes comptent : les astéroïdes dessinés sur le même calque n'ont pas de butin."""
        taille = game_map.chunk_size
        navettes = game_map.gids_tileset(epave.TILESET)
        cases = {(cx * taille + x, cy * taille + y)
                 for (cx, cy), grille in game_map.layers.get(epave.CALQUE, {}).items()
                 for y, ligne in enumerate(grille) for x, valeur in enumerate(ligne) if valeur in navettes}
        self.zones.clear()
        vues = set()
        for depart in sorted(cases):  # tri : la même clé à chaque lancement
            if depart in vues:
                continue
            groupe, pile = [], [depart]
            vues.add(depart)
            while pile:
                x, y = pile.pop()
                groupe.append((x, y))
                for voisin in ((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    if voisin in cases and voisin not in vues:
                        vues.add(voisin)
                        pile.append(voisin)
            cle = min(groupe)
            for case in groupe:
                self.zones[case] = cle
            if cle not in self.coffres:
                remplir_epave(self.ajouter(*cle, epave))
        # conteneurs d'épave qui ne sont plus sur une navette (ex : astéroïdes pris pour des
        # navettes dans les anciennes sauvegardes) : on les retire. Ceux des navettes générées par
        # la graine (absentes de self.zones) restent : leur case du coin est bien une navette.
        valides = set(self.zones.values())
        for cle in [cle for cle, coffre in self.coffres.items()
                    if coffre.construction is epave and cle not in valides
                    and self._coin_navette(game_map, cle) != cle]:
            del self.coffres[cle]

    @staticmethod
    def _coin_navette(game_map, case):
        """Case du coin haut gauche de la navette (5x5) qui couvre `case`, ou None s'il n'y en a pas.
        Une navette reprend la navette du tileset : sa tuile dit où elle est dans la navette."""
        navettes = game_map.gids_tileset(epave.TILESET)
        if not navettes:
            return None  # (carte d'une planète : pas de navettes, ni de calque des épaves)
        gid = game_map.get_layer_gid(epave.CALQUE, *case)
        if gid not in navettes:
            return None
        ligne, colonne = divmod(gid - navettes.start, game_map.colonnes_tileset(epave.TILESET))
        return case[0] - colonne, case[1] - ligne

    def _navette_generee(self, game_map, case):
        """Conteneur de la navette générée par la graine qui couvre `case` (créé avec son butin au
        premier clic), ou None s'il n'y a pas de navette là."""
        cle = self._coin_navette(game_map, case)
        if cle is None:
            return None
        if cle not in self.coffres:
            remplir_epave(self.ajouter(*cle, epave))
        return self.coffres[cle]

    def scan(self, game_map, supprimer_absents=False):
        """Crée un conteneur vide pour chaque tuile de coffre / réacteur de la carte qui
        n'en a pas encore (ceux dessinés directement dans la carte, par exemple), et un
        conteneur de butin pour chaque navette échouée. `supprimer_absents` sert à réconcilier
        la carte de l'hôte après les tuiles reçues d'un client.

        Renvoie les conteneurs supprimés, pour que le jeu referme les panneaux ouverts dessus."""
        self._scan_epaves(game_map)
        taille = game_map.chunk_size
        trouves = set()
        for construction in CONSTRUCTIONS:
            if not getattr(construction, "COFFRE", False):
                continue
            gid = construction.TUILES[0][2]
            for (cx, cy), grille in game_map.layers[construction.CALQUE].items():
                for y, ligne in enumerate(grille):
                    for x, valeur in enumerate(ligne):
                        if valeur == gid:
                            cle = (cx * taille + x, cy * taille + y)
                            trouves.add(cle)
                            if cle not in self.coffres:
                                self.ajouter(*cle, construction)
        disparus = []
        if supprimer_absents:
            for cle, coffre in list(self.coffres.items()):
                if coffre.construction is not epave and cle not in trouves:
                    disparus.append(self.coffres.pop(cle))
        return disparus

    def update(self, dt, manque_oxygene=0.0):
        """Les fours posés cuisent ; les réacteurs nucléaires brûlent leurs barres ; les oxygénateurs
        rendent de l'oxygène au héros, qui en manque `manque_oxygene`. Renvoie l'oxygène rendu."""
        rendu = 0.0
        for coffre in self.coffres.values():
            if hasattr(coffre.construction, "RECETTES"):
                coffre.cuire(dt)
            elif hasattr(coffre.construction, "DUREE_BARRE"):
                coffre.bruler(dt)
            elif hasattr(coffre.construction, "OXYGENE_PAR_SEC"):
                rendu += coffre.souffler(dt, manque_oxygene - rendu)
        return rendu

    def avancer_cuisson(self, dt):
        """Multijoueur, côté client : à appeler à chaque image à la place d'update (c'est l'hôte
        qui cuit ; nous, on ne fait qu'animer la flèche). Voir Coffre.avancer_cuisson."""
        for coffre in self.coffres.values():
            coffre.avancer_cuisson(dt)

    def ajouter(self, tx, ty, construction=construction_coffre):
        self.coffres[(tx, ty)] = Coffre(tx, ty, construction)
        return self.coffres[(tx, ty)]

    def deplacer(self, trajet):
        """La base a bougé : {ancienne case: nouvelle case}."""
        anciens = self.coffres
        self.coffres = {}
        for cle, coffre in anciens.items():
            coffre.tx, coffre.ty = trajet.get(cle, cle)
            self.coffres[(coffre.tx, coffre.ty)] = coffre

    def retirer(self, tx, ty):
        """Renvoie le conteneur retiré (ou None)."""
        return self.coffres.pop((tx, ty), None)

    def est_vide(self, tx, ty):
        coffre = self.coffres.get((tx, ty))
        return coffre is None or coffre.vide

    def sous_souris(self, game_map, camera, pos_vue):
        """Le conteneur sur la case sous la souris (ou None). Pour une construction de
        plusieurs tuiles (réacteur nucléaire 2x2), n'importe laquelle de ses cases compte."""
        case = case_sous_souris(game_map, camera, pos_vue)
        coffre = self.coffres.get(self.zones.get(case, case))
        if coffre is None:
            structure = trouver_structure(game_map, *case)
            if structure is not None and getattr(structure[0], "COFFRE", False):
                coffre = self.coffres.get(structure[1])
        if coffre is None and case not in self.zones:
            coffre = self._navette_generee(game_map, case)  # (navette tirée de la graine)
        return coffre


class PanneauCoffre:
    """Panneau du conteneur ouvert (à gauche de l'inventaire, qui s'ouvre avec lui).
    Clic gauche sur une case du coffre : prend la pile. Clic droit sur une case de
    l'inventaire (barre ou grille) : la range dans le coffre."""

    def __init__(self):
        self.ouvert = None  # conteneur ouvert
        self.panneau = pygame.Rect(0, 0, 0, 0)
        self.rects = []
        self.fleche = None  # four : zone de la flèche / barre de cuisson
        self.fleches = {}   # boîtier : direction (dx, dy) -> bouton (pilotage des réacteurs)
        self.bouton_marche = None
        self.boutons_frequence = []  # boîtier avec clé USB satellite : [(rect, pas en MHz, nom)]
        self.boutons_angle = []      # [(rect, sens (-1, 1) ou 0 = Auto, nom)]
        self.apercu = None           # zone de l'aperçu de l'angle du télescope
        self.mode = None             # commandes affichées : "reacteurs", "satellite" ou None (voir _mode)
        self.telescopes = None       # les télescopes (donnés par le jeu) : pilotés par un boîtier
        self._image_apercu = None
        self.police_titre = pygame.font.Font(None, 36)
        self.police_bouton = pygame.font.Font(None, 30)
        self.police = pygame.font.Font(None, 22)

    # ---- ouverture / fermeture ----
    def ouvrir(self, coffre, inventaire):
        self.ouvert = coffre
        inventaire.ouvert = True  # pour pouvoir y ranger / reprendre des objets

        nombre = len(coffre.objets)
        colonnes = min(COLONNES, nombre)
        lignes = -(-nombre // colonnes)
        largeur_panneau = COLONNES * TAILLE_CASE + (COLONNES - 1) * ESPACE  # toujours 5 colonnes de large
        largeur = colonnes * TAILLE_CASE + (colonnes - 1) * ESPACE
        hauteur = lignes * TAILLE_CASE + (lignes - 1) * ESPACE
        self.panneau = pygame.Rect(0, 0, largeur_panneau + 2 * MARGE_PANNEAU,
                                   hauteur + 2 * MARGE_PANNEAU + HAUTEUR_TITRE)
        self.panneau.midright = (inventaire.panneau.left - 30, inventaire.panneau.centery)
        gx = self.panneau.centerx - largeur // 2  # cases centrées dans le panneau
        gy = self.panneau.y + MARGE_PANNEAU + HAUTEUR_TITRE
        self.rects = [pygame.Rect(gx + (i % colonnes) * (TAILLE_CASE + ESPACE),
                                  gy + (i // colonnes) * (TAILLE_CASE + ESPACE),
                                  TAILLE_CASE, TAILLE_CASE)
                      for i in range(nombre)]
        if hasattr(coffre.construction, "RECETTES"):
            # four : une case d'entrée, une flèche (avec la barre de cuisson) et deux cases de sortie
            self.panneau.height = 2 * MARGE_PANNEAU + HAUTEUR_TITRE + TAILLE_CASE
            self.panneau.midright = (inventaire.panneau.left - 30, inventaire.panneau.centery)
            y = self.panneau.y + MARGE_PANNEAU + HAUTEUR_TITRE
            entree, sortie1, sortie2 = coffre.construction.CASES_ENTREE[0], *coffre.construction.CASES_SORTIE
            x = self.panneau.x + MARGE_PANNEAU
            self.rects[entree] = pygame.Rect(x, y, TAILLE_CASE, TAILLE_CASE)
            self.rects[sortie2] = pygame.Rect(self.panneau.right - MARGE_PANNEAU - TAILLE_CASE, y, TAILLE_CASE, TAILLE_CASE)
            self.rects[sortie1] = self.rects[sortie2].move(-(TAILLE_CASE + ESPACE), 0)
            self.fleche = pygame.Rect(self.rects[entree].right + 12, y + TAILLE_CASE // 2 - 22,
                                      self.rects[sortie1].left - self.rects[entree].right - 24, 44)
        elif hasattr(coffre.construction, "OXYGENE_PAR_SEC") or hasattr(coffre.construction, "DUREE_BARRE"):
            # oxygénateur / réacteur nucléaire : une case et la jauge de ce qu'il reste
            self.panneau.height = 2 * MARGE_PANNEAU + HAUTEUR_TITRE + TAILLE_CASE
            self.panneau.midright = (inventaire.panneau.left - 30, inventaire.panneau.centery)
            y = self.panneau.y + MARGE_PANNEAU + HAUTEUR_TITRE
            self.rects[0] = pygame.Rect(self.panneau.x + MARGE_PANNEAU, y, TAILLE_CASE, TAILLE_CASE)
            self.fleche = pygame.Rect(self.rects[0].right + 16, y + TAILLE_CASE // 2 - 14,
                                      self.panneau.right - MARGE_PANNEAU - self.rects[0].right - 16, 28)
        else:
            self.fleche = None

        self.fleches = {}
        self.bouton_marche = None
        self.boutons_frequence = []
        self.boutons_angle = []
        self.apercu = None
        self.mode = self._mode()
        if self.mode == "satellite":
            # boîtier avec processeur, RAM et clé USB satellite : la fréquence du télescope piloté, un
            # aperçu de son angle (et de ce qu'il voit) et les boutons pour le tourner
            self.panneau.height += HAUTEUR_SATELLITE
            self.panneau.midright = (inventaire.panneau.left - 30, inventaire.panneau.centery)
            for rect in self.rects:
                rect.y = self.panneau.y + MARGE_PANNEAU + HAUTEUR_TITRE
            x0 = self.panneau.x + MARGE_PANNEAU
            y0 = self.rects[0].bottom + 14
            largeur = self.panneau.width - 2 * MARGE_PANNEAU
            pas = (largeur + 6) / len(PAS_FREQUENCE)
            self.boutons_frequence = [(pygame.Rect(round(x0 + i * pas), y0 + 30, round(pas) - 6, 34), valeur, nom)
                                      for i, (valeur, nom) in enumerate(PAS_FREQUENCE)]
            self.apercu = pygame.Rect(x0, y0 + 78, TAILLE_APERCU, TAILLE_APERCU)
            gauche = self.apercu.right + 20
            largeur_bouton = (self.panneau.right - MARGE_PANNEAU - gauche - 2 * 8) // 3
            self.boutons_angle = [(pygame.Rect(gauche + i * (largeur_bouton + 8), self.apercu.bottom - 44,
                                               largeur_bouton, 44), action, nom)
                                  for i, (action, nom) in enumerate(((-1, "-15°"), (1, "+15°"), (0, "Auto")))]
        elif self.mode == "reacteurs":
            # boîtier avec processeur, RAM et clé USB réacteurs : sous ses cases, les commandes des
            # réacteurs (une croix de flèches et marche / arrêt) ; s'il en manque un, rien (voir draw)
            self.panneau.height += HAUTEUR_PILOTAGE
            self.panneau.midright = (inventaire.panneau.left - 30, inventaire.panneau.centery)
            for rect in self.rects:  # (le panneau a bougé en grandissant : les cases le suivent)
                rect.y = self.panneau.y + MARGE_PANNEAU + HAUTEUR_TITRE
            b, e = TAILLE_FLECHE, ESPACE_FLECHE
            x0 = self.panneau.x + MARGE_PANNEAU
            y0 = self.rects[0].bottom + 12
            self.fleches = {
                (0, -1): pygame.Rect(x0 + b + e, y0, b, b),
                (-1, 0): pygame.Rect(x0, y0 + b + e, b, b),
                (1, 0): pygame.Rect(x0 + 2 * (b + e), y0 + b + e, b, b),
                (0, 1): pygame.Rect(x0 + b + e, y0 + 2 * (b + e), b, b),
            }
            gauche = x0 + 3 * b + 2 * e + 30
            self.bouton_marche = pygame.Rect(gauche, y0 + b + e - 18, self.panneau.right - MARGE_PANNEAU - gauche, 56)

    def _mode(self):
        """Commandes à afficher sous les cases : "reacteurs" (boîtier avec processeur, RAM et clé USB
        réacteurs), "satellite" (... et clé USB satellite) ou None (rien : il manque une pièce)."""
        coffre = self.ouvert
        if coffre is None or not getattr(coffre.construction, "PILOTAGE", False):
            return None
        if coffre.construction.pilote_reacteurs(coffre):
            return "reacteurs"
        if coffre.construction.pilote_satellite(coffre) and self.telescopes is not None:
            return "satellite"
        return None

    def _telescope_capte(self):
        """Case du télescope réglé sur la fréquence du boîtier ouvert (mode satellite), ou None."""
        return self.telescopes.sur_frequence(self.ouvert.frequence)

    def fermer_si(self, coffre):
        """Ferme le panneau s'il montre ce conteneur (qui vient de disparaître)."""
        if self.ouvert is coffre:
            self.ouvert = None

    # ---- évènements ----
    def handle_event(self, event, inventaire):
        """Renvoie True si l'évènement est consommé (sinon l'inventaire le traite)."""
        if self.ouvert is None:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.ouvert = None
                inventaire.ouvert = False  # (Echap ne doit pas ouvrir la pause)
                return True
            if event.key == pygame.K_TAB:
                self.ouvert = None  # Tab ferme aussi l'inventaire (voir Inventory)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.panneau.collidepoint(event.pos):
                    for i, rect in enumerate(self.rects):
                        if rect.collidepoint(event.pos):
                            self._prendre(i, inventaire)
                    if self.mode == "reacteurs" and self._mode() == "reacteurs":
                        if self.bouton_marche.collidepoint(event.pos):
                            self.ouvert.marche = not self.ouvert.marche
                        for direction, rect in self.fleches.items():
                            if rect.collidepoint(event.pos):
                                self.ouvert.direction = direction
                    if self.mode == "satellite" and self._mode() == "satellite":
                        for rect, pas, _ in self.boutons_frequence:
                            if rect.collidepoint(event.pos):
                                self.ouvert.frequence = round(min(F_MAX, max(F_MIN, self.ouvert.frequence + pas)), 1)
                        capte = self._telescope_capte()
                        for rect, action, _ in self.boutons_angle:
                            if rect.collidepoint(event.pos) and capte is not None:
                                if action:
                                    self.telescopes.tourner(*capte, action)
                                else:
                                    self.telescopes.liberer(*capte)
                    return True
                if not inventaire.contient(event.pos):  # clic dans le vide : on referme
                    self.ouvert = None
                    inventaire.ouvert = False
                    return True
            elif event.button == 3:
                self._ranger(event.pos, inventaire)
                return True
        return False

    def _prendre(self, i, inventaire):
        coffre = self.ouvert
        if coffre.objets[i] is None:
            return
        reste = inventaire.ajouter_objet(coffre.objets[i], coffre.nombres[i])  # le reste (si plein) y demeure
        coffre.nombres[i] = reste
        if reste == 0:
            coffre.objets[i] = None

    def _ranger(self, pos, inventaire):
        """Clic droit sur une case de l'inventaire : sa pile va dans le coffre."""
        for cases, nombres, rects in ((inventaire.barre, inventaire.barre_nb, inventaire.rects),
                                      (inventaire.grille, inventaire.grille_nb,
                                       inventaire.rects_grille)):
            for i, rect in enumerate(rects):
                if rect.collidepoint(pos) and cases[i] is not None:
                    quantite = nombres[i] or 1  # (un outil compte pour 1)
                    reste = self.ouvert.ajouter_objet(cases[i], quantite)
                    nombres[i] = reste
                    if reste == 0:
                        cases[i] = None
                    return

    # ---- dessin ----
    def draw(self, screen, inventaire):
        if self.ouvert is None:
            return
        if self.mode != self._mode():
            self.ouvrir(self.ouvert, inventaire)  # pièce mise ou enlevée : le panneau s'agrandit / rétrécit
        dessiner_panneau(screen, self.panneau)
        titre = self.police_titre.render(self.ouvert.titre, True, COULEUR_NUMERO)
        screen.blit(titre, (self.panneau.x + MARGE_PANNEAU, self.panneau.y + MARGE_PANNEAU - 4))
        if self.fleche is None:  # (trop étroit pour le four et l'oxygénateur)
            aide = self.police.render("clic : prendre - clic droit (inventaire) : ranger",
                                      True, COULEUR_BORDURE)
            screen.blit(aide, aide.get_rect(bottomright=(self.panneau.right - MARGE_PANNEAU,
                                                         self.panneau.y + MARGE_PANNEAU + 28)))

        if self.fleche is not None and hasattr(self.ouvert.construction, "OXYGENE_PAR_SEC"):
            # oxygénateur : jauge de l'oxygène qu'il lui reste à rendre
            f = self.fleche
            plein = self.ouvert.reserve / self.ouvert.construction.UNITES_PAR_OBJET
            pygame.draw.rect(screen, COULEUR_FOND, f, border_radius=8)
            pygame.draw.rect(screen, COULEUR_SURVOL, (f.x, f.y, int(f.width * min(1.0, plein)), f.height),
                             border_radius=8)
            pygame.draw.rect(screen, COULEUR_BORDURE, f, 2, border_radius=8)
            texte = self.police.render("Oxygène restant", True, COULEUR_NUMERO)
            screen.blit(texte, texte.get_rect(center=f.center))
        elif self.fleche is not None and hasattr(self.ouvert.construction, "DUREE_BARRE"):
            # réacteur nucléaire : jauge de la barre en cours, avec le temps qu'il lui reste
            f = self.fleche
            reste = self.ouvert.reserve
            plein = reste / self.ouvert.construction.DUREE_BARRE
            pygame.draw.rect(screen, COULEUR_FOND, f, border_radius=8)
            pygame.draw.rect(screen, COULEUR_BARRE_NUCLEAIRE, (f.x, f.y, int(f.width * min(1.0, plein)), f.height),
                             border_radius=8)
            pygame.draw.rect(screen, COULEUR_BORDURE, f, 2, border_radius=8)
            etat = f"Barre : {int(reste) // 60}:{int(reste) % 60:02d}" if reste > 0 else "Aucune barre"
            texte = self.police.render(etat, True, COULEUR_NUMERO)
            screen.blit(texte, texte.get_rect(center=f.center))
        elif self.fleche is not None:
            f = self.fleche
            avancement = min(1.0, self.ouvert.progres / self.ouvert.construction.DELAI)
            corps = pygame.Rect(f.x, f.centery - 8, f.width - 18, 16)
            pygame.draw.rect(screen, COULEUR_FOND, corps, border_radius=6)
            pygame.draw.rect(screen, COULEUR_SURVOL, (corps.x, corps.y, int(corps.width * avancement), 16),
                             border_radius=6)
            pygame.draw.rect(screen, COULEUR_BORDURE, corps, 2, border_radius=6)
            pygame.draw.polygon(screen, COULEUR_SURVOL if avancement else COULEUR_BORDURE,
                                [(f.right - 20, f.centery - 18), (f.right, f.centery), (f.right - 20, f.centery + 18)])

        fond = pygame.Surface((TAILLE_CASE, TAILLE_CASE), pygame.SRCALPHA)
        fond.fill(COULEUR_FOND)
        souris = ecran.souris()
        for rect, objet, nombre in zip(self.rects, self.ouvert.objets, self.ouvert.nombres):
            survol = rect.collidepoint(souris)
            inventaire._dessiner_case(screen, rect, objet, nombre, fond,
                                      COULEUR_SURVOL if survol else COULEUR_BORDURE,
                                      3 if survol else 2)
        if self.mode == "reacteurs":
            self._dessiner_pilotage(screen, souris)
        elif self.mode == "satellite":
            self._dessiner_satellite(screen, souris)

    def _dessiner_satellite(self, screen, souris):
        """Boîtier qui pilote un télescope : sa fréquence, l'aperçu de son angle et de ce qu'il voit,
        et les boutons pour le tourner (ou le laisser tourner tout seul : Auto)."""
        coffre = self.ouvert
        x0 = self.panneau.x + MARGE_PANNEAU
        y0 = self.rects[0].bottom + 14
        texte = self.police_bouton.render(f"Télescope sur {nombre(coffre.frequence)} MHz", True, COULEUR_NUMERO)
        screen.blit(texte, (x0, y0))
        for rect, _, nom in self.boutons_frequence:
            dessiner_bouton(screen, self.police, rect, nom, rect.collidepoint(souris))

        capte = self._telescope_capte()
        zone = self.apercu
        centre, rayon = zone.center, zone.width // 2
        pygame.draw.circle(screen, COULEUR_FOND_APERCU, centre, rayon)
        pygame.draw.circle(screen, COULEUR_RECEPTION if capte else COULEUR_BORDURE, centre, rayon, 2)
        for i, lettre in enumerate("NESO"):  # les 4 directions (N en haut de l'écran)
            a = -math.pi / 2 + i * math.pi / 2
            image = self.police.render(lettre, True, COULEUR_BORDURE)
            screen.blit(image, image.get_rect(center=(centre[0] + math.cos(a) * (rayon - 11),
                                                      centre[1] + math.sin(a) * (rayon - 11))))
        gauche = zone.right + 20
        if capte is None:
            image = self.police.render("aucun signal", True, COULEUR_BORDURE)
            screen.blit(image, image.get_rect(center=centre))
            lignes = (("Aucun télescope", COULEUR_BORDURE), ("sur cette fréquence", COULEUR_BORDURE),
                      ("(clic sur un télescope :", COULEUR_BORDURE), ("voir sa fréquence)", COULEUR_BORDURE))
        else:
            angle = self.telescopes.angle(*capte)
            # le cône de ce qu'il voit (ce qui est découvert sur la grande carte), puis le télescope tourné
            vue = direction_vue(angle)
            cone = pygame.Surface(zone.size, pygame.SRCALPHA)
            c = (rayon, rayon)
            points = [c] + [(c[0] + math.cos(vue + k * DEMI_ANGLE_VUE / 4) * (rayon - 4),
                             c[1] + math.sin(vue + k * DEMI_ANGLE_VUE / 4) * (rayon - 4)) for k in range(-4, 5)]
            pygame.draw.polygon(cone, COULEUR_CONE, points)
            screen.blit(cone, zone)
            if self._image_apercu is None:
                self._image_apercu = pygame.transform.smoothscale(self.telescopes.image, (rayon, rayon))
            image = pygame.transform.rotozoom(self._image_apercu, -math.degrees(angle), 1)
            screen.blit(image, image.get_rect(center=centre))
            pilote = self.telescopes.pilote(*capte)
            lignes = (("Télescope capté", COULEUR_RECEPTION), (f"Angle : {round(math.degrees(angle)) % 360}°", COULEUR_NUMERO),
                      ("piloté" if pilote else "tourne tout seul", COULEUR_BORDURE),
                      (f"case {capte[0]}, {capte[1]}", COULEUR_BORDURE))
        for i, (ligne, couleur) in enumerate(lignes):
            police = self.police_bouton if i == 0 else self.police
            screen.blit(police.render(ligne, True, couleur), (gauche, zone.y + 2 + i * 24 + (6 if i else 0)))
        if capte is not None:
            for rect, _, nom in self.boutons_angle:
                dessiner_bouton(screen, self.police_bouton, rect, nom, rect.collidepoint(souris))

    def _dessiner_pilotage(self, screen, souris):
        """Boîtier qui pilote les réacteurs : la croix des directions et le bouton marche / arrêt."""
        coffre = self.ouvert
        for direction, rect in self.fleches.items():
            choisie = coffre.direction == direction
            survol = rect.collidepoint(souris)
            pygame.draw.rect(screen, COULEUR_SURVOL if choisie else COULEUR_FOND, rect, border_radius=8)
            pygame.draw.rect(screen, COULEUR_NUMERO if survol else COULEUR_BORDURE, rect, 2, border_radius=8)
            dx, dy = direction
            c = rect.center
            pointe = (c[0] + dx * 12, c[1] + dy * 12)
            base1 = (c[0] - dx * 8 - dy * 11, c[1] - dy * 8 - dx * 11)
            base2 = (c[0] - dx * 8 + dy * 11, c[1] - dy * 8 + dx * 11)
            couleur = (20, 25, 45) if choisie else COULEUR_NUMERO
            pygame.draw.polygon(screen, couleur, [pointe, base1, base2])

        b = self.bouton_marche
        fond, bordure = ((COULEUR_MARCHE, COULEUR_MARCHE_BORDURE) if coffre.marche
                         else (COULEUR_ARRET, COULEUR_ARRET_BORDURE))
        pygame.draw.rect(screen, fond, b, border_radius=14)
        pygame.draw.rect(screen, COULEUR_NUMERO if b.collidepoint(souris) else bordure, b, 3, border_radius=14)
        texte = self.police_bouton.render("Réacteurs : MARCHE" if coffre.marche else "Réacteurs : ARRÊT",
                                          True, COULEUR_NUMERO)
        screen.blit(texte, texte.get_rect(center=b.center))
        # (nom de la direction : le .get protège d'une valeur abîmée venue du réseau ou d'une
        # vieille sauvegarde — afficher « ? » vaut mieux que faire planter tout le jeu)
        aide = self.police.render(f"Direction : {DIRECTIONS.get(coffre.direction, '?')}   ·   clic : changer",
                                  True, COULEUR_BORDURE)
        screen.blit(aide, aide.get_rect(midtop=(b.centerx, b.bottom + 8)))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
