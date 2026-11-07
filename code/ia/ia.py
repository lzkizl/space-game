"""IA de discussion entraînée de zéro avec PyTorch (mini GPT: Transformer décodeur, mot par mot).

Elle apprend sur corpus.txt (texte Wikipédia, voir corpus.py) et sur les conversations de
conv/conversations*.txt (écrites à la main) et conv/conversations_web_*.txt (récupérées sur internet par
dialogues.py), puis génère ses réponses mot par mot.

Usage: python ia.py            -> discute (entraîne d'abord si besoin)
       python ia.py --train    -> réentraîne de zéro (ajoute --minutes N pour la durée, 10 par défaut)
       python ia.py --continu  -> tourne sans fin: collecte du texte puis continue d'entraîner le même modèle
                                  (--cycle N = minutes d'entraînement entre deux collectes, 20 par défaut)
       Ajoute --lang en pour l'IA anglaise (modele_gpt_en.pt, conv_en/, corpus_en.txt, mots_anglais.json) ;
       --lang fr (par défaut) pour la française. Dans le jeu, la langue se choisit dans Paramètres.
"""
import difflib
import json
import math
import os
import random
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime

import torch
import torch.nn as nn

from savoir import repondre as repondre_savoir

DIR = os.path.dirname(os.path.abspath(__file__))
DONNEES = os.path.join(DIR, "donnees")   # corpus, vocabulaires, états de collecte
MODELES = os.path.join(DIR, "modeles")   # modèles entraînés (.pt)
os.makedirs(DONNEES, exist_ok=True)
os.makedirs(MODELES, exist_ok=True)
CONV_PATH = os.path.join(DIR, "conversations.txt")
CORPUS_PATH = os.path.join(DONNEES, "corpus.txt")
MOTS_PATH = os.path.join(DONNEES, "mots_francais.json")
MODEL_PATH = os.path.join(MODELES, "modele_gpt.pt")

TAILLE_VOCAB = 8000   # mots les plus fréquents gardés par le modèle
CONTEXTE = 64         # nombre de mots que le modèle voit en même temps
SEQ = CONTEXTE        # longueur des séquences d'entraînement
DELAI_ECRITURE = 300  # secondes minimum entre deux écritures du modèle sur le disque
REPETITIONS = 8       # combien de fois les conversations sont répétées dans l'entraînement
SEUIL_MEMOIRE = 0.65  # ressemblance minimale (0 à 1) avec une question connue pour renvoyer sa réponse écrite
SPECIAUX = ["<pad>", "<unk>", "<nl>", "<fin>", "<heure>"]
TOKEN = re.compile(r"<[a-z]+>|[a-zàâäéèêëîïôöùûüÿçœæ]+(?:[-'][a-zàâäéèêëîïôöùûüÿçœæ]+)*|[.,;:!?]")


def tokenize(texte):
    return TOKEN.findall(texte.lower().replace("’", "'").replace("__heure__", "<heure>"))


DOSSIER_CONV = os.path.join(DIR, "conv")   # les fichiers de conversations vivent ici (et à côté de ia.py)
MAX_WEB = {"livres": 6000}                 # paires gardées par source web (les romans sont moins fiables)
MAX_WEB_DEFAUT = 25000

# Une IA par langue : chacune a son modèle, son vocabulaire, son texte Wikipédia et ses conversations.
LANGUES = {
    "fr": {"conv": "conv", "mots": "mots_francais.json", "modele": "modele_gpt.pt", "corpus": "corpus.txt",
           "wiki": "fr.wikipedia.org", "incompris": "Je n'ai pas bien compris, peux-tu reformuler ?"},
    "en": {"conv": "conv_en", "mots": "mots_anglais.json", "modele": "modele_gpt_en.pt", "corpus": "corpus_en.txt",
           "wiki": "en.wikipedia.org", "incompris": "I didn't quite understand, could you rephrase that?"},
}
langue = "fr"
_memoire = None


