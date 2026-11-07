import random

import pygame

COULEUR_FOND = (3, 3, 12)
NB_ETOILES = 300
COULEURS = ((255, 255, 255), (180, 200, 255), (255, 220, 190))


class FondEtoiles:
    """Fond d'étoiles fixe (comme celui du menu principal, mais immobile). Les étoiles
    sont dessinées directement sur la vue du monde à chaque image (300 petits carrés,
    quasi gratuit) au lieu de copier une grande image : dézoomé, la vue fait des millions
    de pixels et la copier coûtait plus de 15 ms par image."""

    def __init__(self):
        self.etoiles = [(random.random(), random.random(), random.choice((1, 1, 2, 2, 3)),
                         random.choice(COULEURS)) for _ in range(NB_ETOILES)]

    def draw(self, vue, zoom):
        vue.fill(COULEUR_FOND)
        largeur, hauteur = vue.get_size()
        for x, y, rayon, couleur in self.etoiles:
            taille = max(1, round(rayon / zoom))  # garde la même taille à l'écran quand on dézoome
            vue.fill(couleur, (int(x * largeur), int(y * hauteur), taille, taille))
