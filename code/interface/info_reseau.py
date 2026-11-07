import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interface.ui import COULEUR_ACCENT, COULEUR_TEXTE, COULEUR_TEXTE_GRIS

# =============================================
# ==== Le bandeau multijoueur, en haut au milieu : quand on héberge, l'adresse à donner aux
# ==== autres et qui est connecté ; et, des deux côtés, les arrivées et les départs.
# =============================================
DUREE_MESSAGE = 6000  # millisecondes d'affichage d'une nouvelle


class InfoReseau:
    def __init__(self, largeur, hauteur):
        self.largeur = largeur
        self.hauteur = hauteur
        self.police = pygame.font.Font(None, 34)
        self.police_petite = pygame.font.Font(None, 28)
        self.messages = []  # [(texte, moment où il disparaît)]

    def annoncer(self, textes):
        fin = pygame.time.get_ticks() + DUREE_MESSAGE
        self.messages.extend((texte, fin) for texte in textes)

    def draw(self, screen, reseau, joueurs):
        if reseau is None:
            return
        y = 12
        if reseau.hote:
            connectes = len(reseau.connectes())
            compagnie = "personne d'autre pour l'instant" if not connectes else (
                f"{connectes} joueur{'s' if connectes > 1 else ''} connecté{'s' if connectes > 1 else ''}")
            titre = f"Partie ouverte — adresse : {reseau.adresse}"
            if reseau.port != 50000:
                titre += f":{reseau.port}"
            image = self.police.render(titre, True, COULEUR_ACCENT)
            screen.blit(image, image.get_rect(midtop=(self.largeur // 2, y)))
            y += image.get_height() + 2
            image = self.police_petite.render(compagnie, True, COULEUR_TEXTE_GRIS)
            screen.blit(image, image.get_rect(midtop=(self.largeur // 2, y)))
            y += image.get_height() + 6

        maintenant = pygame.time.get_ticks()
        self.messages = [m for m in self.messages if m[1] > maintenant]
        for texte, _ in self.messages[-4:]:
            image = self.police_petite.render(texte, True, COULEUR_TEXTE)
            screen.blit(image, image.get_rect(midtop=(self.largeur // 2, y)))
            y += image.get_height() + 2


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
