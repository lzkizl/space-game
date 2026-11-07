import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interface.ui import (COULEUR_ACCENT, COULEUR_TEXTE_GRIS, COULEUR_TITRE, dessiner_infobulle,
                          dessiner_panneau)
from systeme import ecran
from systeme.settings import TAILLE_ICONE

# =============================================
# ==== Réglages
# =============================================
NB_CASES = 5         # cases de la barre du bas
COLONNES = 5         # grille du grand inventaire (Tab)
LIGNES = 4
MAX_PAR_CASE = 80    # nombre maximum d'objets empilés dans une case
QUANTITE_INFINIE = 999  # ressources infinies (panneau admin, F3) : on « possède » autant de chaque objet
TAILLE_CASE = 80
ESPACE = 10          # espace entre les cases
MARGE_BAS = 20       # distance avec le bord bas de l'écran
MARGE_PANNEAU = 20   # marge intérieure du grand inventaire
HAUTEUR_TITRE = 40
HAUTEUR_PIED = 34    # ligne d'aide sous la grille
RAYON_CASE = 12      # coins arrondis des cases

COULEUR_FOND = (30, 30, 50, 225)
COULEUR_PANNEAU = (15, 15, 25, 230)
COULEUR_BORDURE = (90, 90, 115)
COULEUR_SELECTION = (255, 215, 0)
COULEUR_SURVOL = (130, 170, 255)
COULEUR_NUMERO = (255, 255, 255)


def nom_objet(objet):
    """Nom lisible d'un objet : ressource (.nom), recette de la table de craft, ou nom du module."""
    nom = getattr(objet, "nom", None)
    if nom:
        return nom
    from joueur.craft import RECETTES  # (ici et pas en haut : évite un import circulaire)
    for fabrique, nom_recette, _ in RECETTES:
        if fabrique is objet:
            return nom_recette
    return getattr(objet, "__name__", "objet").split(".")[-1].replace("_", " ").capitalize()