def definir_langue(code):
    """Passe l'IA en français ("fr") ou en anglais ("en") : change le modèle, le vocabulaire, le corpus et
    les conversations utilisés. Sans effet si la langue est déjà celle-là."""
    global langue, _memoire, DOSSIER_CONV, CORPUS_PATH, MOTS_PATH, MODEL_PATH, INCOMPRIS
    if code not in LANGUES:
        raise ValueError(f"langue inconnue : {code!r} (choisis parmi {', '.join(LANGUES)})")
    langue = code
    cfg = LANGUES[code]
    DOSSIER_CONV = os.path.join(DIR, cfg["conv"])
    CORPUS_PATH = os.path.join(DONNEES, cfg["corpus"])
    MOTS_PATH = os.path.join(DONNEES, cfg["mots"])
    MODEL_PATH = os.path.join(MODELES, cfg["modele"])
    INCOMPRIS = cfg["incompris"]
    _memoire = None   # la mémoire des conversations est reconstruite dans la nouvelle langue


def fichiers_conversations(web):
    """Fichiers conversations*.txt de conv/ et du dossier de ia.py. web=True : seulement ceux récupérés
    sur internet par dialogues.py (conversations_web_*.txt) ; web=False : ceux écrits à la main."""
    fichiers = []
    for dossier in (DOSSIER_CONV, DIR) if langue == "fr" else (DOSSIER_CONV,):
        if os.path.isdir(dossier):
            for nom in sorted(os.listdir(dossier)):
                if nom.startswith("conversations") and nom.endswith(".txt") and nom.startswith("conversations_web") == web:
                    fichiers.append(os.path.join(dossier, nom))
    return fichiers


def lire_paires(chemin):
    paires = []
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            if ligne.startswith("#") or "|" not in ligne:
                continue
            qs, rs = ligne.split("|", 1)
            paires += [(q.strip(), r.strip()) for q in qs.split(" / ") for r in rs.split(" / ")]
    return paires


def dialogues():
    """Liste de (question, réponse) écrites à la main : conversations.txt, conversations_2.txt, etc."""
    return [p for chemin in fichiers_conversations(web=False) for p in lire_paires(chemin)]


def dialogues_web():
    """Paires récupérées sur internet par dialogues.py (conversations_web_*.txt), limitées par source."""
    paires = []
    for chemin in fichiers_conversations(web=True):
        source = os.path.basename(chemin)[len("conversations_web_"):-len(".txt")]
        lues = lire_paires(chemin)
        limite = MAX_WEB.get(source, MAX_WEB_DEFAUT)
        if len(lues) > limite:
            lues = random.Random(0).sample(lues, limite)
        paires += lues
    return paires


def toutes_les_paires():
    return dialogues() + dialogues_web()


FIN_PHRASE = {".", "!", "?"}
# mots après lesquels une phrase ne peut pas s'arrêter (« Le chat est un », « Je vais à »)
OUVRANTS = {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "et", "ou", "à", "au", "aux", "en", "que", "qui",
            "dans", "pour", "par", "sur", "avec", "ce", "se", "ne", "ma", "mon", "mes", "ta", "ton", "tes", "sa", "son",
            "ses", "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "mais", "donc", "car", "si", "comme",
            "est", "sont", "a", "ont", "très", "plus", "pas", ",", ";", ":"}


def echange(question, reponse):
    mots = tokenize(reponse)
    if mots and mots[-1] not in FIN_PHRASE:
        mots.append(".")   # toute réponse finit par un point : le modèle apprend à finir ses phrases
    return ["<nl>", "toi", ":"] + tokenize(question) + ["<nl>", "ia", ":"] + mots + ["<fin>"]


def sans_accents(texte):
    texte = unicodedata.normalize("NFD", texte)
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def variantes(question):
    """La même question écrite de plusieurs façons (avec ou sans accents, avec ou sans « ? »),
    pour que le modèle comprenne comment les gens écrivent vraiment."""
    base = question.strip()
    ecritures = {base, sans_accents(base)}
    ecritures |= {q + " ?" for q in list(ecritures) if not q.endswith("?")}
    return ecritures


def normaliser(texte):
    """Mots d'un texte en minuscules et sans accents (pour comparer deux questions)."""
    return re.findall(r"[a-z0-9]+", sans_accents(texte.lower().replace("’", "'")))


