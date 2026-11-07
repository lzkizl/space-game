import math
import random
from functools import lru_cache

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import telescope
from systeme import ecran
from interface.radio_menu import F_MAX, F_MIN, PAS_FREQUENCE, PORTEE_NETTE, nombre
from interface.ui import (COULEUR_ACCENT, COULEUR_BORDURE, COULEUR_BOUTON, COULEUR_TEXTE_GRIS, COULEUR_TITRE,
                          dessiner_bouton, dessiner_panneau)
from structures.building import case_sous_souris, trouver_structure

GID_TELESCOPE = telescope.TUILES[0][2]  # tuile en haut à gauche du bloc 2x2
TAILLE_IMAGE = 256    # côté du télescope à l'écran (pixels monde) : 2 cases
DUREE_ROTATION = 6.0  # secondes pour tourner d'une direction à la suivante
PAUSE_MIN, PAUSE_MAX = 3.0, 8.0  # secondes pendant lesquelles il reste pointé au même endroit
NB_DIRECTIONS = 20    # directions tirées par télescope, parcourues en boucle
VITESSE_PILOTE = math.radians(40)  # piloté par un boîtier : vitesse de rotation (radians par seconde)
PAS_ANGLE = math.radians(15)       # un clic sur un bouton de rotation du boîtier
# ce que voit un télescope (découvert sur la grande carte) : un cône devant lui, qui s'allonge
# doucement tant qu'il reste pointé au même endroit (et repart de PORTEE_DEPART dès qu'il tourne)
PORTEE_DEPART = 15                 # longueur du cône dès qu'il regarde quelque part, en cases
VITESSE_VUE = 2.0                  # cases gagnées par seconde à regarder au même endroit
PORTEE_MAX = 15000000                 # longueur maxi du cône (atteinte après ~2 heures sans bouger)
DEMI_ANGLE_VUE = math.radians(8)   # demi-ouverture du cône
DELAI_VUE = 0.2                    # secondes entre deux découvertes
ANGLE_IMMOBILE = math.radians(1)   # s'il a tourné de plus que ça, il regarde ailleurs : la vue repart de près


@lru_cache(maxsize=64)
def _etapes(tx, ty):
    """([(direction, durée de la pause), ...], durée d'un cycle) du télescope posé en (tx, ty) :
    toujours les mêmes pour cette case."""
    tirage = random.Random(f"telescope:{tx}:{ty}")
    etapes = [(tirage.uniform(0, 2 * math.pi), tirage.uniform(PAUSE_MIN, PAUSE_MAX))
              for _ in range(NB_DIRECTIONS)]
    etapes.append(etapes[0])  # la dernière ramène à la première : la boucle ne saute pas
    return etapes, sum(DUREE_ROTATION + pause for _, pause in etapes[1:])


def _ecart(depart, arrivee):
    """Angle à tourner pour aller de `depart` à `arrivee`, par le plus court (dans [-pi, pi))."""
    return (arrivee - depart + math.pi) % (2 * math.pi) - math.pi


def direction_vue(angle):
    """Direction (radians, 0 = droite, y vers le bas) où regarde un télescope tourné de `angle` :
    sur l'image, son objectif est en haut."""
    return angle - math.pi / 2