class Inventory:
    """Barre d'inventaire en bas de l'écran (clic = sélection de la case) et grand
    inventaire en grille qu'on ouvre/ferme avec Tab. Un clic sur un objet de la
    grille l'échange avec la case sélectionnée de la barre.

    Les cases contiennent un module de construction/ (ou None si elle est vide)."""

    def __init__(self, screen_width, screen_height):
        self.barre = [None] * NB_CASES
        self.grille = [None] * (COLONNES * LIGNES)
        self.selected = 0
        self.ouvert = False
        self.infini = False  # ressources infinies (panneau admin, F3) : rien ne s'use, tout se fabrique
        # quantité empilée dans chaque case (utile pour les ressources : verre, fer, cuivre...)
        self.barre_nb = [0] * NB_CASES
        self.grille_nb = [0] * (COLONNES * LIGNES)
        self.police = pygame.font.Font(None, 24)
        self.police_titre = pygame.font.Font(None, 32)
        self.police_menu = pygame.font.Font(None, 48)
        self._icones = {}  # module de construction -> image réduite
        self._fond_case = pygame.Surface((TAILLE_CASE, TAILLE_CASE), pygame.SRCALPHA)
        pygame.draw.rect(self._fond_case, COULEUR_FOND, self._fond_case.get_rect(), border_radius=RAYON_CASE)

        # barre du bas
        largeur_barre = NB_CASES * TAILLE_CASE + (NB_CASES - 1) * ESPACE
        x0 = (screen_width - largeur_barre) // 2
        y = screen_height - TAILLE_CASE - MARGE_BAS
        self.rects = [
            pygame.Rect(x0 + i * (TAILLE_CASE + ESPACE), y, TAILLE_CASE, TAILLE_CASE)
            for i in range(NB_CASES)
        ]

        # grand inventaire, centré sur l'écran
        largeur_grille = COLONNES * TAILLE_CASE + (COLONNES - 1) * ESPACE
        hauteur_grille = LIGNES * TAILLE_CASE + (LIGNES - 1) * ESPACE
        self.panneau = pygame.Rect(0, 0,
                                   largeur_grille + 2 * MARGE_PANNEAU,
                                   hauteur_grille + 2 * MARGE_PANNEAU + HAUTEUR_TITRE + HAUTEUR_PIED)
        self.panneau.center = (screen_width // 2, screen_height // 2)
        gx = self.panneau.x + MARGE_PANNEAU
        gy = self.panneau.y + MARGE_PANNEAU + HAUTEUR_TITRE
        self.rects_grille = [
            pygame.Rect(gx + c * (TAILLE_CASE + ESPACE), gy + l * (TAILLE_CASE + ESPACE),
                        TAILLE_CASE, TAILLE_CASE)
            for l in range(LIGNES) for c in range(COLONNES)
        ]

    # ---- objet sélectionné ----
    @property
    def objet_selectionne(self):
        return self.barre[self.selected]

    @staticmethod
    def pile_max(objet):
        """Nombre max d'exemplaires dans une case : 1 pour un outil, MAX_PAR_CASE sinon."""
        return 1 if getattr(objet, "OUTIL", False) else MAX_PAR_CASE

    def _listes(self):
        return ((self.barre, self.barre_nb), (self.grille, self.grille_nb))

    def place_pour(self, objet):
        """Nombre d'exemplaires de cet objet qu'on peut encore ranger (piles non pleines
        et cases libres)."""
        maxi = self.pile_max(objet)
        place = 0
        for cases, nombres in self._listes():
            for case, nombre in zip(cases, nombres):
                if case is objet:
                    place += maxi - nombre
                elif case is None:
                    place += maxi
        return place

    def ajouter_objet(self, objet, quantite=1):
        """Ajoute la quantité aux piles de cet objet (construction, outil ou ressource),
        puis dans les cases libres (barre d'abord, puis grille). Renvoie ce qui n'a pas
        pu rentrer (0 si tout est rangé)."""
        maxi = self.pile_max(objet)
        for cases, nombres in self._listes():
            for i, case in enumerate(cases):
                if case is objet and quantite:
                    mis = min(quantite, maxi - nombres[i])
                    nombres[i] += mis
                    quantite -= mis
        for cases, nombres in self._listes():
            for i, case in enumerate(cases):
                if case is None and quantite:
                    mis = min(quantite, maxi)
                    cases[i] = objet
                    nombres[i] = mis
                    quantite -= mis
        return quantite

    def compter(self, objet):
        """Nombre total d'exemplaires de cet objet dans l'inventaire."""
        if self.infini:
            return QUANTITE_INFINIE
        return sum(nombre for cases, nombres in self._listes()
                   for case, nombre in zip(cases, nombres) if case is objet)

    def retirer(self, objet, quantite):
        """Retire cette quantité d'exemplaires (les cases vidées redeviennent libres).
        À n'appeler que si `compter(objet) >= quantite`."""
        if self.infini:
            return
        for cases, nombres in self._listes():
            for i, case in enumerate(cases):
                if case is objet and quantite:
                    pris = min(quantite, nombres[i])
                    nombres[i] -= pris
                    quantite -= pris
                    if nombres[i] == 0:
                        cases[i] = None

    def consommer_selection(self):
        """Retire un exemplaire de l'objet de la case sélectionnée (la case se vide
        quand il n'en reste plus)."""
        if not self.infini:
            self._enlever_selection()

    def _enlever_selection(self):
        self.barre_nb[self.selected] -= 1
        if self.barre_nb[self.selected] <= 0:
            self.barre[self.selected] = None
            self.barre_nb[self.selected] = 0

    def jeter(self, tout=False):
        """Jette (détruit) un exemplaire de l'objet sélectionné, ou toute la pile avec tout=True.
        L'outil de déconstruction ne se jette pas. Renvoie True si quelque chose a été jeté."""
        objet = self.objet_selectionne
        if objet is None or getattr(objet, "OUTIL", False):
            return False
        if tout:
            self.barre_nb[self.selected] = 1
        self._enlever_selection()  # (on peut jeter même avec les ressources infinies)
        return True

    def icone(self, objet):
        if objet not in self._icones:
            image = pygame.image.load(objet.ICONE).convert_alpha()
            self._icones[objet] = pygame.transform.smoothscale(image, TAILLE_ICONE)
        return self._icones[objet]

    # ---- souris / clavier ----
    def contient(self, pos):
        """True si la position (écran) est sur l'inventaire (barre ou grand inventaire ouvert)."""
        if self.ouvert and self.panneau.collidepoint(pos):
            return True
        return any(rect.collidepoint(pos) for rect in self.rects)

    def handle_event(self, event):
        """Gère Tab et le clic gauche. Renvoie True si l'évènement a été consommé."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            self.ouvert = not self.ouvert
            return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_j:
            self.jeter(tout=bool(event.mod & pygame.KMOD_SHIFT))
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    return True

            if self.ouvert:
                for i, rect in enumerate(self.rects_grille):
                    if rect.collidepoint(event.pos):
                        # échange avec la case sélectionnée de la barre
                        self.grille[i], self.barre[self.selected] = (
                            self.barre[self.selected], self.grille[i])
                        self.grille_nb[i], self.barre_nb[self.selected] = (
                            self.barre_nb[self.selected], self.grille_nb[i])
                        return True
                return True  # tout clic quand l'inventaire est ouvert est absorbé
        return False

    # ---- dessin ----
    def _dessiner_case(self, screen, rect, objet, nombre, fond, bordure, epaisseur):
        """Une case arrondie (le paramètre `fond` n'est plus utilisé : gardé pour les panneaux
        de coffres et de stockage qui appellent cette méthode)."""
        screen.blit(self._fond_case, rect)
        if objet is not None:
            image = self.icone(objet)
            screen.blit(image, image.get_rect(center=rect.center))
            if nombre > 1:
                texte = self.police_titre.render(str(nombre), True, COULEUR_NUMERO)
                ombre = self.police_titre.render(str(nombre), True, (0, 0, 0))
                place = texte.get_rect(bottomright=(rect.right - 7, rect.bottom - 5))
                screen.blit(ombre, place.move(2, 2))
                screen.blit(texte, place)
        pygame.draw.rect(screen, bordure, rect, epaisseur, border_radius=RAYON_CASE)

    def draw(self, screen):
        souris = ecran.souris()

        if self.ouvert:
            self._dessiner_grille(screen, souris)

        # socle discret derrière la barre
        socle = self.rects[0].unionall(self.rects).inflate(28, 28)
        fond = pygame.Surface(socle.size, pygame.SRCALPHA)
        pygame.draw.rect(fond, (15, 15, 25, 150), fond.get_rect(), border_radius=20)
        screen.blit(fond, socle)
        pygame.draw.rect(screen, (60, 60, 85), socle, 2, border_radius=20)

        for i, rect in enumerate(self.rects):
            if i == self.selected:
                pygame.draw.rect(screen, (120, 100, 20), rect.inflate(8, 8), 2, border_radius=RAYON_CASE + 4)
                bordure, epaisseur = COULEUR_SELECTION, 4
            elif rect.collidepoint(souris):
                bordure, epaisseur = COULEUR_SURVOL, 3
            else:
                bordure, epaisseur = COULEUR_BORDURE, 2
            self._dessiner_case(screen, rect, self.barre[i], self.barre_nb[i], None, bordure, epaisseur)

            numero = self.police.render(str(i + 1), True, COULEUR_TEXTE_GRIS)
            screen.blit(numero, (rect.x + 8, rect.y + 5))

        # nom de l'objet sélectionné, au-dessus de la barre
        if self.objet_selectionne is not None and not self.ouvert:
            nom = self.police_titre.render(nom_objet(self.objet_selectionne), True, COULEUR_TITRE)
            ombre = self.police_titre.render(nom_objet(self.objet_selectionne), True, (0, 0, 0))
            place = nom.get_rect(midbottom=(socle.centerx, socle.y - 8))
            screen.blit(ombre, place.move(2, 2))
            screen.blit(nom, place)

        # infobulle de la case survolée
        for rects, cases in ((self.rects, self.barre), (self.rects_grille if self.ouvert else [], self.grille)):
            for rect, objet in zip(rects, cases):
                if objet is not None and rect.collidepoint(souris):
                    dessiner_infobulle(screen, self.police_titre, nom_objet(objet), souris)

    def _dessiner_grille(self, screen, souris):
        dessiner_panneau(screen, self.panneau)
        titre = self.police_menu.render("Inventaire", True, COULEUR_TITRE)
        screen.blit(titre, (self.panneau.x + MARGE_PANNEAU, self.panneau.y + MARGE_PANNEAU - 4))
        aide = self.police.render("Tab : fermer", True, COULEUR_TEXTE_GRIS)
        screen.blit(aide, aide.get_rect(topright=(self.panneau.right - MARGE_PANNEAU, self.panneau.y + MARGE_PANNEAU + 4)))

        for rect, objet, nombre in zip(self.rects_grille, self.grille, self.grille_nb):
            if rect.collidepoint(souris):
                bordure, epaisseur = COULEUR_SURVOL, 3
            else:
                bordure, epaisseur = COULEUR_BORDURE, 2
            self._dessiner_case(screen, rect, objet, nombre, None, bordure, epaisseur)

        pied = self.police.render("Clic : échanger avec la barre  ·  J : jeter", True,
                                  COULEUR_TEXTE_GRIS)
        screen.blit(pied, pied.get_rect(midbottom=(self.panneau.centerx, self.panneau.bottom - 14)))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