class Memoire:
    """Les questions de conversations*.txt. Si on pose une question connue (même avec des fautes de
    frappe, sans accents ou avec un point d'interrogation en plus), elle renvoie la réponse écrite :
    c'est exact à chaque fois, contrairement au modèle qui devine mot par mot."""

    def __init__(self, paires):
        self.reponses = defaultdict(list)
        for question, reponse in paires:
            cle = tuple(normaliser(question))
            if cle:
                self.reponses[cle].append(reponse)
        self.cles = list(self.reponses)
        frequence = Counter(m for cle in self.cles for m in set(cle))
        n = len(self.cles)
        # un mot rare dans les questions (« chat ») compte plus qu'un mot courant (« quoi »)
        self.idf = {m: math.log((n + 1) / (c + 1)) + 1 for m, c in frequence.items()}
        self.inconnu = math.log(n + 1) + 1  # poids d'un mot qui n'apparaît dans aucune question
        self.mots = list(self.idf)
        self.index = defaultdict(list)       # mot -> numéros des questions qui le contiennent
        for i, cle in enumerate(self.cles):
            for m in set(cle):
                self.index[m].append(i)
        self.normes = [math.sqrt(sum(self.idf[m] ** 2 for m in set(cle))) for cle in self.cles]

    def _corriger(self, mot):
        """Corrige une faute de frappe : renvoie le mot connu le plus proche (« bonjoure » -> « bonjour »)."""
        if mot in self.idf:
            return mot
        proche = difflib.get_close_matches(mot, self.mots, n=1, cutoff=0.8)
        return proche[0] if proche else mot

    def chercher(self, question):
        """(ressemblance de 0 à 1, question connue la plus proche ou None)."""
        mots = {self._corriger(m) for m in normaliser(question)}
        if not mots:
            return 0.0, None
        poids = {m: self.idf.get(m, self.inconnu) for m in mots}
        norme = math.sqrt(sum(p * p for p in poids.values()))
        scores = Counter()
        for m in mots:
            for i in self.index.get(m, ()):
                scores[i] += poids[m] * self.idf[m]
        if not scores:
            return 0.0, None
        meilleur = max(scores, key=lambda i: scores[i] / (norme * self.normes[i]))
        return scores[meilleur] / (norme * self.normes[meilleur]), self.cles[meilleur]

    def repondre(self, question):
        """Réponse écrite de la question connue la plus proche, ou None si aucune ne ressemble assez."""
        score, cle = self.chercher(question)
        if cle is None or score < SEUIL_MEMOIRE:
            return None
        reponse = random.choice(self.reponses[cle])
        return reponse.replace("<heure>", datetime.now().strftime("%H:%M"))


def memoire():
    """La mémoire des conversations (construite une seule fois)."""
    global _memoire
    if _memoire is None:
        _memoire = Memoire(dialogues())
    return _memoire


class Bloc(nn.Module):
    """Un bloc Transformer: auto-attention (chaque mot regarde les mots d'avant) puis petit réseau MLP."""

    def __init__(self, dim, tetes, dropout):
        super().__init__()
        self.ln1 = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(dim, tetes, dropout=dropout, batch_first=True)
        self.ln2 = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(nn.Linear(dim, 4 * dim), nn.GELU(), nn.Linear(4 * dim, dim), nn.Dropout(dropout))

    def forward(self, x, masque):
        h = self.ln1(x)
        x = x + self.attn(h, h, h, attn_mask=masque, need_weights=False)[0]
        return x + self.mlp(self.ln2(x))


class Modele(nn.Module):
    """Mini GPT: même architecture que les grands modèles (Transformer décodeur, attention causale)."""

    def __init__(self, n_vocab, dim=256, couches=4, tetes=4, dropout=0.1):
        super().__init__()
        self.emb = nn.Embedding(n_vocab, dim)
        self.pos = nn.Embedding(CONTEXTE, dim)
        self.drop = nn.Dropout(dropout)
        self.blocs = nn.ModuleList(Bloc(dim, tetes, dropout) for _ in range(couches))
        self.ln = nn.LayerNorm(dim)
        self.sortie = nn.Linear(dim, n_vocab, bias=False)
        self.sortie.weight = self.emb.weight   # mêmes poids pour lire et écrire les mots
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.zeros_(m.bias)

    def forward(self, x, h=None):
        T = x.size(1)
        masque = torch.triu(torch.ones(T, T, dtype=torch.bool), diagonal=1)   # interdit de voir le futur
        y = self.drop(self.emb(x) + self.pos(torch.arange(T)))
        for bloc in self.blocs:
            y = bloc(y, masque)
        return self.sortie(self.ln(y)), None