class Telescopes:
    """Les télescopes posés : leurs tuiles sont transparentes (elles servent juste à savoir où ils
    sont) ; on dessine ici le télescope, qui tourne lentement vers des directions au hasard puis
    s'y arrête un moment. Il découvre la grande carte là où il regarde (un cône devant lui).
    Chacun émet un signal sur une fréquence qu'on choisit en cliquant dessus (voir PanneauTelescope).
    Un boîtier (PC) avec processeur, RAM et clé USB satellite, réglé sur cette fréquence, le pilote :
    on y voit son angle et on le change (voir coffres.PanneauCoffre)."""

    def __init__(self, game_map):
        self.game_map = game_map
        image = pygame.image.load(telescope.ICONE).convert_alpha()
        self.image = pygame.transform.smoothscale(image, (TAILLE_IMAGE, TAILLE_IMAGE))
        self.temps = 0.0
        # (tx, ty) -> {"frequence": MHz, "cible": angle voulu (piloté) ou None (au hasard),
        #              "angle": angle affiché quand il est piloté ou qu'il revient au hasard, sinon None}
        self.etats = {}
        self._attente_vue = 0.0
        # (tx, ty) -> {"angle": où il regarde, "portee": jusqu'où il voit (cases), "vue": jusqu'où c'est déjà découvert}
        self._vues = {}

    def reveler(self, dt, grande_carte):
        """Chaque télescope découvre sur la grande carte le cône qu'il regarde (toutes les DELAI_VUE
        secondes) : plus il reste pointé au même endroit, plus le cône est long."""
        self._attente_vue += dt
        if self._attente_vue < DELAI_VUE:
            return
        ecoule, self._attente_vue = self._attente_vue, 0.0
        for case in self.tous():
            angle = self.angle(*case)
            vue = self._vues.get(case)
            if vue is None or abs(_ecart(vue["angle"], angle)) >= ANGLE_IMMOBILE:
                vue = self._vues[case] = {"angle": angle, "portee": PORTEE_DEPART, "vue": 0}
            else:
                vue["portee"] = min(PORTEE_MAX, vue["portee"] + VITESSE_VUE * ecoule)
            portee = int(vue["portee"])
            # les planètes dans tout le cône sont vues (elles bougent : Mars peut y entrer plus tard)
            grande_carte.voir_planetes_cone(case[0] + 1, case[1] + 1, direction_vue(angle), DEMI_ANGLE_VUE, portee)
            if portee > vue["vue"]:   # on ne découvre que le bout de cône qui vient de s'ajouter
                grande_carte.decouvrir_cone(self.game_map.chunk_size, case[0] + 1, case[1] + 1, direction_vue(angle),
                                            DEMI_ANGLE_VUE, portee, depuis=vue["vue"] + 1)
                vue["vue"] = portee

    def portee(self, tx, ty):
        """Jusqu'où (en cases) le télescope voit en ce moment."""
        vue = self._vues.get((tx, ty))
        return int(vue["portee"]) if vue is not None else PORTEE_DEPART

    # ---- état de chaque télescope ----
    def etat(self, tx, ty):
        if (tx, ty) not in self.etats:
            frequence = round(random.Random(f"frequence:{tx}:{ty}").uniform(F_MIN + 5, F_MAX - 5), 1)
            self.etats[(tx, ty)] = {"frequence": frequence, "cible": None, "angle": None}
        return self.etats[(tx, ty)]

    def tous(self):
        """Cases (tx, ty) de tous les télescopes posés."""
        taille = self.game_map.chunk_size
        return [(cx * taille + lx, cy * taille + ly)
                for (cx, cy), grille in self.game_map.layers[telescope.CALQUE].items()
                if any(GID_TELESCOPE in ligne for ligne in grille)
                for ly, ligne in enumerate(grille) for lx, gid in enumerate(ligne) if gid == GID_TELESCOPE]

    def sur_frequence(self, frequence):
        """Case du télescope le mieux accordé sur cette fréquence (à PORTEE_NETTE près), ou None."""
        ecarts = [(abs(self.etat(*case)["frequence"] - frequence), case) for case in self.tous()]
        ecart, case = min(ecarts, default=(None, None))
        return case if ecart is not None and ecart <= PORTEE_NETTE else None

    def sous_souris(self, game_map, camera, pos_vue):
        """Case (tx, ty) du télescope sous la souris, ou None."""
        structure = trouver_structure(game_map, *case_sous_souris(game_map, camera, pos_vue))
        return structure[1] if structure is not None and structure[0] is telescope else None

    # ---- pilotage (boîtier avec une clé USB satellite) ----
    def tourner(self, tx, ty, sens):
        """Le télescope tourne d'un cran (sens = -1 ou 1), et ne tourne plus tout seul."""
        e = self.etat(tx, ty)
        if e["angle"] is None:
            e["angle"] = self._angle_auto(tx, ty)
        e["cible"] = (e["cible"] if e["cible"] is not None else e["angle"]) + sens * PAS_ANGLE

    def liberer(self, tx, ty):
        """Le télescope recommence à tourner tout seul (il rejoint doucement sa rotation au hasard)."""
        self.etat(tx, ty)["cible"] = None

    def pilote(self, tx, ty):
        return self.etat(tx, ty)["cible"] is not None

    def update(self, dt):
        self.temps += dt
        for (tx, ty), e in self.etats.items():
            if e["angle"] is None:
                continue
            cible = e["cible"] if e["cible"] is not None else self._angle_auto(tx, ty)
            ecart = _ecart(e["angle"], cible)
            pas = VITESSE_PILOTE * dt
            if abs(ecart) <= pas:
                e["angle"] = cible
                if e["cible"] is None:
                    e["angle"] = None  # il a rejoint sa rotation au hasard
            else:
                e["angle"] += pas if ecart > 0 else -pas

    def _angle_auto(self, tx, ty):
        """Angle de la rotation au hasard, en ce moment."""
        # chaque étape = tourner vers la direction suivante, puis attendre ; on retrouve l'étape
        # en cours en déroulant les étapes d'un cycle (décalé par télescope)
        etapes, duree_cycle = _etapes(tx, ty)
        cycle = len(etapes) - 1
        t = (self.temps + (tx * 7.3 + ty * 3.1)) % duree_cycle
        for k in range(cycle):
            depart, arrivee = etapes[k][0], etapes[k + 1][0]
            if t < DUREE_ROTATION:
                avance = t / DUREE_ROTATION
                avance = avance * avance * (3 - 2 * avance)  # démarre et s'arrête en douceur
                return depart + _ecart(depart, arrivee) * avance
            t -= DUREE_ROTATION
            if t < etapes[k + 1][1]:
                return arrivee
            t -= etapes[k + 1][1]
        return etapes[cycle][0]

    def angle(self, tx, ty):
        """Angle (radians) du télescope posé en (tx, ty) en ce moment."""
        e = self.etats.get((tx, ty))
        if e is not None and e["angle"] is not None:
            return e["angle"]
        return self._angle_auto(tx, ty)

    # ---- sauvegarde ----
    def exporter(self):
        return [{"tx": tx, "ty": ty, **e} for (tx, ty), e in self.etats.items()]

    def importer(self, donnees):
        self.etats = {(d["tx"], d["ty"]): {"frequence": d["frequence"], "cible": d["cible"], "angle": d["angle"]}
                      for d in donnees}

    # ---- dessin ----
    def draw_monde(self, vue, camera, game_map, propulsion=None):
        """Dessine les télescopes visibles (seuls les chunks à l'écran sont parcourus)."""
        taille = game_map.chunk_size
        pas_x, pas_y = taille * game_map.tilewidth, taille * game_map.tileheight
        cam_x, cam_y = camera.offset
        couches = game_map.layers[telescope.CALQUE]
        for cy in range(math.floor(cam_y / pas_y) - 1, math.floor((cam_y + camera.screen_height) / pas_y) + 1):
            for cx in range(math.floor(cam_x / pas_x) - 1, math.floor((cam_x + camera.screen_width) / pas_x) + 1):
                grille = couches.get((cx, cy))  # (un télescope posé rend toujours son chunk modifiable)
                if grille is None or not any(GID_TELESCOPE in ligne for ligne in grille):
                    continue
                for ly, ligne in enumerate(grille):
                    for lx, gid in enumerate(ligne):
                        if gid == GID_TELESCOPE:
                            self._dessiner(vue, camera.offset, game_map, propulsion, cx * taille + lx, cy * taille + ly)

    def _dessiner(self, vue, camera_offset, game_map, propulsion, tx, ty):
        offset = propulsion.offset_de(camera_offset, (tx, ty)) if propulsion else camera_offset
        centre = ((tx + 1) * game_map.tilewidth - offset[0], (ty + 1) * game_map.tileheight - offset[1])
        image = pygame.transform.rotozoom(self.image, -math.degrees(self.angle(tx, ty)), 1)
        vue.blit(image, image.get_rect(center=centre))


