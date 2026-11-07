"""Récupérateur de mots ANGLAIS, sans fin (le frère de mots.py, qui lui fait le français).

Chaque mot reçoit un numéro (mots_anglais.json) ; les mots déjà présents gardent le leur.

Il tourne tant que tu ne l'arrêtes pas (Ctrl+C), sans jamais planter :
  - coupure d'internet ou limite de débit -> il attend et recommence tout seul ;
  - il reprend exactement où il s'était arrêté (etat_mots_en.json) ;
  - les fichiers sont écrits par étapes (jamais à moitié) avec une copie de secours .bak.

Sources, dans l'ordre :
  1. dictionnaires : liste de 370 000 mots anglais, Hunspell en_US, Wiktionary anglais (noms, verbes,
     adjectifs, formes conjuguées, pluriels...). Leurs mots sont acceptés tout de suite.
  2. textes : TOUS les articles de Wikipedia anglais, un par un dans l'ordre alphabétique (le vrai scan
     complet, il reprend où il s'était arrêté), puis Simple English Wikipedia, Wikinews, Wikiquote et
     Wikibooks. En plus, des articles au hasard sans fin. Un mot trouvé dans un texte n'entre dans le
     dictionnaire qu'après l'avoir vu 2 fois (écarte les fautes et les noms bizarres).

Usage: python mots_en.py              (sans fin)
       python mots_en.py --minutes 30 (s'arrête après 30 minutes)
"""
import re
import sys
import time
import urllib.parse
from collections import Counter

from mots import (DIR, DONNEES, CAPACITE, PAUSE_ENTRE_REQUETES, ErreurReseau, Source, api_json, ecrire_json, entrer,
                  lire_json, telecharger, verrouiller)

SORTIE = DONNEES / "mots_anglais.json"
ETAT = DONNEES / "etat_mots_en.json"
SAUVER_TOUS = 300                  # secondes entre deux écritures sur le disque

SOURCE_LISTE = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
SOURCE_HUNSPELL = "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US.dic"
CATEGORIES_WIKTIONARY = [
    "Category:English nouns", "Category:English verbs", "Category:English adjectives", "Category:English adverbs",
    "Category:English prepositions", "Category:English pronouns", "Category:English conjunctions",
    "Category:English interjections", "Category:English determiners", "Category:English numerals",
    "Category:English verb forms", "Category:English noun forms", "Category:English plurals",
    "Category:English past participles", "Category:English present participles",
    "Category:English simple past forms", "Category:English third-person singular forms",
    "Category:English comparative adjectives", "Category:English superlative adjectives",
    "Category:English contractions", "Category:English abbreviations", "Category:English slang",
    "Category:English proper nouns",
]
SITES_TEXTE = ["en.wikipedia.org", "simple.wikipedia.org", "en.wikinews.org", "en.wikiquote.org", "en.wikibooks.org"]

# Mots que les dictionnaires ne connaissent pas mais que l'IA utilise
EXTRAS = {"pytorch", "chatgpt", "openai", "anthropic", "minecraft", "roblox", "fortnite", "pokemon", "numpy",
          "tensorflow", "dataset", "epoch", "gpu", "fps", "mayday", "okay", "hey", "thanks", "goodbye"}

JETON = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")      # un mot (lettres de toutes langues, ' et - au milieu)
MOT_ANGLAIS = re.compile(r"[a-z]+(?:['-][a-z]+)*")      # seulement a-z : on écarte les mots d'autres langues


def valide(m):
    return bool(MOT_ANGLAIS.fullmatch(m)) and (2 <= len(m) <= 30 or m in ("a", "i"))


def mots_de(texte):
    return [m for m in (j.lower() for j in JETON.findall(texte.replace("’", "'"))) if valide(m)]


class ListeMots(Source):
    """Un fichier texte avec un mot par ligne."""

    def __init__(self, nom, url):
        super().__init__(nom, None)
        self.url = url

    def suivant(self):
        contenu = telecharger(self.url, timeout=120).decode("utf-8", errors="ignore")
        self.fini = True
        return [m for m in (l.strip().lower() for l in contenu.splitlines()) if valide(m)]


class Hunspell(Source):
    def suivant(self):
        contenu = telecharger(SOURCE_HUNSPELL, timeout=120).decode("utf-8", errors="ignore")
        self.fini = True
        return [m for m in (l.split("/")[0].strip().lower() for l in contenu.splitlines()[1:]) if valide(m)]


class Wiktionary(Source):
    """Toutes les entrées d'une catégorie du Wiktionary anglais, 500 par requête, en reprenant au curseur."""

    def __init__(self, categorie, etat):
        super().__init__("wiktionary:" + categorie.split(":", 1)[1], etat)
        self.categorie = categorie
        self.pause = PAUSE_ENTRE_REQUETES
        self.fini = self.etat["curseurs"].get(self.nom) == "fini"

    def suivant(self):
        url = ("https://en.wiktionary.org/w/api.php?action=query&list=categorymembers&format=json"
               "&cmnamespace=0&cmlimit=500&cmtitle=" + urllib.parse.quote(self.categorie))
        curseur = self.etat["curseurs"].get(self.nom)
        if curseur:
            url += "&cmcontinue=" + urllib.parse.quote(curseur)
        data = api_json(url)
        membres = data.get("query", {}).get("categorymembers", [])
        suite = data.get("continue", {}).get("cmcontinue")
        self.etat["curseurs"][self.nom] = suite if suite else "fini"
        self.fini = not suite
        return [t for t in (m["title"].lower() for m in membres) if valide(t)]


