import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interface.ui import (COULEUR_ACCENT, COULEUR_BORDURE, COULEUR_TEXTE, COULEUR_TEXTE_GRIS, COULEUR_TITRE,
                          dessiner_bouton, dessiner_panneau)
from systeme import ecran, langue, son

# =============================================
# ==== Page « Paramètres » (partagée par le menu principal et le menu pause)
# ==== Langue de l'IA, choix de la musique, volume de la musique et des sons,
# ==== fenêtre (plein écran ou fenêtré).
# ==== Chaque ligne : [<]  valeur  [>]  (flèches gauche/droite au clavier)
# =============================================
LARGEUR_BOUTON = 420
HAUTEUR_BOUTON = 70
HAUTEUR_LIGNE = 56
ESPACE_LIGNES = 90
LARGEUR_FLECHE = 60
LARGEUR_VALEUR = 380

# (titre, sous-titre anglais, est un volume)
LIGNES = [
    ("Langue de l'IA", "AI language", False),
    ("Musique", "Music", False),
    ("Volume musique", "Music volume", True),
    ("Volume des sons", "Sound volume", True),
    ("Fenêtre", "Window", False),
]
FENETRE = 4            # index de la ligne « Fenêtre » (plein écran / fenêtré)
RETOUR = len(LIGNES)   # index du bouton Retour pour la sélection au clavier


