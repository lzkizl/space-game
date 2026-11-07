import os

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme import preferences

# =============================================
# ==== Fenêtre du jeu : plein écran ou fenêtré (réglable dans les paramètres)
# ====
# ==== Le jeu dessine TOUJOURS sur une surface de la taille du bureau (la « surface
# ==== logique ») : tous les menus et l'interface sont calés sur cette taille, elle ne
# ==== change donc jamais, même quand on réduit la fenêtre. À la fin de chaque frame,
# ==== `presenter()` l'étire dans la vraie fenêtre, et `souris()` / `traduire()` font le
# ==== chemin inverse pour les clics (sinon on cliquerait à côté).
# =============================================
PLEIN = "plein"
FENETRE = "fenetre"
MODES = [PLEIN, FENETRE]
NOMS = {
    PLEIN: "Plein écran / Fullscreen",
    FENETRE: "Fenêtré / Windowed",
}
PART_FENETRE = 0.75   # en fenêtré, la fenêtre occupe 75 % du bureau
COULEUR_BANDES = (0, 0, 0)   # bandes noires si la fenêtre n'a pas les proportions du bureau

_mode = None       # PLEIN ou FENETRE
_logique = None    # taille de la surface de jeu (celle du bureau)
_ecran = None      # la surface sur laquelle le jeu dessine (jamais remplacée)
_fenetre = None    # la vraie fenêtre (ce que renvoie pygame.display.set_mode)
_rendu = None      # la partie de la fenêtre où l'on étire l'écran (hors bandes noires)
_echelle = 1.0     # taille de la fenêtre / taille logique
_marge = (0, 0)    # décalage du rendu dans la fenêtre (bandes noires)


def _mode_garde():
    """Mode gardé dans parametres.json (plein écran par défaut)."""
    mode = preferences.lire("fenetre", PLEIN)
    return mode if mode in MODES else PLEIN


def creer():
    """Ouvre la fenêtre et renvoie la surface sur laquelle tout le jeu dessine.
    À appeler une seule fois, après pygame.init()."""
    global _logique, _ecran
    if _ecran is None:
        info = pygame.display.Info()
        _logique = (info.current_w, info.current_h)
        _ouvrir(_mode_garde())
        _ecran = pygame.Surface(_logique).convert()
    return _ecran


def surface():
    """La surface de jeu (celle que `creer` a renvoyée)."""
    return _ecran


def taille():
    return _logique


def actuel():
    """Le mode en cours ; celui gardé dans parametres.json si la fenêtre n'est pas
    encore ouverte (une page de menu affichée toute seule, pour l'essayer)."""
    return _mode or _mode_garde()


def choisir(mode):
    """Passe en plein écran ou en fenêtré, tout de suite, et garde le choix."""
    if mode not in MODES or mode == actuel():
        return
    preferences.ecrire("fenetre", mode)
    if _ecran is not None:
        _ouvrir(mode)   # la fenêtre existe : on change tout de suite


def suivant(sens=1):
    """Mode suivant (sens = 1) ou précédent (sens = -1) : pour les flèches des paramètres."""
    choisir(MODES[(MODES.index(actuel()) + sens) % len(MODES)])


def nom():
    return NOMS[actuel()]


# ---- ouverture de la fenêtre ----
def _ouvrir(mode):
    global _mode, _fenetre
    largeur, hauteur = _logique
    if mode == PLEIN:
        # sans bordure, collée en haut à gauche, exactement la taille du bureau
        os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
        _fenetre = pygame.display.set_mode((largeur, hauteur), pygame.NOFRAME)
    else:
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
        os.environ["SDL_VIDEO_CENTERED"] = "1"
        taille_fenetre = (max(640, int(largeur * PART_FENETRE)),
                          max(480, int(hauteur * PART_FENETRE)))
        _fenetre = pygame.display.set_mode(taille_fenetre, pygame.RESIZABLE)
        _centrer()
    _mode = mode
    _calculer_rendu()


def _centrer():
    """Remet la fenêtre au milieu du bureau (SDL garde sa position précédente quand on
    change de mode sans recréer la fenêtre)."""
    try:
        from pygame._sdl2 import video

        video.Window.from_display_module().position = video.WINDOWPOS_CENTERED
    except Exception:
        pass   # pas grave : la fenêtre reste où SDL l'a mise


def _redimensionner(taille_fenetre):
    """La fenêtre a été agrandie / réduite à la souris : on refait la vraie fenêtre à
    cette taille, puis on recalcule où étirer la surface de jeu."""
    global _fenetre
    if _mode != FENETRE:
        return
    largeur, hauteur = taille_fenetre
    _fenetre = pygame.display.set_mode((max(320, largeur), max(240, hauteur)), pygame.RESIZABLE)
    _calculer_rendu()


def _calculer_rendu():
    """Où étirer la surface de jeu dans la fenêtre : le plus grand rectangle aux
    proportions du bureau, centré (bandes noires autour s'il en reste). `_rendu` est
    l'image intermédiaire où l'on réduit la surface de jeu, recyclée d'une frame à
    l'autre (réduire directement dans la fenêtre fait planter SDL)."""
    global _rendu, _echelle, _marge
    largeur, hauteur = _logique
    fl, fh = _fenetre.get_size()
    _echelle = min(fl / largeur, fh / hauteur)
    taille = (max(1, int(largeur * _echelle)), max(1, int(hauteur * _echelle)))
    _marge = ((fl - taille[0]) // 2, (fh - taille[1]) // 2)
    _rendu = None if taille == _logique else pygame.Surface(taille).convert()


# ---- chaque frame ----
def presenter():
    """Remplace pygame.display.flip() : met la surface de jeu dans la fenêtre."""
    if _rendu is None:   # la fenêtre fait exactement la taille de la surface de jeu
        _fenetre.blit(_ecran, (0, 0))
    else:
        if _marge != (0, 0):
            _fenetre.fill(COULEUR_BANDES)   # fenêtre aux mauvaises proportions : bandes noires
        pygame.transform.scale(_ecran, _rendu.get_size(), _rendu)
        _fenetre.blit(_rendu, _marge)
    pygame.display.flip()


# ---- souris : de la fenêtre vers la surface de jeu ----
def convertir(pos):
    """Position dans la fenêtre -> position dans la surface de jeu."""
    if _echelle == 1.0 and _marge == (0, 0):
        return pos
    return (int((pos[0] - _marge[0]) / _echelle), int((pos[1] - _marge[1]) / _echelle))


def souris():
    """Remplace pygame.mouse.get_pos()."""
    return convertir(pygame.mouse.get_pos())


A_POSITION = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)


def traduire(event):
    """Remplace les coordonnées d'un évènement de souris par celles de la surface de jeu.
    Suit aussi les redimensionnements de la fenêtre. À appeler sur chaque évènement reçu."""
    if event.type == pygame.VIDEORESIZE:
        _redimensionner(event.size)
        return event
    if event.type not in A_POSITION or _ecran is None:
        return event
    attributs = dict(event.__dict__)
    attributs["pos"] = convertir(event.pos)
    if "rel" in attributs and _echelle:
        attributs["rel"] = (int(event.rel[0] / _echelle), int(event.rel[1] / _echelle))
    return pygame.event.Event(event.type, attributs)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
