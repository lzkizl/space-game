import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import RACINE

# =============================================
# ==== Réglages (tu peux les changer)
# =============================================
SPEED = 300           # vitesse en pixels par seconde
FRAME_DURATION = 0.15 # temps (en secondes) pour chaque image de l'animation

DOSSIER = RACINE / "image" / "astronote" / "sprites_astronaute" / "sprites"


# =============================================
# ==== Charge les 4 images d'une animation
# ==== Exemple : charger_images("courir1", "haut", "Z")
# ==== -> [image1, image2, image3, image4]
# =============================================
def charger_images(action, direction, lettre):
    images = []
    for numero in range(1, 5):  # 1, 2, 3, 4
        fichier = f"{DOSSIER}/{action}_{direction}_{lettre}_frame{numero}.png"
        images.append(pygame.image.load(fichier).convert_alpha())
    return images


class Hero:
    def __init__(self, x, y):
        self.x = x  # position dans le monde
        self.y = y

        self.direction = "bas"  # bas / haut / gauche / droite
        self.action = "immobile"  # immobile / course

        # On charge toutes les animations au démarrage.
        # Pour en retrouver une : self.images["course", "haut"]
        self.images = {}
        for direction, lettre in [("bas", "S"), ("haut", "Z"), ("gauche", "Q"), ("droite", "D")]:
            self.images["immobile", direction] = charger_images("rienfaire", direction, lettre)
            self.images["course", direction] = charger_images("courir1", direction, lettre)

        # Vers la gauche (Q), on désactive les images 3 et 4 : on garde seulement 1 et 2
        self.images["immobile", "gauche"] = self.images["immobile", "gauche"][:2]
        self.images["course", "gauche"] = self.images["course", "gauche"][:2]

        self.numero_image = 0  # quelle image on affiche (0, 1, 2 ou 3)
        self.chrono = 0        # temps passé sur l'image actuelle

    def hitbox(self, x, y):
        """Rectangle de collision (en pixels monde) : la moitié basse du sprite,
        centrée, pour que la tête puisse passer devant les murs."""
        image = self.images["immobile", "bas"][0]
        w, h = image.get_size()
        return pygame.Rect(int(x + w * 0.25), int(y + h * 0.5), int(w * 0.5), int(h * 0.5))

    # ---- animation ----
    def animation(self):
        """Les images de l'animation en cours. Jamais vide et jamais absente : si l'action ou la
        direction ne correspondent à rien (valeur abîmée, venue du réseau), on retombe sur
        « immobile, bas » plutôt que de lever une KeyError en plein dessin."""
        return self.images.get((self.action, self.direction)) or self.images["immobile", "bas"]

    def regler_animation(self, action, direction, numero_image):
        """Multijoueur : applique l'animation annoncée par un autre joueur.

        Tout est vérifié ici parce que ces trois valeurs arrivent du réseau, et qu'elles ne vont
        pas forcément ensemble : « gauche » n'a que 2 images, les autres en ont 4. Un numéro
        d'image de 3 appliqué à une direction « gauche » ferait planter le dessin du héros
        (IndexError), ce qui est exactement ce qui arrive en marchant de gauche à droite."""
        if (action, direction) in self.images:
            self.action, self.direction = action, direction
        animation = self.animation()
        try:
            self.numero_image = int(numero_image) % len(animation)
        except (TypeError, ValueError):
            self.numero_image = 0

    def update(self, dt, keys, game_map=None):
        # ---- 1) Déplacement
        # keys[touche] vaut 1 si appuyée, 0 sinon.
        # d - q = +1 (droite), -1 (gauche) ou 0 (rien)
        dx = keys[pygame.K_d] - keys[pygame.K_q]
        dy = keys[pygame.K_s] - keys[pygame.K_z]

        # On teste chaque axe séparément : on glisse le long des murs
        # au lieu de rester collé dessus.
        new_x = self.x + dx * SPEED * dt  # dt = même vitesse sur tous les PC
        if game_map is None or not game_map.bloque(self.hitbox(new_x, self.y)):
            self.x = new_x

        new_y = self.y + dy * SPEED * dt
        if game_map is None or not game_map.bloque(self.hitbox(self.x, new_y)):
            self.y = new_y

        # ---- 2) Direction vers laquelle il regarde
        ancienne_animation = self.action, self.direction
        if keys[pygame.K_q]: self.direction = "gauche"
        if keys[pygame.K_d]: self.direction = "droite"
        if keys[pygame.K_z]: self.direction = "haut"
        if keys[pygame.K_s]: self.direction = "bas"

        # ---- 3) Il court s'il bouge vers le haut ou le bas, sinon immobile
        if (dx or dy) and self.direction in ("haut", "bas"):
            self.action = "course"
        else:
            self.action = "immobile"

        # Une direction peut avoir moins d'images que la précédente (gauche : 2).
        if (self.action, self.direction) != ancienne_animation:
            self.numero_image = 0
            self.chrono = 0

        # ---- 4) Faire tourner l'animation, seulement s'il bouge
        if dx or dy:
            animation = self.animation()
            self.chrono += dt
            if self.chrono >= FRAME_DURATION:
                self.chrono = 0
                self.numero_image += 1
                if self.numero_image == len(animation):  # après la dernière image on recommence
                    self.numero_image = 0
        else:
            # Il ne bouge pas : animation arrêtée sur la première image
            self.numero_image = 0
            self.chrono = 0

    def draw(self, screen, camera_offset=(0, 0)):
        # On prend la bonne animation, puis la bonne image dedans (le numéro est ramené dans
        # l'animation : dessiner ne doit jamais pouvoir planter, même sur une valeur douteuse)
        animation = self.animation()
        image = animation[self.numero_image % len(animation)]

        # Position à l'écran = position dans le monde - décalage de la caméra
        x = self.x - camera_offset[0]
        y = self.y - camera_offset[1]
        screen.blit(image, (x, y))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