def construire_vocab(textes_corpus, paires, paires_web=()):
    """Mots du corpus qui existent vraiment en français (mots_francais.json) + tous les mots de tes
    conversations. Les mots des dialogues web ne comptent que s'ils sont fréquents (le vocabulaire reste de
    TAILLE_VOCAB mots)."""
    with open(MOTS_PATH, encoding="utf-8") as f:
        dico = json.load(f)
    freq = Counter(m for t in textes_corpus for m in tokenize(t))
    for q, r in paires_web:
        freq.update(tokenize(q) + tokenize(r))
    mots = set(SPECIAUX) | {",", ".", ";", ":", "!", "?", "toi", "ia"}
    for q, r in paires:
        mots.update(tokenize(q) + tokenize(r))
    gardes = [m for m, _ in freq.most_common() if m in dico and m not in mots]
    mots.update(gardes[: max(0, TAILLE_VOCAB - len(mots))])
    return SPECIAUX + sorted(mots - set(SPECIAUX))


def lire_corpus():
    if not os.path.exists(CORPUS_PATH):
        return []
    with open(CORPUS_PATH, encoding="utf-8") as f:
        return [l for l in f.read().splitlines() if l]


def collecter(requetes):
    """Ajoute de nouveaux articles Wikipédia à corpus.txt (sans doublons). Renvoie le nombre ajouté."""
    import corpus as wiki
    connus = set(lire_corpus())
    ajoutes = 0
    with open(CORPUS_PATH, "a", encoding="utf-8") as f:
        for _ in range(requetes):
            try:
                for texte in wiki.articles(LANGUES[langue]["wiki"]):
                    if texte not in connus:
                        connus.add(texte)
                        f.write(texte + "\n")
                        ajoutes += 1
            except Exception:
                time.sleep(5)   # Wikipédia limite le débit
                continue
            time.sleep(1)
    return ajoutes


def sequences(docs, index):
    unk = index["<unk>"]
    flux = torch.tensor([index.get(m, unk) for d in docs for m in d])
    n = (len(flux) - 1) // SEQ
    if n <= 0:
        return torch.zeros(0, SEQ, dtype=torch.long), torch.zeros(0, SEQ, dtype=torch.long)
    return flux[: n * SEQ].view(n, SEQ), flux[1: n * SEQ + 1].view(n, SEQ)


def preparer(vocab):
    """Entraînement + validation. La validation = conversations et articles que le modèle ne voit JAMAIS
    pendant l'apprentissage, pour mesurer s'il comprend vraiment ou s'il apprend par cœur."""
    index = {m: i for i, m in enumerate(vocab)}
    paires, corpus = dialogues(), lire_corpus()
    val_p, train_p = paires[::20], [p for i, p in enumerate(paires) if i % 20]
    val_c, train_c = corpus[::30], [t for i, t in enumerate(corpus) if i % 30]

    conversations = [echange(v, r) for q, r in train_p for v in variantes(q)]
    docs = [["<nl>"] + tokenize(t) for t in train_c] + conversations * REPETITIONS
    # dialogues récupérés sur internet : une seule fois chacun, et seulement s'ils sont bien couverts par le
    # vocabulaire (trop de mots inconnus apprendrait au modèle à répondre n'importe quoi)
    inconnu, nb_web = index["<unk>"], 0
    for q, r in dialogues_web():
        if not 4 <= len(tokenize(r)) <= 45:   # ni fragments (« Oui ça va »), ni pavés qui ne tiennent pas dans le contexte
            continue
        doc = echange(q, r)
        if sum(index.get(m, inconnu) == inconnu for m in doc) <= 0.12 * len(doc):
            docs.append(doc)
            nb_web += 1
    random.Random(0).shuffle(docs)
    X, Y = sequences(docs, index)
    Xv, Yv = sequences([["<nl>"] + tokenize(t) for t in val_c] + [echange(q, r) for q, r in val_p], index)
    print(f"{len(corpus)} articles, {len(paires)} échanges, {nb_web} dialogues web -> {len(X)} séquences "
          f"d'entraînement, {len(Xv)} de validation", flush=True)
    return X, Y, Xv, Yv