class TousLesArticles(Source):
    """Scan complet d'un site Wikimédia : tous les articles, dans l'ordre alphabétique, 20 par requête.
    Le curseur est sauvegardé : après un arrêt il repart exactement de là."""
    fiable = False

    def __init__(self, site, etat):
        super().__init__("scan:" + site, etat)
        self.site = site
        self.pause = PAUSE_ENTRE_REQUETES
        self.fini = self.etat["curseurs"].get(self.nom) == "fini"

    def suivant(self):
        url = (f"https://{self.site}/w/api.php?action=query&format=json&generator=allpages&gapnamespace=0"
               "&gapfilterredir=nonredirects&gaplimit=20&prop=extracts&exintro=1&explaintext=1&exlimit=20")
        curseur = self.etat["curseurs"].get(self.nom)
        if isinstance(curseur, dict):
            url += "&" + urllib.parse.urlencode(curseur)
        data = api_json(url)
        suite = data.get("continue")
        self.etat["curseurs"][self.nom] = suite if suite else "fini"
        self.fini = not suite
        pages = data.get("query", {}).get("pages", {}).values()
        return mots_de(" ".join(p.get("extract", "") for p in pages))


class TexteAuHasard(Source):
    """Articles au hasard d'un site Wikimédia : source qui ne finit jamais."""
    fiable = False

    def __init__(self, site, etat):
        super().__init__("hasard:" + site, etat)
        self.site = site
        self.pause = PAUSE_ENTRE_REQUETES

    def suivant(self):
        url = (f"https://{self.site}/w/api.php?action=query&format=json&generator=random&grnnamespace=0"
               "&grnlimit=20&prop=extracts&exintro=1&explaintext=1&exlimit=20")
        pages = api_json(url).get("query", {}).get("pages", {}).values()
        return mots_de(" ".join(p.get("extract", "") for p in pages))


class MotsAMoi(Source):
    def suivant(self):
        self.fini = True
        return list(EXTRAS)


def construire_sources(etat):
    sources = [MotsAMoi("extras", etat)]
    if not etat["fait"].get("liste"):
        sources.append(ListeMots("liste", SOURCE_LISTE))
    if not etat["fait"].get("hunspell"):
        sources.append(Hunspell("hunspell", etat))
    sources += [Wiktionary(c, etat) for c in CATEGORIES_WIKTIONARY]
    sources += [TousLesArticles(s, etat) for s in SITES_TEXTE]
    sources += [TexteAuHasard(s, etat) for s in SITES_TEXTE]      # ne finit jamais : le programme est sans fin
    return sources


def charger_existants():
    data = lire_json(SORTIE, {})
    return {m: i for i, m in enumerate(data)} if isinstance(data, list) else data


def main():
    args = sys.argv[1:]
    fin = time.time() + float(args[args.index("--minutes") + 1]) * 60 if "--minutes" in args else None

    if not verrouiller("mots_en"):
        print("Le récupérateur de mots anglais tourne déjà dans une autre fenêtre : celle-ci se ferme.", flush=True)
        return
    ids = charger_existants()
    etat = lire_json(ETAT, {})
    etat.setdefault("curseurs", {})
    etat.setdefault("fait", {})
    etat.setdefault("candidats", {})
    candidats = etat["candidats"]
    sources = construire_sources(etat)
    depart, derniere_sauvegarde, dernier_affichage = len(ids), time.time(), 0.0
    par_source = Counter()
    print(f"English words already stored: {len(ids)}. Ctrl+C to stop (everything is saved).", flush=True)

    def sauvegarder():
        ecrire_json(SORTIE, ids)
        ecrire_json(ETAT, etat)

    try:
        while fin is None or time.time() < fin:
            actives = [s for s in sources if not s.fini]
            dico = [s for s in actives if s.fiable]            # d'abord les dictionnaires, puis les textes
            for source in (dico or actives):
                if fin is not None and time.time() >= fin:
                    break
                try:
                    mots = source.suivant()
                except ErreurReseau as e:
                    print(f"  [{source.nom}] pas de réponse ({e}) : pause de 60 s", flush=True)
                    time.sleep(60)
                    continue
                except Exception as e:                           # une source qui bogue ne doit jamais tout arrêter
                    print(f"  [{source.nom}] erreur {type(e).__name__}: {e}", flush=True)
                    time.sleep(10)
                    continue
                par_source[source.nom] += entrer(ids, candidats, mots, source.fiable)
                if source.fini and source.nom in ("liste", "hunspell"):
                    etat["fait"][source.nom] = True
                if len(ids) >= CAPACITE:
                    print(f"Dictionnaire plein ({CAPACITE} mots) : arrêt.", flush=True)
                    return
                if time.time() - derniere_sauvegarde >= SAUVER_TOUS:
                    sauvegarder()
                    derniere_sauvegarde = time.time()
                if time.time() - dernier_affichage >= 20:
                    detail = ", ".join(f"{n.split(':')[-1][:16]} +{c}" for n, c in par_source.most_common(4))
                    print(f"  {len(ids)} words (+{len(ids) - depart})  [{detail}]", flush=True)
                    dernier_affichage = time.time()
                time.sleep(source.pause)
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        sauvegarder()
        print(f"Écrit : {len(ids)} mots (+{len(ids) - depart} cette fois) dans {SORTIE.name}", flush=True)


if __name__ == "__main__":
    main()
