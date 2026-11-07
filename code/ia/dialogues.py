"""Récupérateur de dialogues français sur internet, sans fin.

Il écrit des paires « question | réponse » dans conversations_web_*.txt (un fichier par source, que tu
peux supprimer si une source ne te plaît pas). L'IA les lit à l'entraînement, en plus de tes
conversations.txt. Comme mots.py : il ne plante jamais, reprend où il s'était arrêté (etat_dialogues.json),
et attend tout seul si internet coupe.

Sources (toutes publiques, avec une licence qui permet de s'en servir) :
  1. OpenAssistant oasst2 : vraies conversations écrites par des humains bénévoles (licence Apache 2.0).
  2. CATIE-AQ/everyday-conversations : conversations de tous les jours (licence Apache 2.0). Elles ont été
     écrites par le modèle Llama 3.1 de Meta, pas par des humains.
  3. Livres français du domaine public (Project Gutenberg) : les dialogues des romans.

Seules les paires courtes et propres sont gardées (l'IA ne voit que 64 mots à la fois).

Usage: python dialogues.py              (sans fin)
       python dialogues.py --minutes 30 (s'arrête après 30 minutes)
"""
import gzip
import json
import re
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import mots as base   # réseau robuste, fichiers écrits sans risque

DIR = Path(__file__).resolve().parent
DIR_CONV = DIR / "conv"             # les fichiers de conversations vivent ici
DIR_CONV.mkdir(exist_ok=True)
DONNEES = DIR / "donnees"          # états de collecte
ETAT = DONNEES / "etat_dialogues.json"
MAX_MOTS_QUESTION = 25
MAX_MOTS_REPONSE = 40
MAX_TOKENS = 56                     # question + réponse ; le modèle voit 64 mots à la fois
PAUSE = 1.0
SAUVER_TOUS = 120
RELIRE_APRES = 3600                 # quand tout est collecté : nouvelle vérification après 1 h

URL_OASST2 = "https://huggingface.co/datasets/OpenAssistant/oasst2/resolve/main/2023-11-05_oasst2_ready.trees.jsonl.gz"
DATASET_QUOTIDIEN = "CATIE-AQ/everyday-conversations-llama3.1-2k-in-french"
GROS_MOTS = {
    "putain", "merde", "con", "connard", "connasse", "salope", "enculé", "encule", "bite", "couille", "couilles",
    "nique", "niquer", "pute", "foutre", "bordel", "chier", "cul", "baiser", "branler", "pd", "nazi",
}
TOKEN = re.compile(r"\w+(?:['’-]\w+)*|[.,;:!?]")
NARRATION = re.compile(
    r"\b(?:dit|dis|fit|fait|répond|répondit|demanda|demande|s['’]écria|reprit|reprend|murmura|ajouta|répliqua|cria|"
    r"observa|continua|interrompit|poursuivit)\b[-\s]+(?:il|elle|je|on|ils|elles|mon|ma|le|la|l['’]|d['’]|de|du|[A-ZÉÈ])")


# =============================================
# ==== Nettoyage et filtres
# =============================================
def nettoyer(texte):
    texte = re.sub(r"```.*?```", " ", texte, flags=re.S)           # blocs de code
    texte = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", " ", texte)  # adresses
    texte = re.sub(r"[*_#>`~\[\]{}<>|\\]", " ", texte)              # restes de mise en forme
    texte = texte.replace(" / ", ", ")
    return " ".join(texte.split())


def tronquer(texte, max_mots):
    """Garde les premières phrases entières tant qu'elles tiennent dans max_mots ; '' si la 1re est trop longue."""
    phrases = re.split(r"(?<=[.!?])\s+", texte)
    gardees, total = [], 0
    for phrase in phrases:
        n = len(TOKEN.findall(phrase))
        if total + n > max_mots:
            break
        gardees.append(phrase)
        total += n
    return " ".join(gardees)


def valide(question, reponse):
    """(question, réponse) nettoyées si la paire est bonne pour l'entraînement, sinon None."""
    q, r = nettoyer(question), tronquer(nettoyer(reponse), MAX_MOTS_REPONSE)
    if not q or not r or q.lower() == r.lower():
        return None
    nq, nr = len(TOKEN.findall(q)), len(TOKEN.findall(r))
    if nq < 1 or nq > MAX_MOTS_QUESTION or nr < 2 or nq + nr > MAX_TOKENS:
        return None
    if GROS_MOTS & {m.lower() for m in re.findall(r"\w+", q + " " + r)}:
        return None
    lettres = sum(c.isalpha() for c in q + r)
    if lettres < 0.7 * len(q + r):                                  # trop de chiffres ou de symboles
        return None
    return q, r


# =============================================
# ==== Sources : suivant() renvoie une liste de paires (question, réponse)
# =============================================
class Source:
    def __init__(self, nom, fichier, etat):
        self.nom, self.fichier, self.etat, self.fini = nom, DIR_CONV / fichier, etat, False
        self.pause = PAUSE


