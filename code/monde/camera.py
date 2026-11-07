import math


class Camera:
    """Suit une cible (le héros) mais seulement quand elle approche du bord
    de la fenêtre : tant que le héros reste dans la zone centrale ("zone
    morte"), la caméra ne bouge pas.

    Pas de bornage sur une taille de carte fixe : le monde est chargé par
    chunks et n'a pas de limites prédéfinies.
    """

    def __init__(self, window_width, window_height, edge_margin=200,
                 zoom_min=0.25, zoom_max=2.0):
        self.window_width = window_width    # taille de la fenêtre (pixels écran)
        self.window_height = window_height
        self.edge_margin = edge_margin
        self.zoom_min = zoom_min
        self.zoom_max = zoom_max
        self.zoom = 1.0
        self.x = 0
        self.y = 0
        # déplacement total de la caméra quand elle suit sa cible (pas celui dû au zoom) : sert au
        # décor lointain, qui défile moins vite que le monde mais zoome comme lui (voir debris.py)
        self.deplacement_x = 0.0
        self.deplacement_y = 0.0

    # =============================================
    # ==== Taille de la zone du monde visible (en pixels monde) :
    # ==== plus on zoome, plus elle est petite
    # =============================================
    @property
    def screen_width(self):
        return math.ceil(self.window_width / self.zoom)

    @property
    def screen_height(self):
        return math.ceil(self.window_height / self.zoom)

    # =============================================
    # ==== Zoom en gardant fixe le point du monde sous la souris
    # =============================================
    def zoom_by(self, factor, mouse_pos):
        ancien = self.zoom
        self.zoom = max(self.zoom_min, min(self.zoom_max, ancien * factor))
        self.x += mouse_pos[0] / ancien - mouse_pos[0] / self.zoom
        self.y += mouse_pos[1] / ancien - mouse_pos[1] / self.zoom

    def screen_to_view(self, pos):
        """Position écran -> position dans la vue du monde (avant agrandissement)."""
        return pos[0] / self.zoom, pos[1] / self.zoom

    # =============================================
    # ==== Ne déplace la caméra que si la cible sort
    # ==== de la zone morte centrale (marge des bords)
    # =============================================
    def update(self, target):
        """target doit avoir des attributs .x et .y (ex: Hero)."""
        screen_x = target.x - self.x
        screen_y = target.y - self.y
        avant = (self.x, self.y)

        if screen_x < self.edge_margin:
            self.x -= self.edge_margin - screen_x
        elif screen_x > self.screen_width - self.edge_margin:
            self.x += screen_x - (self.screen_width - self.edge_margin)

        if screen_y < self.edge_margin:
            self.y -= self.edge_margin - screen_y
        elif screen_y > self.screen_height - self.edge_margin:
            self.y += screen_y - (self.screen_height - self.edge_margin)
        self.deplacement_x += self.x - avant[0]
        self.deplacement_y += self.y - avant[1]

    # =============================================
    # ==== Décalage à appliquer à tout ce qui est dessiné
    # =============================================
    @property
    def offset(self):
        return (self.x, self.y)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lanceur import lancer

    lancer()
