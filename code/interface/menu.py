import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interface.parametres import PageParametres
from systeme import ecran
from interface.ui import (COULEUR_ACCENT, COULEUR_BORDURE, COULEUR_TEXTE, COULEUR_TEXTE_GRIS, COULEUR_TITRE,
                dessiner_bouton, dessiner_panneau)

# =============================================
# ==== Réglages
# =============================================
LARGEUR_BOUTON = 420
HAUTEUR_BOUTON = 70
ESPACE_BOUTONS = 20
DUREE_MESSAGE = 2000  # millisecondes

COULEUR_VOILE = (0, 0, 10, 170)

COMMANDES = [
    ("Z Q S D", "Se déplacer"),
    ("Molette", "Zoom / dézoom"),
    ("Clic gauche", "Poser / boire / manger l'objet sélectionné"),
    ("Clic dessus", "Table, coffre, réacteur, robot, plante"),
    ("Clic droit", "Ranger une case dans le coffre / réacteur"),
    ("Tab", "Ouvrir / fermer l'inventaire"),
    ("Echap", "Menu pause"),
]

ACTIONS = ["Reprendre", "Sauvegarder", "Commandes", "Paramètres", "Menu principal", "Quitter le jeu"]


class Menu:
    """Menu pause ouvert/fermé avec Echap. Boutons à la souris ou au clavier
    (haut/bas ou Z/S, Entrée). Le jeu est en pause tant qu'il est ouvert."""

    def __init__(self, screen_width, screen_height):
        self.largeur = screen_width
        self.hauteur = screen_height
        self.ouvert = False
        self.commandes = False  # True : on affiche la page des commandes
        self.parametres = False  # True : on affiche la page des paramètres (langue de l'IA)
        self.page_parametres = PageParametres(screen_width, screen_height)
        self.confirmation = False  # True : « Êtes-vous sûr de quitter ? »
        self.choix_confirmation = 1  # 0 = Oui, 1 = Non (par défaut, pour éviter un quit par erreur)
        self.choix = 0
        self.message = ""
        self.message_fin = 0
        self.police_titre = pygame.font.Font(None, 120)
        self.police = pygame.font.Font(None, 48)
        self.police_petite = pygame.font.Font(None, 34)

        self.voile = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        self.voile.fill(COULEUR_VOILE)

        total = len(ACTIONS) * HAUTEUR_BOUTON + (len(ACTIONS) - 1) * ESPACE_BOUTONS
        y0 = screen_height // 2 - total // 2 + 60
        self.rects = [
            pygame.Rect((screen_width - LARGEUR_BOUTON) // 2,
                        y0 + i * (HAUTEUR_BOUTON + ESPACE_BOUTONS),
                        LARGEUR_BOUTON, HAUTEUR_BOUTON)
            for i in range(len(ACTIONS))
        ]
        self.rect_retour = pygame.Rect(0, 0, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        self.rect_retour.midbottom = (screen_width // 2, screen_height // 2 + 330)
        # boutons Oui / Non de la confirmation
        self.rects_confirmation = []
        for i in range(2):
            rect = pygame.Rect(0, 0, 200, HAUTEUR_BOUTON)
            rect.center = (screen_width // 2 + (-120 if i == 0 else 120), screen_height // 2 + 70)
            self.rects_confirmation.append(rect)

    def afficher_message(self, texte):
        """Petit message sous les boutons (ex : « Monde sauvegardé »)."""
        self.message = texte
        self.message_fin = pygame.time.get_ticks() + DUREE_MESSAGE

    # ---- évènements ----
    def handle_event(self, event):
        """Renvoie l'action à faire par le jeu : "sauvegarder", "menu_principal" ou
        "quitter" (None sinon). Tant que le menu est ouvert il absorbe tout :
        l'appelant doit ignorer l'évènement (voir `ouvert`)."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.ouvert and (self.commandes or self.confirmation or self.parametres):
                self.commandes = self.confirmation = self.parametres = False  # Echap : retour au menu
            else:
                self.ouvert = not self.ouvert
                self.commandes = self.parametres = False
                self.choix = 0
            return None

        if not self.ouvert:
            return None

        if self.parametres:
            if self.page_parametres.evenement(event):
                self.parametres = False
            return None

        if self.confirmation:
            return self._evenement_confirmation(event)

        if self.commandes:
            clic = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
                and self.rect_retour.collidepoint(event.pos)
            entree = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
            if clic or entree:
                self.commandes = False
            return None

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

    def _evenement_confirmation(self, event):
        """Oui -> "quitter" ; Non (ou Echap) -> retour au menu."""
        oui = None
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_q, pygame.K_d):
                self.choix_confirmation = 1 - self.choix_confirmation
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                oui = self.choix_confirmation == 0
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.rects_confirmation):
                if rect.collidepoint(event.pos):
                    self.choix_confirmation = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.rects_confirmation):
                if rect.collidepoint(event.pos):
                    oui = i == 0
        if oui is None:
            return None
        self.confirmation = False
        return "quitter" if oui else None

    def _valider(self, index):
        action = ACTIONS[index]
        if action == "Reprendre":
            self.ouvert = False
        elif action == "Commandes":
            self.commandes = True
        elif action == "Paramètres":
            self.parametres = True
            self.page_parametres.ouvrir()
        elif action == "Sauvegarder":
            return "sauvegarder"
        elif action == "Menu principal":
            return "menu_principal"
        elif action == "Quitter le jeu":
            self.confirmation = True
            self.choix_confirmation = 1
        return None

    # ---- dessin ----
    def draw(self, screen):
        if not self.ouvert:
            return
        screen.blit(self.voile, (0, 0))
        centre_x = self.largeur // 2
        souris = ecran.souris()

        if self.commandes:
            self._draw_commandes(screen, souris)
            return

        if self.parametres:
            self.page_parametres.dessiner(screen, souris, avec_panneau=True)
            return

        if self.confirmation:
            self._draw_confirmation(screen, souris)
            return

        panneau = pygame.Rect(0, 0, LARGEUR_BOUTON + 160, 780)
        panneau.center = (centre_x, self.hauteur // 2 + 20)
        dessiner_panneau(screen, panneau)

        titre = self.police_titre.render("PAUSE", True, COULEUR_TITRE)
        screen.blit(titre, titre.get_rect(center=(centre_x, panneau.y + 90)))
        pygame.draw.line(screen, COULEUR_ACCENT, (centre_x - 120, panneau.y + 150),
                         (centre_x + 120, panneau.y + 150), 3)

        for i, (rect, texte) in enumerate(zip(self.rects, ACTIONS)):
            dessiner_bouton(screen, self.police, rect, texte,
                            i == self.choix or rect.collidepoint(souris))

        if self.message and pygame.time.get_ticks() < self.message_fin:
            image = self.police_petite.render(self.message, True, COULEUR_ACCENT)
            screen.blit(image, image.get_rect(center=(centre_x, panneau.bottom - 30)))

    def _draw_confirmation(self, screen, souris):
        centre_x = self.largeur // 2
        panneau = pygame.Rect(0, 0, 760, 380)
        panneau.center = (centre_x, self.hauteur // 2 - 10)
        dessiner_panneau(screen, panneau)

        titre = self.police.render("Êtes-vous sûr de vouloir quitter ?", True, COULEUR_TITRE)
        screen.blit(titre, titre.get_rect(center=(centre_x, panneau.y + 90)))
        info = self.police_petite.render("La partie sera sauvegardée.", True, COULEUR_TEXTE_GRIS)
        screen.blit(info, info.get_rect(center=(centre_x, panneau.y + 140)))

        for i, (rect, texte) in enumerate(zip(self.rects_confirmation, ("Oui", "Non"))):
            dessiner_bouton(screen, self.police, rect, texte,
                            i == self.choix_confirmation or rect.collidepoint(souris))

    def _draw_commandes(self, screen, souris):
        centre_x = self.largeur // 2
        panneau = pygame.Rect(0, 0, 1000, 760)
        panneau.center = (centre_x, self.hauteur // 2 + 20)
        dessiner_panneau(screen, panneau)

        titre = self.police_titre.render("COMMANDES", True, COULEUR_TITRE)
        screen.blit(titre, titre.get_rect(center=(centre_x, panneau.y + 90)))

        y = panneau.y + 190
        for touche, description in COMMANDES:
            image = self.police.render(touche, True, COULEUR_ACCENT)
            screen.blit(image, (panneau.x + 70, y))
            image = self.police_petite.render(description, True, COULEUR_TEXTE_GRIS)
            screen.blit(image, (panneau.x + 330, y + 8))
            y += 62

        dessiner_bouton(screen, self.police, self.rect_retour, "Retour",
                        self.rect_retour.collidepoint(souris))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