class PanneauTelescope:
    """Panneau ouvert par un clic sur un télescope : on y choisit la fréquence de son signal
    (boutons, curseur ou molette). Echap, Tab ou un clic dehors le ferment."""

    def __init__(self, screen_width, screen_height, telescopes):
        self.telescopes = telescopes
        self.ouvert = None   # case (tx, ty) du télescope ouvert
        self.glisse = False
        self.police_titre = pygame.font.Font(None, 60)
        self.police_grande = pygame.font.Font(None, 90)
        self.police = pygame.font.Font(None, 34)
        self.police_petite = pygame.font.Font(None, 27)
        self.panneau = pygame.Rect(0, 0, 640, 460)
        self.panneau.center = (screen_width // 2, screen_height // 2)
        x, y = self.panneau.x + 30, self.panneau.y
        self.boutons = [(pygame.Rect(x + i * 98, y + 205, 88, 46), pas, nom) for i, (pas, nom) in enumerate(PAS_FREQUENCE)]
        self.barre = pygame.Rect(x, y + 275, self.panneau.width - 60, 22)

    @property
    def frequence(self):
        return self.telescopes.etat(*self.ouvert)["frequence"]

    def regler(self, frequence):
        self.telescopes.etat(*self.ouvert)["frequence"] = round(min(F_MAX, max(F_MIN, frequence)), 1)

    def _regler_depuis_souris(self, x):
        self.regler(F_MIN + (x - self.barre.x) / self.barre.width * (F_MAX - F_MIN))

    def ouvrir(self, case, inventaire):
        self.ouvert = case
        inventaire.ouvert = False

    def fermer_si(self, case):
        """Ferme le panneau s'il montre ce télescope (qui vient d'être enlevé)."""
        if self.ouvert == case:
            self.ouvert = None

    def handle_event(self, event):
        """Ouvert, il absorbe les évènements. Renvoie True s'il est consommé."""
        if self.ouvert is None:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                self.ouvert = None  # Tab ouvre l'inventaire à la place
                return False
            if event.key == pygame.K_ESCAPE:
                self.ouvert = None  # (Echap ne doit pas ouvrir la pause)
            return True
        if event.type == pygame.MOUSEWHEEL:
            self.regler(self.frequence + event.y)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panneau.collidepoint(event.pos):
                self.ouvert = None
                return True
            for rect, pas, _ in self.boutons:
                if rect.collidepoint(event.pos):
                    self.regler(self.frequence + pas)
            if self.barre.inflate(0, 30).collidepoint(event.pos):
                self.glisse = True
                self._regler_depuis_souris(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.glisse:
            self._regler_depuis_souris(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.glisse:
            self.glisse = False
            return True
        return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)

    def draw(self, screen):
        if self.ouvert is None:
            return
        dessiner_panneau(screen, self.panneau)
        x, y = self.panneau.x + 30, self.panneau.y
        screen.blit(self.police_titre.render("Télescope NASA", True, COULEUR_TITRE), (x, y + 22))
        aide = self.police_petite.render("Echap pour fermer", True, COULEUR_TEXTE_GRIS)
        screen.blit(aide, aide.get_rect(topright=(self.panneau.right - 30, y + 36)))
        screen.blit(self.police.render("Fréquence de son signal", True, COULEUR_TEXTE_GRIS), (x, y + 85))
        freq = self.police_grande.render(f"{nombre(self.frequence)} MHz", True, COULEUR_TITRE)
        screen.blit(freq, freq.get_rect(midtop=(self.panneau.centerx, y + 118)))

        souris = ecran.souris()
        for rect, _, nom in self.boutons:
            dessiner_bouton(screen, self.police, rect, nom, rect.collidepoint(souris))
        pygame.draw.rect(screen, COULEUR_BOUTON, self.barre, border_radius=8)
        pygame.draw.rect(screen, COULEUR_BORDURE, self.barre, 2, border_radius=8)
        for f in (200, 400, 600, 800):
            tx = self.barre.x + (f - F_MIN) / (F_MAX - F_MIN) * self.barre.width
            texte = self.police_petite.render(str(f), True, COULEUR_TEXTE_GRIS)
            screen.blit(texte, texte.get_rect(midtop=(tx, self.barre.bottom + 4)))
        curseur_x = self.barre.x + (self.frequence - F_MIN) / (F_MAX - F_MIN) * self.barre.width
        pygame.draw.rect(screen, COULEUR_ACCENT, pygame.Rect(curseur_x - 7, self.barre.y - 6, 14, self.barre.height + 12),
                         border_radius=6)

        etat = "piloté par un boîtier" if self.telescopes.pilote(*self.ouvert) else "tourne tout seul"
        lignes = (f"En ce moment : {etat}, il voit à {self.telescopes.portee(*self.ouvert)} cases.",
                  "Plus il reste pointé au même endroit, plus il voit loin.",
                  "Pour le piloter : un boîtier avec processeur, RAM et",
                  "clé USB satellite, réglé sur cette fréquence.")
        for i, ligne in enumerate(lignes):
            screen.blit(self.police_petite.render(ligne, True, COULEUR_TEXTE_GRIS), (x, y + 340 + i * 26))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
