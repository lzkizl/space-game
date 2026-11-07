import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interface.ui import dessiner_panneau
from systeme import ecran
from joueur.inventory import (COULEUR_BORDURE, COULEUR_FOND, COULEUR_NUMERO,
                       COULEUR_SURVOL, ESPACE, MARGE_BAS, MARGE_PANNEAU, TAILLE_CASE)

HAUTEUR_TITRE = 30


class PanneauStock:
    """Panneau d'inventaire d'un robot ou d'une plante, ouvert par un clic gauche dessus.
    Le conteneur affiché a : `titre`, `cases` (la liste des ressources, une case chacune)
    et `stock` ({ressource: quantité}). On ne peut rien y mettre, seulement y prendre
    (sauf une tourelle, qui a `charger` : cliquer sa case avec des munitions en main la charge)."""

    def __init__(self, screen_width, screen_height):
        self.largeur = screen_width
        self.hauteur = screen_height
        self.ouvert = None  # conteneur dont le panneau est ouvert
        self.panneau = pygame.Rect(0, 0, 0, 0)
        self.rects = []
        self.police = pygame.font.Font(None, 28)

    # ---- ouverture / fermeture ----
    def ouvrir(self, conteneur):
        """Ouvre le panneau du conteneur : une case par ressource, centré juste au-dessus
        de la barre du bas."""
        self.ouvert = conteneur
        nombre = len(conteneur.cases)
        largeur = nombre * TAILLE_CASE + (nombre - 1) * ESPACE
        self.panneau = pygame.Rect(0, 0, max(largeur, 330) + 2 * MARGE_PANNEAU,
                                   TAILLE_CASE + 2 * MARGE_PANNEAU + HAUTEUR_TITRE)
        barre_y = self.hauteur - TAILLE_CASE - MARGE_BAS
        self.panneau.midbottom = (self.largeur // 2, barre_y - 20)
        gx = self.panneau.centerx - largeur // 2
        gy = self.panneau.y + MARGE_PANNEAU + HAUTEUR_TITRE
        self.rects = [pygame.Rect(gx + i * (TAILLE_CASE + ESPACE), gy, TAILLE_CASE, TAILLE_CASE)
                      for i in range(nombre)]

    def fermer_si(self, conteneur):
        """Ferme le panneau s'il montre ce conteneur (qui vient de disparaître)."""
        if self.ouvert is conteneur:
            self.ouvert = None

    def contient(self, pos):
        """True si la position (écran) est sur le panneau ouvert."""
        return self.ouvert is not None and self.panneau.collidepoint(pos)

    # ---- évènements ----
    def handle_event(self, event, inventaire):
        """Clic sur une case : prend ce qu'elle contient. Echap ferme le panneau, un clic
        ailleurs aussi. Renvoie True si l'évènement est consommé."""
        if self.ouvert is None:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.ouvert = None  # (Echap ne doit pas ouvrir la pause)
                return True
            if event.key == pygame.K_TAB:
                self.ouvert = None  # Tab ouvre l'inventaire à la place

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panneau.collidepoint(event.pos):
                self.ouvert = None
                return False  # le clic continue (autre robot, pose...)
            for rect, ressource in zip(self.rects, self.ouvert.cases):
                if rect.collidepoint(event.pos):
                    quantite = self.ouvert.stock[ressource]
                    if hasattr(self.ouvert, "charger") and inventaire.objet_selectionne is ressource:
                        self.ouvert.charger(inventaire)  # tourelle : on y met les munitions tenues
                    elif quantite:
                        # ce qui ne rentre pas (inventaire plein) reste sur place
                        self.ouvert.stock[ressource] = inventaire.ajouter_objet(ressource, quantite)
                    break
            return True  # tout clic sur le panneau est absorbé
        return False

    # ---- dessin ----
    def draw(self, screen, inventaire):
        if self.ouvert is None:
            return
        dessiner_panneau(screen, self.panneau)
        titre = self.police.render(f"{self.ouvert.titre}  (clic : prendre)", True, COULEUR_NUMERO)
        screen.blit(titre, (self.panneau.x + MARGE_PANNEAU, self.panneau.y + MARGE_PANNEAU - 4))

        fond = pygame.Surface((TAILLE_CASE, TAILLE_CASE), pygame.SRCALPHA)
        fond.fill(COULEUR_FOND)
        souris = ecran.souris()
        for rect, ressource in zip(self.rects, self.ouvert.cases):
            quantite = self.ouvert.stock[ressource]
            survol = bool(quantite) and rect.collidepoint(souris)
            inventaire._dessiner_case(screen, rect, ressource if quantite else None, quantite, fond,
                                      COULEUR_SURVOL if survol else COULEUR_BORDURE, 3 if survol else 2)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