class OpenAssistant(Source):
    """Les arbres de conversation d'oasst2 : on garde les réponses de l'assistant aux questions en français."""

    def __init__(self, etat):
        super().__init__("oasst2", "conversations_web_oasst.txt", etat)
        self.fini = bool(etat["fait"].get("oasst2"))

    def suivant(self):
        print("  [oasst2] téléchargement des conversations (54 Mo), patience...", flush=True)
        brut = gzip.decompress(base.telecharger(URL_OASST2, essais=4, timeout=900))
        paires = []

        def parcourir(noeud, parent):
            if (parent and parent.get("role") == "prompter" and noeud.get("role") == "assistant"
                    and noeud.get("lang") == "fr" and parent.get("lang") == "fr"
                    and not noeud.get("deleted") and noeud.get("rank") in (0, None)):
                paires.append((parent["text"], noeud["text"]))
            for fils in noeud.get("replies", []):
                parcourir(fils, noeud)

        for ligne in brut.decode("utf-8", errors="ignore").splitlines():
            if ligne.strip():
                parcourir(json.loads(ligne)["prompt"], None)
        self.etat["fait"]["oasst2"] = True
        self.fini = True
        return paires


class ConversationsQuotidiennes(Source):
    """everyday-conversations : 100 conversations par requête, chaque tour de l'utilisateur et la réponse."""

    def __init__(self, etat):
        super().__init__("quotidien", "conversations_web_quotidien.txt", etat)
        self.fini = bool(etat["fait"].get("quotidien"))

    def suivant(self):
        curseur = self.etat["curseurs"].setdefault("quotidien", {"split": "train", "offset": 0})
        url = ("https://datasets-server.huggingface.co/rows?dataset=" + urllib.parse.quote(DATASET_QUOTIDIEN)
               + f"&config=default&split={curseur['split']}&offset={curseur['offset']}&length=100")
        try:
            data = json.loads(base.telecharger(url).decode("utf-8"))
            lignes = data.get("rows", [])
        except base.ErreurReseau:
            lignes = []                                              # fin du jeu de données (ou page absente)
        paires = []
        for ligne in lignes:
            messages = ligne["row"]["messages"]
            for i in range(len(messages) - 1):
                if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
                    paires.append((messages[i]["content"], messages[i + 1]["content"]))
        if len(lignes) < 100:
            if curseur["split"] == "train":
                curseur["split"], curseur["offset"] = "test", 0
            else:
                self.etat["fait"]["quotidien"] = True
                self.fini = True
        else:
            curseur["offset"] += 100
        return paires


class LivresGutenberg(Source):
    """Les livres français du domaine public (via gutendex.com) : on garde les répliques qui se suivent."""

    def __init__(self, etat):
        super().__init__("livres", "conversations_web_livres.txt", etat)
        self.pause = 2.0
        self.etat["curseurs"].setdefault("livres", {"page": "https://gutendex.com/books?languages=fr", "attente": [], "faits": 0})
        self.fini = bool(etat["fait"].get("livres"))

    def suivant(self):
        c = self.etat["curseurs"]["livres"]
        if not c["attente"]:
            if not c["page"]:
                self.etat["fait"]["livres"] = True
                self.fini = True
                return []
            page = json.loads(base.telecharger(c["page"]).decode("utf-8"))
            c["attente"] = [
                [b["id"], next((u for k, u in b["formats"].items() if k.startswith("text/plain")), None)]
                for b in page.get("results", [])
            ]
            c["page"] = page.get("next")
        numero, adresse = c["attente"].pop(0)
        c["faits"] += 1
        if not adresse:
            return []
        try:
            texte = base.telecharger(adresse, essais=3, timeout=120).decode("utf-8", errors="ignore")
        except base.ErreurReseau:
            return []                                                # un livre introuvable : on passe au suivant
        return self.repliques(texte)

    @staticmethod
    def repliques(texte):
        """Paires de répliques consécutives (paragraphes commençant par un tiret ou un guillemet)."""
        debut, fin = texte.find("*** START"), texte.find("*** END")
        if debut >= 0:
            texte = texte[texte.find("\n", debut):fin if fin > debut else len(texte)]
        tours = []
        for p in re.split(r"\n\s*\n", texte):
            p = " ".join(p.split())
            if p.startswith(("—", "–", "- ")):
                t = re.split(r"\s[—–]\s", p.lstrip("—–- ").strip(), maxsplit=1)[0]   # coupe avant la narration
            elif p.startswith("«"):
                t = p[1:].split("»")[0]
            else:
                tours.append(None)
                continue
            t = re.sub(r",?\s*(?:dit|répondit|demanda|fit|s'écria|reprit|murmura|ajouta)-(?:il|elle|je|on)[^.!?]*", "", t).strip()
            # une réplique qui garde de la narration (« dit d'Artagnan », « fit Milady »...) est abandonnée
            if NARRATION.search(t) or re.search(r"[«»:]|--", t):
                tours.append(None)
            else:
                tours.append(t if t and t[-1] in ".!?" else None)
        return [(a, b) for a, b in zip(tours, tours[1:]) if a and b]


