"""Collecte du texte français (introductions d'articles Wikipédia) dans corpus.txt.

Usage: python corpus.py [nombre_de_requêtes]   (20 articles par requête, Ctrl+C pour arrêter)
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

SORTIE = Path(__file__).parent / "donnees" / "corpus.txt"
URL = ("https://{site}/w/api.php?action=query&format=json&generator=random"
       "&grnnamespace=0&grnlimit=20&prop=extracts&exintro=1&explaintext=1&exlimit=20")


def articles(site="fr.wikipedia.org"):
    """Articles au hasard du site Wikipédia donné (fr.wikipedia.org, en.wikipedia.org...)."""
    req = urllib.request.Request(URL.format(site=site), headers={"User-Agent": "corpus.py/1.0 (entrainement IA locale)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    for p in data.get("query", {}).get("pages", {}).values():
        texte = " ".join(p.get("extract", "").split())   # une seule ligne par article
        if len(texte) > 80:
            yield texte


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    total = 0
    try:
        with open(SORTIE, "a", encoding="utf-8") as f:
            for i in range(1, n + 1):
                try:
                    for texte in articles():
                        f.write(texte + "\n")
                        total += 1
                except Exception as e:
                    print(f"  erreur: {e}")
                    time.sleep(5)
                    continue
                f.flush()
                if i % 10 == 0:
                    print(f"  requête {i}/{n}: {total} articles")
                time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    print(f"{total} articles ajoutés à {SORTIE}")


if __name__ == "__main__":
    main()