@torch.no_grad()
def evaluer(model, X, Y):
    if len(X) == 0:
        return float("inf")
    model.eval()
    loss_fn = nn.CrossEntropyLoss()
    total = 0.0
    for k in range(0, len(X), 128):
        sortie, _ = model(X[k: k + 128])
        total += loss_fn(sortie.reshape(-1, sortie.size(-1)), Y[k: k + 128].reshape(-1)).item() * len(X[k: k + 128])
    return total / len(X)


def sauver(etat, vocab):
    torch.save({"state": etat, "vocab": vocab}, MODEL_PATH)


def apprendre(model, vocab, minutes, lr, patience=None):
    """Entraîne `model` pendant `minutes`. Ne sauvegarde que si la validation s'améliore.
    Avec `patience`, s'arrête avant la fin quand il n'a pas progressé pendant ce nombre d'epochs
    (inutile de continuer : il apprendrait ses exemples par cœur)."""
    X, Y, Xv, Yv = preparer(vocab)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    sans_progres = 0
    loss_fn = nn.CrossEntropyLoss()
    meilleur = evaluer(model, Xv, Yv)
    print(f"  validation de départ : {meilleur:.3f}", flush=True)
    fin = time.time() + minutes * 60
    epoch = 0
    meilleur_etat = None      # meilleur modèle, gardé en mémoire
    derniere_ecriture = 0.0   # dernière fois qu'on l'a écrit sur le disque
    try:
        while time.time() < fin:
            epoch += 1
            model.train()
            ordre = torch.randperm(len(X))
            total = 0.0
            for k in range(0, len(X), 64):
                b = ordre[k: k + 64]
                opt.zero_grad()
                sortie, _ = model(X[b])
                loss = loss_fn(sortie.reshape(-1, len(vocab)), Y[b].reshape(-1))
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                total += loss.item() * len(b)
                if time.time() > fin:
                    break
            val = evaluer(model, Xv, Yv)
            if val < meilleur:
                meilleur = val
                meilleur_etat = {k: v.clone() for k, v in model.state_dict().items()}
                note = "meilleur"
                sans_progres = 0
            else:
                sans_progres += 1
                lr = max(lr / 2, 1e-4)   # il n'apprend plus -> on ralentit
                for g in opt.param_groups:
                    g["lr"] = lr
                note = "pas mieux, apprentissage ralenti"
            if meilleur_etat is not None and time.time() - derniere_ecriture >= DELAI_ECRITURE:
                sauver(meilleur_etat, vocab)   # on n'écrit pas le fichier à chaque epoch
                derniere_ecriture, meilleur_etat = time.time(), None
                note += ", écrit sur le disque"
            print(f"epoch {epoch}  entraînement={total / len(X):.3f}  validation={val:.3f}  [{note}]"
                  f"  (reste {max(0, fin - time.time()) / 60:.1f} min)", flush=True)
            if patience and sans_progres >= patience:
                print(f"Pas de progrès depuis {patience} epochs : il n'apprend plus, arrêt.", flush=True)
                break
    finally:
        if meilleur_etat is not None:      # fin ou Ctrl+C : on écrit ce qui n'est pas encore sur le disque
            sauver(meilleur_etat, vocab)
            print("Meilleur modèle écrit sur le disque.", flush=True)
    return meilleur


def entrainer(minutes):
    """Entraînement depuis zéro."""
    vocab = construire_vocab(lire_corpus(), dialogues(), dialogues_web())
    print(f"{len(vocab)} mots dans le vocabulaire")
    torch.manual_seed(0)
    apprendre(Modele(len(vocab)), vocab, minutes, lr=0.001, patience=8)
    print("Terminé.")