# =============================================
# ==== Boucle principale
# =============================================
def lire_existantes():
    """Paires déjà écrites (pour ne jamais écrire deux fois la même)."""
    connues = set()
    for fichier in list(DIR_CONV.glob("conversations_web*.txt")) + list(DIR.glob("conversations_web*.txt")):
        for ligne in fichier.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "|" in ligne and not ligne.startswith("#"):
                connues.add(ligne.strip().lower())
    return connues


def ecrire(source, paires, connues):
    """Ajoute les paires valides et nouvelles au fichier de la source. Renvoie le nombre écrit."""
    lignes = []
    for question, reponse in paires:
        paire = valide(question, reponse)
        if paire is None:
            continue
        ligne = f"{paire[0]} | {paire[1]}"
        if ligne.lower() not in connues:
            connues.add(ligne.lower())
            lignes.append(ligne)
    if lignes:
        nouveau = not source.fichier.exists()
        with open(source.fichier, "a", encoding="utf-8") as f:
            if nouveau:
                f.write("# Dialogues récupérés sur internet par dialogues.py (une ligne = question | réponse)\n")
            f.write("\n".join(lignes) + "\n")
    return len(lignes)


def main():
    args = sys.argv[1:]
    fin = time.time() + float(args[args.index("--minutes") + 1]) * 60 if "--minutes" in args else None
    choix = args[args.index("--source") + 1].split(",") if "--source" in args else None
    inconnues = set(choix or []) - {"quotidien", "oasst2", "livres"}
    if inconnues:
        print(f"Source inconnue : {inconnues}. Choix : quotidien, oasst2, livres.", flush=True)
        return
    nom = "_".join(sorted(choix)) if choix else "tout"
    if not base.verrouiller("dialogues_" + nom):
        print(f"La collecte « {nom} » tourne déjà dans une autre fenêtre : celle-ci se ferme.", flush=True)
        return
    # un fichier d'état par choix de sources, pour que plusieurs fenêtres ne s'écrasent jamais
    fichier_etat = ETAT if not choix else DONNEES / f"etat_dialogues_{nom}.json"
    etat = base.lire_json(fichier_etat, None)
    if etat is None:
        etat = base.lire_json(ETAT, {})                              # reprend l'ancien état commun
    etat.setdefault("curseurs", {})
    etat.setdefault("fait", {})
    sources = [ConversationsQuotidiennes(etat), OpenAssistant(etat), LivresGutenberg(etat)]
    if choix:
        sources = [s for s in sources if s.nom in choix]
    connues = lire_existantes()
    total, derniere_sauvegarde = Counter(), time.time()
    print(f"{len(connues)} paires déjà récupérées. Ctrl+C pour arrêter (tout est sauvegardé).", flush=True)
    try:
        while fin is None or time.time() < fin:
            actives = [s for s in sources if not s.fini]
            if not actives and not any(s.nom == "livres" for s in sources):
                print("Tout est collecté pour cette source.", flush=True)
                break
            if not actives:
                print(f"Tout est collecté. Nouvelle vérification dans {RELIRE_APRES // 60} minutes...", flush=True)
                for s in sources:                                    # de nouveaux livres peuvent apparaître
                    if s.nom == "livres":
                        etat["fait"].pop("livres", None)
                        etat["curseurs"]["livres"] = {"page": "https://gutendex.com/books?languages=fr", "attente": [], "faits": 0}
                        s.fini = False
                time.sleep(RELIRE_APRES)
                continue
            for source in actives:
                if fin is not None and time.time() >= fin:
                    break
                try:
                    paires = source.suivant()
                except base.ErreurReseau as e:
                    print(f"  [{source.nom}] pas de réponse ({e}) : pause de 60 s", flush=True)
                    time.sleep(60)
                    continue
                except Exception as e:                               # une source qui bogue ne doit jamais tout arrêter
                    print(f"  [{source.nom}] erreur {type(e).__name__}: {e}", flush=True)
                    time.sleep(10)
                    continue
                ecrites = ecrire(source, paires, connues)
                total[source.nom] += ecrites
                if source.nom != "livres" or ecrites:
                    print(f"  [{source.nom}] +{ecrites} paires (total {dict(total)})", flush=True)
                if time.time() - derniere_sauvegarde >= SAUVER_TOUS or source.fini:
                    base.ecrire_json(fichier_etat, etat)
                    derniere_sauvegarde = time.time()
                time.sleep(source.pause)
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        base.ecrire_json(fichier_etat, etat)
        print(f"Terminé : {dict(total)} paires ajoutées cette fois.", flush=True)


if __name__ == "__main__":
    main()
