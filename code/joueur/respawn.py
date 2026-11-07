import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interface.ui import (COULEUR_ACCENT, COULEUR_ALERTE_TEXTE, COULEUR_TEXTE_GRIS, dessiner_bouton,
                dessiner_panneau)
from systeme import ecran

# =============================================
# ==== Réglages
# =============================================
LARGEUR_BOUTON = 420
HAUTEUR_BOUTON = 70
ESPACE_BOUTONS = 20
COULEUR_VOILE = (40, 0, 0, 190)

ACTIONS = ["Réapparaître", "Menu principal"]


class Respawn:
    """Menu affiché quand le héros meurt : on réapparaît au point de départ (jauges
    pleines, inventaire gardé) ou on retourne au menu principal. Le jeu est en pause
    tant qu'il est ouvert."""

    def __init__(self, screen_width, screen_height):
        self.largeur = screen_width
        self.hauteur = screen_height
        self.ouvert = False
        self.cause = ""
        self.choix = 0
        self.police_titre = pygame.font.Font(None, 120)
        self.police = pygame.font.Font(None, 48)
        self.police_petite = pygame.font.Font(None, 40)

        self.voile = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        self.voile.fill(COULEUR_VOILE)

        self.panneau = pygame.Rect(0, 0, LARGEUR_BOUTON + 160, 560)
        self.panneau.center = (screen_width // 2, screen_height // 2)
        y0 = self.panneau.y + 290
        self.rects = [
            pygame.Rect((screen_width - LARGEUR_BOUTON) // 2,
                        y0 + i * (HAUTEUR_BOUTON + ESPACE_BOUTONS),
                        LARGEUR_BOUTON, HAUTEUR_BOUTON)
            for i in range(len(ACTIONS))
        ]

    def ouvrir(self, cause):
        self.ouvert = True
        self.cause = cause
        self.choix = 0

    def handle_event(self, event):
        """Renvoie "reapparaitre" ou "menu_principal" (None sinon)."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_z):
                self.choix = (self.choix - 1) % len(ACTIONS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.choix = (self.choix + 1) % len(ACTIONS)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self._valider(self.choix)
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.choix = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    return self._valider(i)
        return None

    def _valider(self, index):
        if ACTIONS[index] == "Réapparaître":
            self.ouvert = False
            return "reapparaitre"
        return "menu_principal"

    def draw(self, screen):
        if not self.ouvert:
            return
        screen.blit(self.voile, (0, 0))
        dessiner_panneau(screen, self.panneau)
        centre_x = self.largeur // 2

        titre = self.police_titre.render("VOUS ÊTES MORT", True, COULEUR_ALERTE_TEXTE)
        screen.blit(titre, titre.get_rect(center=(centre_x, self.panneau.y + 90)))
        pygame.draw.line(screen, COULEUR_ACCENT, (centre_x - 120, self.panneau.y + 160),
                         (centre_x + 120, self.panneau.y + 160), 3)
        cause = self.police_petite.render(self.cause, True, COULEUR_TEXTE_GRIS)
        screen.blit(cause, cause.get_rect(center=(centre_x, self.panneau.y + 210)))

        souris = ecran.souris()
        for i, (rect, texte) in enumerate(zip(self.rects, ACTIONS)):
            dessiner_bouton(screen, self.police, rect, texte,
                            i == self.choix or rect.collidepoint(souris))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