def continu(cycle, requetes=40):
    """Tourne sans fin: collecte de nouveaux articles, puis continue d'entraîner le MÊME modèle.
    Plus tu le laisses tourner, plus il a lu de texte. Ctrl+C pour arrêter (le meilleur modèle est déjà sauvegardé)."""
    if os.path.exists(MODEL_PATH):
        model, vocab = charger()
        lr = 0.0003
        print(f"Reprise du modèle existant ({len(vocab)} mots).")
    else:
        vocab = construire_vocab(lire_corpus(), dialogues(), dialogues_web())
        torch.manual_seed(0)
        model, lr = Modele(len(vocab)), 0.001
        print(f"Nouveau modèle ({len(vocab)} mots).")
    n = 0
    try:
        while True:
            n += 1
            print(f"\n=== Cycle {n} : collecte de texte… ===", flush=True)
            print(f"  +{collecter(requetes)} nouveaux articles", flush=True)
            print(f"=== Cycle {n} : entraînement ({cycle} min) ===", flush=True)
            apprendre(model, vocab, cycle, lr)
            lr = 0.0003
    except KeyboardInterrupt:
        print("\nArrêt. Le meilleur modèle est sauvegardé.")


def charger():
    data = torch.load(MODEL_PATH)
    model = Modele(len(data["vocab"]))
    model.load_state_dict(data["state"])
    model.eval()
    return model, data["vocab"]


def recoller(mots):
    texte = " ".join(mots)
    texte = re.sub(r" ([.,;:!?])", r"\1", texte)
    texte = re.sub(r"(\w)'\s", r"\1'", texte)
    texte = re.sub(r"([.!?]) (\w)", lambda m: m[1] + " " + m[2].upper(), texte)   # majuscule après chaque phrase
    return texte[:1].upper() + texte[1:]


OPERATIONS = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b, "/": lambda a, b: a / b}
CALCUL = re.compile(r"(\d+(?:[.,]\d+)?)\s*(\+|-|\*|/|x|×|÷|plus|moins|fois|divisé par|minus|times|divided by)\s*(\d+(?:[.,]\d+)?)")
SYMBOLES = {"x": "*", "×": "*", "÷": "/", "plus": "+", "moins": "-", "fois": "*", "divisé par": "/",
            "minus": "-", "times": "*", "divided by": "/"}


def calculer(question):
    """Calculatrice: répond aux questions comme 'combien font 18 + 5', sinon None."""
    m = CALCUL.search(question.lower())
    if not m:
        return None
    a, op, b = float(m[1].replace(",", ".")), SYMBOLES.get(m[2], m[2]), float(m[3].replace(",", "."))
    if op == "/" and b == 0:
        return "On ne peut pas diviser par zéro !" if langue == "fr" else "You can't divide by zero!"
    res = OPERATIONS[op](a, b)
    virgule = "," if langue == "fr" else "."
    fmt = lambda v: str(int(v)) if v == int(v) else f"{v:.4f}".rstrip("0").replace(".", virgule)
    return f"{fmt(a)} {op} {fmt(b)} = {fmt(res)}"


INCOMPRIS = "Je n'ai pas bien compris, peux-tu reformuler ?"


@torch.no_grad()
def repondre(question, model=None, vocab=None, temperature=0.5, max_mots=60, station=None):
    """1. un calcul -> la calculatrice ; 2. une question sur une constellation -> le savoir (savoir.py) ;
    3. une question connue -> sa réponse écrite (mémoire) ; 4. sinon le modèle invente sa réponse mot par mot
    (sans modèle : « pas compris »). station : nom du vaisseau qui répond (« Orion »), s'il y en a un."""
    calcul = calculer(question)
    if calcul:
        return calcul
    savoir = repondre_savoir(question, station)
    if savoir:
        return savoir
    connue = memoire().repondre(question)
    if connue:
        return connue
    if model is None:
        return INCOMPRIS

    index = {m: i for i, m in enumerate(vocab)}
    amorce = ["<nl>", "toi", ":"] + tokenize(question) + ["<nl>", "ia", ":"]
    ids = [index.get(m, index["<unk>"]) for m in amorce]
    # on tire jusqu'à 4 réponses et on garde la première qui est une vraie phrase complète
    meilleure = []
    for _ in range(4):
        mots, complete = generer(model, vocab, index, ids, temperature, max_mots)
        if complete and not repetitif(mots):
            meilleure = mots
            break
        if len(mots) > len(meilleure):
            meilleure = mots
    return recoller(meilleure) if len(meilleure) >= 3 else INCOMPRIS