class PageParametres:
    """Page de réglages. `evenement` renvoie True quand on clique sur Retour."""

    def __init__(self, screen_width, screen_height):
        self.largeur = screen_width
        self.hauteur = screen_height
        self.police_titre = pygame.font.Font(None, 100)
        self.police = pygame.font.Font(None, 44)
        self.police_petite = pygame.font.Font(None, 30)
        self.choix = 0    # ligne sélectionnée au clavier

        centre_x, centre_y = screen_width // 2, screen_height // 2
        self.x_titres = centre_x - 440
        self.lignes = []   # [(rect_moins, rect_valeur, rect_plus)]
        for i in range(len(LIGNES)):
            y = centre_y - 200 + i * ESPACE_LIGNES - HAUTEUR_LIGNE // 2
            moins = pygame.Rect(centre_x - 60, y, LARGEUR_FLECHE, HAUTEUR_LIGNE)
            valeur = pygame.Rect(moins.right + 10, y, LARGEUR_VALEUR, HAUTEUR_LIGNE)
            plus = pygame.Rect(valeur.right + 10, y, LARGEUR_FLECHE, HAUTEUR_LIGNE)
            self.lignes.append((moins, valeur, plus))
        self.rect_retour = pygame.Rect(0, 0, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        self.rect_retour.center = (centre_x, centre_y + 290)

    def ouvrir(self):
        """À appeler quand on affiche la page."""
        self.choix = 0

    # ---- valeurs ----
    def _changer(self, ligne, sens):
        """Passe à la valeur suivante (sens = 1) ou précédente (sens = -1) de la ligne."""
        if ligne == 0:
            codes = list(langue.LANGUES)
            langue.choisir(codes[(codes.index(langue.actuelle()) + sens) % len(codes)])
        elif ligne == 1:
            choix = son.CHOIX_MUSIQUE
            son.choisir_musique(choix[(choix.index(son.musique()) + sens) % len(choix)])
        elif ligne == 2:
            son.regler_volume_musique(son.volume_musique() + sens * son.PAS_VOLUME)
        elif ligne == 3:
            son.regler_volume_sons(son.volume_sons() + sens * son.PAS_VOLUME)
        elif ligne == FENETRE:
            ecran.suivant(sens)   # plein écran <-> fenêtré, tout de suite

    def _volume_au_clic(self, ligne, x):
        """Clic dans la barre d'un volume : le volume prend la position du clic."""
        rect = self.lignes[ligne][1]
        valeur = round((x - rect.x) / rect.w / son.PAS_VOLUME) * son.PAS_VOLUME
        (son.regler_volume_musique if ligne == 2 else son.regler_volume_sons)(valeur)

    def _texte(self, ligne):
        if ligne == 0:
            return langue.LANGUES[langue.actuelle()]
        if ligne == 1:
            return son.nom_musique(son.musique())
        if ligne == FENETRE:
            return ecran.nom()
        return ""

    def _volume(self, ligne):
        return son.volume_musique() if ligne == 2 else son.volume_sons()

    # ---- évènements ----
    def _ligne_sous(self, pos):
        for i, (moins, _, plus) in enumerate(self.lignes):
            if moins.y <= pos[1] < moins.bottom and self.x_titres <= pos[0] < plus.right:
                return i
        return RETOUR if self.rect_retour.collidepoint(pos) else None

    def evenement(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_z):
                self.choix = (self.choix - 1) % (RETOUR + 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.choix = (self.choix + 1) % (RETOUR + 1)
            elif event.key in (pygame.K_LEFT, pygame.K_q) and self.choix != RETOUR:
                self._changer(self.choix, -1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d) and self.choix != RETOUR:
                self._changer(self.choix, 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.choix == RETOUR:
                    return True
                self._changer(self.choix, 1)
        elif event.type == pygame.MOUSEMOTION:
            ligne = self._ligne_sous(event.pos)
            if ligne is not None:
                self.choix = ligne
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect_retour.collidepoint(event.pos):
                return True
            for i, (moins, valeur, plus) in enumerate(self.lignes):
                if moins.collidepoint(event.pos):
                    self._changer(i, -1)
                elif plus.collidepoint(event.pos):
                    self._changer(i, 1)
                elif valeur.collidepoint(event.pos):
                    if LIGNES[i][2]:
                        self._volume_au_clic(i, event.pos[0])
                    else:
                        self._changer(i, 1)
        return False

    # ---- dessin ----
    def dessiner(self, screen, souris, avec_panneau=False):
        centre_x, centre_y = self.largeur // 2, self.hauteur // 2
        if avec_panneau:
            panneau = pygame.Rect(0, 0, 1000, 720)
            panneau.center = (centre_x, centre_y)
            dessiner_panneau(screen, panneau)
        titre = self.police_titre.render("Paramètres / Settings", True, COULEUR_TITRE)
        screen.blit(titre, titre.get_rect(center=(centre_x, centre_y - 280)))

        for i, ((nom, nom_en, est_volume), (moins, valeur, plus)) in enumerate(zip(LIGNES, self.lignes)):
            selection = i == self.choix
            image = self.police.render(nom, True, COULEUR_ACCENT if selection else COULEUR_TEXTE)
            screen.blit(image, (self.x_titres, moins.y))
            image = self.police_petite.render(nom_en, True, COULEUR_TEXTE_GRIS)
            screen.blit(image, (self.x_titres, moins.y + 34))

            dessiner_bouton(screen, self.police, moins, "-" if est_volume else "<", moins.collidepoint(souris))
            dessiner_bouton(screen, self.police, plus, "+" if est_volume else ">", plus.collidepoint(souris))
            if est_volume:
                self._dessiner_volume(screen, valeur, self._volume(i), selection)
            else:
                dessiner_bouton(screen, self.police, valeur, self._texte(i), selection or valeur.collidepoint(souris))

        dessiner_bouton(screen, self.police, self.rect_retour, "Retour / Back",
                        self.choix == RETOUR or self.rect_retour.collidepoint(souris))
        astuce = self.police_petite.render(
            "Gauche / droite ou clic pour changer  /  Left / right or click to change",
            True, COULEUR_TEXTE_GRIS)
        screen.blit(astuce, astuce.get_rect(center=(centre_x, centre_y + 230)))

    def _dessiner_volume(self, screen, rect, volume, selection):
        """Barre remplie selon le volume, avec le pourcentage écrit dessus."""
        pygame.draw.rect(screen, (20, 20, 30), rect, border_radius=14)
        if volume > 0:
            rempli = pygame.Rect(rect.x, rect.y, max(28, round(rect.w * volume)), rect.h)
            pygame.draw.rect(screen, (55, 70, 130), rempli, border_radius=14)
        pygame.draw.rect(screen, COULEUR_ACCENT if selection else COULEUR_BORDURE, rect, 3, border_radius=14)
        image = self.police.render(f"{round(volume * 100)} %", True, COULEUR_TEXTE)
        screen.blit(image, image.get_rect(center=rect.center))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
