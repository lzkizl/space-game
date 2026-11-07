import random
import time

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme import preferences
from systeme.settings import RACINE

# =============================================
# ==== Musique de fond + bruitages, réglables dans les paramètres
# ==== (choix de la musique, volume de la musique, volume des sons)
# =============================================
DOSSIER = RACINE / "son"
# toutes les musiques du dossier son/ dont le nom commence par "music" (ajouter music_3.mp3 suffit)
MUSIQUES = sorted(f.name for f in DOSSIER.glob("music*") if f.suffix.lower() in (".mp3", ".ogg", ".wav"))
ALEATOIRE = "aleatoire"
AUCUNE = "aucune"
CHOIX_MUSIQUE = [ALEATOIRE] + MUSIQUES + [AUCUNE]
VOLUME_MUSIQUE = 0.3   # valeurs par défaut (avant tout réglage du joueur)
VOLUME_SONS = 0.8
PAS_VOLUME = 0.1
DELAI_DEGAT = 0.25  # secondes mini entre deux sons de dégât (les aliens touchent à chaque frame)
FIN_MUSIQUE = pygame.USEREVENT + 1  # envoyé quand une musique se termine : on lance la suivante

_degat = None
_dernier_degat = 0.0
_derniere_musique = None
_reglages = None


def _audio_ok():
    """Le son ne doit jamais faire planter le jeu (pas de carte son, fichier absent...)."""
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        return True
    except pygame.error:
        return False


def _r():
    """Réglages du joueur, lus une seule fois dans parametres.json."""
    global _reglages
    if _reglages is None:
        musique = preferences.lire("musique", ALEATOIRE)
        _reglages = {
            "musique": musique if musique in CHOIX_MUSIQUE else ALEATOIRE,
            "volume_musique": _borner(preferences.lire("volume_musique", VOLUME_MUSIQUE)),
            "volume_sons": _borner(preferences.lire("volume_sons", VOLUME_SONS)),
        }
    return _reglages


def _borner(valeur):
    try:
        return round(max(0.0, min(1.0, float(valeur))), 2)
    except (TypeError, ValueError):
        return 0.0


def nom_musique(choix):
    """Nom affiché d'un choix de musique : "music_1.mp3" -> "Musique 1"."""
    if choix == ALEATOIRE:
        return "Aléatoire / Random"
    if choix == AUCUNE:
        return "Aucune / None"
    return Path(choix).stem.replace("music", "Musique").replace("_", " ").strip()


# ---- musique ----
def musique():
    return _r()["musique"]


def choisir_musique(choix):
    """Change la musique (ALEATOIRE, AUCUNE ou un fichier de MUSIQUES), la relance et la garde."""
    if choix not in CHOIX_MUSIQUE:
        return
    _r()["musique"] = choix
    preferences.ecrire("musique", choix)
    lancer_musique()


def lancer_musique():
    """Joue la musique choisie (ou une au hasard, différente de la précédente) ; à sa fin,
    FIN_MUSIQUE relance la suivante."""
    global _derniere_musique
    if not _audio_ok():
        return
    pygame.mixer.music.set_endevent()   # couper la musique en cours ne doit pas relancer FIN_MUSIQUE
    choix = musique()
    if choix == AUCUNE or not MUSIQUES:
        pygame.mixer.music.stop()
        return
    if choix == ALEATOIRE:
        autres = [m for m in MUSIQUES if m != _derniere_musique] or MUSIQUES
        choix = random.choice(autres)
    _derniere_musique = choix
    try:
        pygame.mixer.music.load(str(DOSSIER / choix))
        pygame.mixer.music.set_volume(volume_musique())
        pygame.mixer.music.play()
        pygame.mixer.music.set_endevent(FIN_MUSIQUE)
    except (pygame.error, FileNotFoundError):
        pass


def volume_musique():
    return _r()["volume_musique"]


def regler_volume_musique(valeur):
    _r()["volume_musique"] = _borner(valeur)
    preferences.ecrire("volume_musique", volume_musique())
    if _audio_ok():
        pygame.mixer.music.set_volume(volume_musique())


def handle_event(event):
    if event.type == FIN_MUSIQUE:
        lancer_musique()


# ---- bruitages ----
def volume_sons():
    return _r()["volume_sons"]


def regler_volume_sons(valeur):
    """Change le volume des bruitages et fait entendre le son de dégât pour essayer."""
    global _dernier_degat
    _r()["volume_sons"] = _borner(valeur)
    preferences.ecrire("volume_sons", volume_sons())
    _dernier_degat = 0.0
    degat()


def degat():
    """Son quand le héros est touché."""
    global _degat, _dernier_degat
    maintenant = time.time()
    if maintenant - _dernier_degat < DELAI_DEGAT or not _audio_ok():
        return
    _dernier_degat = maintenant
    try:
        if _degat is None:
            _degat = pygame.mixer.Sound(str(DOSSIER / "damage_hit.mp3"))
        _degat.set_volume(volume_sons())
        _degat.play()
    except (pygame.error, FileNotFoundError):
        pass
