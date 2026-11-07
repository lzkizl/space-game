"""Récupérateur de mots français, sans fin.

Chaque mot reçoit un numéro (mots_francais.json) ; les mots déjà présents gardent le leur.

Il tourne tant que tu ne l'arrêtes pas (Ctrl+C), sans jamais planter :
  - coupure d'internet ou limite de débit -> il attend et recommence tout seul ;
  - il reprend exactement où il s'était arrêté (etat_mots.json) ;
  - les fichiers sont écrits par étapes (jamais à moitié) avec une copie de secours .bak.

Sources, dans l'ordre :
  1. dictionnaires : Hunspell, liste des formes conjuguées, Wiktionnaire (toutes les catégories
     de mots français). Leurs mots sont acceptés tout de suite.
  2. textes : TOUS les articles de Wikipédia, Wikinews, Wikiquote, Wikibooks, un par un dans l'ordre
     alphabétique (scan complet qui reprend où il s'était arrêté), puis des articles au hasard sans fin.
     Toutes les sources tournent à tour de rôle (les textes n'attendent plus la fin des dictionnaires). Un mot
     trouvé dans un texte n'entre dans le dictionnaire qu'après l'avoir vu 2 fois (écarte les fautes).
  3. tes fichiers conversations*.txt (mots à toi, acceptés tout de suite).

Usage: python mots.py              (sans fin)
       python mots.py --minutes 30 (s'arrête après 30 minutes)
"""
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

DIR = Path(__file__).resolve().parent
DONNEES = DIR / "donnees"          # corpus, vocabulaires, états de collecte, verrous
DONNEES.mkdir(exist_ok=True)
SORTIE = DONNEES / "mots_francais.json"
ETAT = DONNEES / "etat_mots.json"
CAPACITE = 2_097_152               # nombre maximum de mots (voir radio.py : 21 bits par mot)
SAUVER_TOUS = 300                  # secondes entre deux écritures sur le disque
VUES_POUR_ENTRER = 2               # fois qu'un mot d'un texte doit être vu pour entrer dans le dictionnaire
PAUSE_ENTRE_REQUETES = 1.0         # secondes (on reste poli avec les sites)

SOURCE_DICO = "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/dictionaries/fr.dic"
SOURCE_FORMES = "https://raw.githubusercontent.com/hbenbel/French-Dictionary/master/dictionary/dictionary.csv"
CATEGORIES_WIKTIONNAIRE = [
    "Catégorie:Lemmes en français",
    "Catégorie:Formes de verbes en français",
    "Catégorie:Formes de noms communs en français",
    "Catégorie:Formes d'adjectifs en français",
    "Catégorie:Formes de pronoms en français",
    "Catégorie:Adverbes en français",
    "Catégorie:Interjections en français",
]
SITES_TEXTE = ["fr.wikipedia.org", "fr.wikinews.org", "fr.wikiquote.org", "fr.wikibooks.org"]

# Mots que les dictionnaires ne connaissent pas mais que l'IA et la radio utilisent
EXTRAS = {
    "mayday", "pytorch", "torch", "chatgpt", "openai", "anthropic", "minecraft", "roblox", "fortnite",
    "pokémon", "zelda", "sonic", "pygame", "numpy", "tensorflow", "dataset", "epoch", "loss", "gpu",
    "fps", "mod", "deep", "learning", "brasilia", "surapprentissage", "okay", "hey", "mdr", "ptdr",
    "slt", "stp", "svp", "ptn", "goodbye", "thanks", "thank", "you", "speak", "english", "and", "over",
    "guten", "buongiorno", "ouaf", "tagada",
}
LETTRES = "a-zàâäéèêëîïôöùûüÿçœæ"
MOT = re.compile(rf"[{LETTRES}]+(?:[-'][{LETTRES}]+)*", re.IGNORECASE)


# =============================================
# ==== Réseau qui ne plante pas
# =============================================
class ErreurReseau(Exception):
    """Internet ou le site ne répond pas, même après plusieurs essais."""


def telecharger(url, essais=6, timeout=45):
    """Contenu d'une adresse (en octets). Réessaie avec des pauses de plus en plus longues."""
    derniere = None
    for essai in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mots-collecteur/2.0 (projet personnel IA)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            derniere = e
            if e.code in (404, 410):                       # l'adresse n'existe pas : inutile de réessayer
                raise ErreurReseau(f"{e.code} {url}") from e
            attente = e.headers.get("Retry-After", "") if e.headers else ""
            pause = int(attente) if attente.isdigit() else min(120, 3 * 2 ** essai)
        except Exception as e:                             # pas d'internet, délai dépassé...
            derniere = e
            pause = min(120, 3 * 2 ** essai)
        time.sleep(pause + random.random())
    raise ErreurReseau(f"{derniere} ({url[:80]})")


