import os
import signal
import threading

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import DELAI_FERMETURE, MOT_POUR_GARDER


def fermer_terminal_apres_delai():
    """Après la fermeture du jeu : ferme le terminal au bout de DELAI_FERMETURE
    secondes, sauf si on tape MOT_POUR_GARDER dans le terminal."""
    garder = threading.Event()

    def attendre_saisie():
        try:
            while True:
                if input().strip().lower() == MOT_POUR_GARDER:
                    break
        except (EOFError, OSError):  # pas de terminal interactif : on ne ferme rien
            pass
        garder.set()

    print(f"\nLe terminal se ferme dans {DELAI_FERMETURE} s "
          f"(tape « {MOT_POUR_GARDER} » puis Entrée pour le garder).")
    threading.Thread(target=attendre_saisie, daemon=True).start()

    if garder.wait(DELAI_FERMETURE):
        print("Terminal conservé.")
        return

    # Le processus parent est le terminal (shell) : en l'arrêtant, la fenêtre se ferme.
    os.kill(os.getppid(), signal.SIGTERM)
