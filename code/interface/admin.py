import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interface.ui import COULEUR_ACCENT, COULEUR_TEXTE_GRIS, COULEUR_TITRE, dessiner_bouton, dessiner_panneau
from systeme import ecran

# =============================================
# ==== Panneau admin (F3) : découvrir toute la carte, ressources infinies
# =============================================
LARGEUR_BOUTON = 460
HAUTEUR_BOUTON = 64
ESPACE_BOUTONS = 18
DUREE_MESSAGE = 2000  # millisecondes


class Admin:
    """Panneau admin ouvert/fermé avec F3 (Echap ou un clic à côté le ferment aussi). Le jeu continue
    pendant qu'il est ouvert ; il absorbe les clics."""

    def __init__(self, screen_width, screen_height):
        self.ouvert = False
        self.message = ""
        self.message_fin = 0
        self.police_titre = pygame.font.Font(None, 64)
        self.police = pygame.font.Font(None, 40)
        self.police_petite = pygame.font.Font(None, 28)
        self.panneau = pygame.Rect(0, 0, LARGEUR_BOUTON + 80, 330)
        self.panneau.center = (screen_width // 2, screen_height // 2)
        y0 = self.panneau.y + 110
        self.bouton_carte = pygame.Rect(0, y0, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        self.bouton_infini = pygame.Rect(0, y0 + HAUTEUR_BOUTON + ESPACE_BOUTONS, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        for bouton in (self.bouton_carte, self.bouton_infini):
            bouton.centerx = self.panneau.centerx

    def _afficher_message(self, texte):
        self.message = texte
        self.message_fin = pygame.time.get_ticks() + DUREE_MESSAGE

    def handle_event(self, event, inventaire, grande_carte):
        """F3 ouvre / ferme. Renvoie True si l'évènement est consommé."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self.ouvert = not self.ouvert
            return True
        if not self.ouvert:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ouvert = False  # (Echap ne doit pas ouvrir la pause)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panneau.collidepoint(event.pos):
                self.ouvert = False
            elif self.bouton_carte.collidepoint(event.pos) and not grande_carte.tout_decouvert:
                grande_carte.tout_decouvrir()
                self._afficher_message("Toute la carte est découverte")
            elif self.bouton_infini.collidepoint(event.pos):
                inventaire.infini = not inventaire.infini
                self._afficher_message("Ressources infinies " + ("activées" if inventaire.infini else "désactivées"))
            return True
        return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL)

    def draw(self, screen, inventaire, grande_carte):
        if not self.ouvert:
            return
        souris = ecran.souris()
        dessiner_panneau(screen, self.panneau)
        titre = self.police_titre.render("Admin", True, COULEUR_TITRE)
        screen.blit(titre, titre.get_rect(center=(self.panneau.centerx, self.panneau.y + 50)))
        aide = self.police_petite.render("F3 / Echap : fermer", True, COULEUR_TEXTE_GRIS)
        screen.blit(aide, aide.get_rect(center=(self.panneau.centerx, self.panneau.y + 86)))

        carte = "Carte déjà découverte" if grande_carte.tout_decouvert else "Découvrir toute la carte"
        dessiner_bouton(screen, self.police, self.bouton_carte, carte,
                        not grande_carte.tout_decouvert and self.bouton_carte.collidepoint(souris))
        infini = "Ressources infinies : " + ("OUI" if inventaire.infini else "NON")
        dessiner_bouton(screen, self.police, self.bouton_infini, infini,
                        inventaire.infini or self.bouton_infini.collidepoint(souris))

        if self.message and pygame.time.get_ticks() < self.message_fin:
            image = self.police_petite.render(self.message, True, COULEUR_ACCENT)
            screen.blit(image, image.get_rect(center=(self.panneau.centerx, self.panneau.bottom - 28)))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
