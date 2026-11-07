"""Lance en même temps la collecte des mots français (mots.py) et anglais (mots_en.py) dans ce terminal.
Usage: python mots_tout.py        (Ctrl+C arrête les deux ; elles reprennent où elles s'étaient arrêtées)"""
import subprocess
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
SCRIPTS = ["mots.py", "mots_en.py"]


def main():
    processus = [subprocess.Popen([sys.executable, "-X", "utf8", "-u", nom], cwd=DIR) for nom in SCRIPTS]
    try:
        for p in processus:
            p.wait()
    except KeyboardInterrupt:      # Ctrl+C a déjà été envoyé aux deux : on attend qu'ils sauvegardent et se ferment
        for p in processus:
            p.wait()


if __name__ == "__main__":
    main()
