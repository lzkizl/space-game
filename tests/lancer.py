"""Lance tous les tests du dossier, l'un apres l'autre, et dit ce qui casse.

    python tests/lancer.py

Chaque test tourne sans fenetre (SDL dummy) et n'ecrit jamais dans les mondes existants.
A lancer apres chaque changement un peu profond : c'est le filet de securite du chantier
multijoueur (voir le plan : la verification se fait a chaque etape, pas a la fin).
"""
import subprocess
import sys
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
CODE = DOSSIER.parent / "code"

# du plus rapide au plus lent
TESTS = [
    ("copier_coller.py", [], "copier-coller de l'adresse dans le menu multijoueur"),
    ("deux_joueurs.py", [], "le monde gere plusieurs joueurs"),
    ("propulsion.py", [], "plusieurs bases poussees en meme temps"),
    ("reseau.py", [], "hote et client se parlent par de vraies sockets"),
    ("anciennes.py", [], "les sauvegardes deja sur le disque se relisent"),
    ("fumee.py", ["90"], "la vraie boucle de jeu tourne, sauvegarde et recharge"),
    ("deux_jeux.py", [], "deux vraies parties jouent ensemble (deux processus)"),
]


def main():
    resultats = []
    for fichier, args, quoi in TESTS:
        print(f"\n===== {fichier} : {quoi}")
        termine = subprocess.run([sys.executable, str(DOSSIER / fichier), str(CODE), *args])
        resultats.append((fichier, termine.returncode == 0))

    print("\n===== resume")
    for fichier, ok in resultats:
        print(f"  {'OK   ' if ok else 'ECHEC'} {fichier}")
    rates = [f for f, ok in resultats if not ok]
    if rates:
        print(f"\n{len(rates)} test(s) en echec : {', '.join(rates)}")
        return 1
    print("\nTout passe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