def api_json(url):
    return json.loads(telecharger(url).decode("utf-8", errors="ignore"))


# =============================================
# ==== Fichiers écrits sans risque
# =============================================
def lire_json(chemin, defaut):
    """JSON d'un fichier ; si le fichier est abîmé, on prend la copie de secours .bak."""
    for p in (Path(chemin), Path(str(chemin) + ".bak")):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return defaut


def ecrire_json(chemin, data):
    """Écrit dans un fichier temporaire puis le remplace : le fichier n'est jamais à moitié écrit."""
    chemin = Path(chemin)
    tmp = chemin.with_name(chemin.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    if chemin.exists():
        shutil.copy2(chemin, str(chemin) + ".bak")
    os.replace(tmp, chemin)


def charger_existants(chemin=SORTIE):
    """{mot: numéro}. Un ancien fichier en liste est converti."""
    data = lire_json(chemin, {})
    if isinstance(data, list):
        return {m: i for i, m in enumerate(data)}
    return data


_VERROUS = []                       # on garde les fichiers ouverts : le verrou dure tant que le programme tourne


def verrouiller(nom):
    """Empêche de lancer deux fois la même collecte (elles s'écraseraient). False si déjà lancée ailleurs.
    Le verrou disparaît tout seul à la fermeture du programme, même après un plantage."""
    f = open(DONNEES / f".verrou_{nom}", "a+")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _VERROUS.append(f)
    return True


def ajouter(ids, mots):
    """Les mots nouveaux reçoivent les numéros suivants (les anciens ne changent jamais)."""
    prochain = max(ids.values(), default=-1) + 1
    ajoutes = 0
    for m in sorted(set(mots) - ids.keys()):
        if prochain >= CAPACITE:
            break
        ids[m] = prochain
        prochain += 1
        ajoutes += 1
    return ajoutes


def sauver(ids):
    ecrire_json(SORTIE, ids)


# =============================================
# ==== Sources de mots : chacune donne un lot de mots à chaque appel
# =============================================
def mots_de(texte):
    return [m.lower() for m in MOT.findall(texte.replace("’", "'")) if 2 <= len(m) <= 30]


class Source:
    """Une source de mots. suivant() renvoie une liste de mots ; fini passe à True quand elle n'a plus rien."""
    fiable = True       # True : les mots entrent dans le dictionnaire tout de suite

    def __init__(self, nom, etat):
        self.nom, self.etat, self.fini = nom, etat, False
        self.pause = 0.0


class Hunspell(Source):
    def suivant(self):
        contenu = telecharger(SOURCE_DICO).decode("utf-8", errors="ignore")
        mots = {ligne.split("/")[0].strip().lower() for ligne in contenu.splitlines()[1:]}
        self.fini = True
        return [m for m in mots if m and MOT.fullmatch(m)]


class FormesConjuguees(Source):
    def suivant(self):
        contenu = telecharger(SOURCE_FORMES, timeout=120).decode("utf-8", errors="ignore")
        self.fini = True
        return [m for m in (l.strip().lower() for l in contenu.splitlines()) if m and MOT.fullmatch(m)]


class Wiktionnaire(Source):
    """Toutes les entrées d'une catégorie du Wiktionnaire français, 500 par requête, en reprenant au curseur."""

    def __init__(self, categorie, etat):
        super().__init__("wiktionnaire:" + categorie.split(":", 1)[1], etat)
        self.categorie = categorie
        self.pause = PAUSE_ENTRE_REQUETES
        self.fini = bool(etat["curseurs"].get(self.nom) == "fini")

    def suivant(self):
        url = ("https://fr.wiktionary.org/w/api.php?action=query&list=categorymembers&format=json"
               "&cmnamespace=0&cmlimit=500&cmtitle=" + urllib.parse.quote(self.categorie))
        curseur = self.etat["curseurs"].get(self.nom)
        if curseur:
            url += "&cmcontinue=" + urllib.parse.quote(curseur)
        data = api_json(url)
        membres = data.get("query", {}).get("categorymembers", [])
        suite = data.get("continue", {}).get("cmcontinue")
        self.etat["curseurs"][self.nom] = suite if suite else "fini"
        self.fini = not suite
        return [m["title"].lower() for m in membres if MOT.fullmatch(m["title"])]


class TexteAuHasard(Source):
    """Articles au hasard d'un site Wikimédia : source sans fin. Un mot n'entre qu'après plusieurs sightings."""
    fiable = False

    def __init__(self, site, etat):
        super().__init__("texte:" + site, etat)
        self.site = site
        self.pause = PAUSE_ENTRE_REQUETES

    def suivant(self):
        url = (f"https://{self.site}/w/api.php?action=query&format=json&generator=random&grnnamespace=0"
               "&grnlimit=20&prop=extracts&exintro=1&explaintext=1&exlimit=20")
        pages = api_json(url).get("query", {}).get("pages", {}).values()
        return mots_de(" ".join(p.get("extract", "") for p in pages))


class TousLesArticles(Source):
    """Scan complet d'un site Wikimédia : tous les articles, dans l'ordre alphabétique, 20 par requête.
    Le curseur est sauvegardé : après un arrêt il repart exactement de là."""
    fiable = False

    def __init__(self, site, etat):
        super().__init__("scan:" + site, etat)
        self.site = site
        self.pause = PAUSE_ENTRE_REQUETES
        self.fini = etat["curseurs"].get(self.nom) == "fini"

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


class FichiersConversations(Source):
    """Les mots de tes fichiers conversations*.txt (relus à chaque démarrage)."""

    def suivant(self):
        mots = []
        for fichier in sorted(DIR.glob("conversations*.txt")) + sorted((DIR / "conv").glob("conversations*.txt")):
            if fichier.name.startswith("conversations_web"):
                continue                                         # les dialogues web passent par les « textes » (2 sightings)
            mots += mots_de(fichier.read_text(encoding="utf-8", errors="ignore"))
        mots += list(EXTRAS)
        self.fini = True
        return mots


class DialoguesWeb(Source):
    """Les mots des dialogues récupérés par dialogues.py : comme un texte, un mot entre après 2 sightings."""
    fiable = False

    def suivant(self):
        mots = []
        for fichier in sorted((DIR / "conv").glob("conversations_web*.txt")) + sorted(DIR.glob("conversations_web*.txt")):
            mots += mots_de(fichier.read_text(encoding="utf-8", errors="ignore"))
        self.fini = True
        return mots


# =============================================
# ==== Boucle principale
# =============================================
def construire_sources(etat):
    sources = [FichiersConversations("conversations", etat), DialoguesWeb("dialogues web", etat)]
    if not etat["fait"].get("hunspell"):
        sources.append(Hunspell("hunspell", etat))
    if not etat["fait"].get("formes"):
        sources.append(FormesConjuguees("formes", etat))
    sources += [Wiktionnaire(c, etat) for c in CATEGORIES_WIKTIONNAIRE]
    sources += [TousLesArticles(s, etat) for s in SITES_TEXTE]    # le scan complet, reprend où il s'était arrêté
    sources += [TexteAuHasard(s, etat) for s in SITES_TEXTE]      # ne finit jamais : le programme est sans fin
    return sources


def entrer(ids, candidats, mots, fiable):
    """Fait entrer des mots dans le dictionnaire. Renvoie le nombre de mots nouveaux."""
    if fiable:
        return ajouter(ids, mots)
    acceptes = []
    for m in mots:
        if m in ids:
            continue
        candidats[m] = candidats.get(m, 0) + 1
        if candidats[m] >= VUES_POUR_ENTRER:
            acceptes.append(m)
            del candidats[m]
    if len(candidats) > 1_500_000:                           # on ne garde pas tout : on oublie les mots vus une fois
        for m in [m for m, n in candidats.items() if n < 2]:
            del candidats[m]
    return ajouter(ids, acceptes)


def main():
    args = sys.argv[1:]
    fin = time.time() + float(args[args.index("--minutes") + 1]) * 60 if "--minutes" in args else None

    if not verrouiller("mots"):
        print("Le récupérateur de mots tourne déjà dans une autre fenêtre : celle-ci se ferme.", flush=True)
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
    print(f"Mots déjà présents : {len(ids)}. Ctrl+C pour arrêter (tout est sauvegardé).", flush=True)

    def sauvegarder():
        sauver(ids)
        ecrire_json(ETAT, etat)

    try:
        while fin is None or time.time() < fin:
            actives = [s for s in sources if not s.fini]
            for source in actives:                             # toutes les sources à tour de rôle (dico ET textes)
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
                nouveaux = entrer(ids, candidats, mots, source.fiable)
                par_source[source.nom] += nouveaux
                if source.fini and source.nom in ("hunspell", "formes"):
                    etat["fait"][source.nom] = True
                if len(ids) >= CAPACITE:
                    print(f"Dictionnaire plein ({CAPACITE} mots) : arrêt.", flush=True)
                    return
                if time.time() - derniere_sauvegarde >= SAUVER_TOUS:
                    sauvegarder()
                    derniere_sauvegarde = time.time()
                if time.time() - dernier_affichage >= 20:
                    detail = ", ".join(f"{n.split(':')[-1][:14]} +{c}" for n, c in par_source.most_common(4))
                    print(f"  {len(ids)} mots (+{len(ids) - depart})  [{detail}]", flush=True)
                    dernier_affichage = time.time()
                time.sleep(source.pause)
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        sauvegarder()
        print(f"Écrit : {len(ids)} mots (+{len(ids) - depart} cette fois) dans {SORTIE.name}", flush=True)


if __name__ == "__main__":
    main()