def repetitif(mots):
    """Vrai si un groupe de 3 mots revient deux fois (« il est un il est un »)."""
    trios = [tuple(mots[i:i + 3]) for i in range(len(mots) - 2)]
    return len(trios) != len(set(trios))


def generer(model, vocab, index, ids, temperature, max_mots):
    """Une réponse mot par mot. Renvoie (mots, complete) : complete=True si le modèle a lui-même fini sa phrase.
    Une réponse ne peut pas s'arrêter trop tôt ni juste après « le », « de », une virgule…, et finit toujours
    par un . ! ou ?"""
    ids = list(ids)
    mots, compte = [], Counter()
    fin, nl = index["<fin>"], index["<nl>"]
    interdits = [index["<pad>"], index["<unk>"]]
    ponct_fin = [index[p] for p in FIN_PHRASE if p in index]
    complete = False
    for _ in range(max_mots):
        sortie, _ = model(torch.tensor([ids[-CONTEXTE:]]))   # le Transformer relit tout le contexte
        logits = sortie[0, -1].clone()
        for i, c in compte.items():                          # pénalise les mots déjà dits (les petits mots à peine)
            mot = vocab[i]
            if mot in ".,;:!?":
                continue
            p = (1.08 if len(mot) <= 3 else 1.4) ** c
            logits[i] = logits[i] / p if logits[i] > 0 else logits[i] * p
        logits = logits / temperature
        logits[interdits] = float("-inf")
        dernier = mots[-1] if mots else None
        if dernier is None or dernier in OUVRANTS:           # pas de point juste après « de » ou au tout début
            logits[ponct_fin] = float("-inf")
        if len(mots) < 3 or dernier in OUVRANTS:             # pas de fin trop tôt ni au milieu d'une phrase
            logits[[fin, nl]] = float("-inf")
        haut, pos = logits.topk(10)
        suivant = pos[torch.multinomial(torch.softmax(haut, 0), 1)].item()
        mot = vocab[suivant]
        if suivant in (fin, nl):
            complete = True
            break
        mots.append(datetime.now().strftime("%H:%M") if mot == "<heure>" else mot)
        compte[suivant] += 1
        ids.append(suivant)
        if mot in FIN_PHRASE and len(mots) >= 4 and random.random() < 0.5:
            complete = True   # une phrase est finie : on peut s'arrêter là (une fois sur deux, pour en laisser deux)
            break
    if not complete:          # trop long : on coupe à la dernière phrase terminée
        for i in range(len(mots) - 1, 2, -1):
            if mots[i] in FIN_PHRASE:
                return mots[: i + 1], False
    while mots and mots[-1] in OUVRANTS:
        mots.pop()            # jamais de « … et » ou « … de » à la fin
    if mots and mots[-1] not in FIN_PHRASE:
        mots.append(".")
    return mots, complete


def main():
    args = sys.argv[1:]
    if "--lang" in args:
        definir_langue(args[args.index("--lang") + 1])
    minutes = float(args[args.index("--minutes") + 1]) if "--minutes" in args else 10
    if "--continu" in args:
        continu(float(args[args.index("--cycle") + 1]) if "--cycle" in args else 20)
        return
    if "--train" in args or not os.path.exists(MODEL_PATH):
        entrainer(minutes)
    model, vocab = charger()

    print(f"IA prête ({len(vocab)} mots) ! Tape 'quit' pour quitter.")
    while True:
        try:
            texte = input("Toi : ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texte:
            continue
        if texte.lower() in ("quit", "exit", "q"):
            break
        print("IA  :", repondre(texte, model, vocab))


if __name__ == "__main__":
    main()
