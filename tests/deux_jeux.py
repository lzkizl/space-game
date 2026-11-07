"""Lance DEUX vraies parties dans deux processus : l'une heberge, l'autre rejoint. C'est le seul
test qui exerce la boucle de jeu complete des deux cotes (main.jouer en mode hote et en mode
client), avec de vraies sockets. Sans fenetre (SDL dummy).

Usage : python deux_jeux.py <dossier_code>
        python deux_jeux.py <dossier_code> --role hote|client   (les processus enfants)
"""
import json
import os
import subprocess
import sys
import time
from collections import defaultdict

DOSSIER_CODE = sys.argv[1]
ROLE = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--role" else None

MONDE = "__deux_jeux__"
PORT = 50124
IMAGES_HOTE = 700        # ~12 s a 60 images/seconde
IMAGES_CLIENT = 330      # ~5,5 s
ATTENTE_CLIENT = 2.0     # secondes entre deux tentatives de connexion
SAUT = 2000              # de combien chaque joueur se deplace, au milieu de la partie


# =====================================================================
# ==== Un processus enfant : il joue une partie scriptee et raconte ce qu'il a vu
# =====================================================================
def jouer_un_role(role):
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    sys.path.insert(0, DOSSIER_CODE)

    import pygame
    pygame.init()

    import main
    from systeme import ecran as mod_ecran
    screen = mod_ecran.creer()  # comme main.main() : c'est lui qui ouvre la fenetre

    from reseau import client as mod_client
    from reseau.serveur import Hote as VraiHote
    from systeme import sauvegarde

    # l'hote ecoute sur un port de test, pour ne pas tomber sur une vraie partie en cours
    main.Hote = lambda *a, **k: VraiHote(*a, **{**k, "port": PORT})

    # on recupere la Partie creee par main.jouer : c'est par elle qu'on observe et qu'on agit
    parties = []
    vraie_partie = main.Partie
    main.Partie = lambda *a, **k: parties.append(vraie_partie(*a, **k)) or parties[-1]

    images = IMAGES_HOTE if role == "hote" else IMAGES_CLIENT
    vu = {"joueurs_max": 0, "pseudos": [], "autre_x": None, "erreur": None, "fin": None}
    compteur = {"n": 0}
    vrai_event_get = pygame.event.get

    def event_get_scripte(*args, **kwargs):
        compteur["n"] += 1
        numero = compteur["n"]
        if parties:
            partie = parties[0]
            presents = partie.presents()
            vu["joueurs_max"] = max(vu["joueurs_max"], len(presents))
            if len(presents) > 1:
                vu["pseudos"] = sorted(j.pseudo for j in presents)
                autre = next(j for j in presents if j is not partie.moi)
                vu["autre_x"] = round(autre.hero.x, 1)
            if numero == 120:   # au bout de 2 s, on se deplace franchement
                partie.moi.hero.x += SAUT if role == "hote" else -SAUT
        if numero >= images:
            return [pygame.event.Event(pygame.QUIT)]
        return vrai_event_get(*args, **kwargs)

    pygame.event.get = event_get_scripte

    try:
        if role == "hote":
            main.jouer(screen, MONDE, True, {"graine": 777, "delai": 99}, "Alice", mode="hote")
        else:
            # l'hote met un moment a charger son monde avant d'ouvrir sa porte : on reessaie
            fin = time.monotonic() + 90.0
            connexion = None
            while connexion is None:
                time.sleep(ATTENTE_CLIENT)
                try:
                    connexion, mon_id, etat = mod_client.rejoindre("127.0.0.1", PORT, "Bob", delai=10.0)
                except mod_client.ErreurReseau:
                    if time.monotonic() > fin:
                        raise
            vu["fin"] = main.jouer(screen, "", False, None, "Bob", mode="client",
                                   etat=etat, connexion=connexion, mon_id=mon_id)
    except SystemExit:
        pass  # fermeture normale : quitter() leve SystemExit
    except Exception as erreur:  # noqa: BLE001 - on la remonte au parent
        import traceback
        traceback.print_exc()
        vu["erreur"] = f"{type(erreur).__name__}: {erreur}"

    if parties:
        vu["ma_position"] = round(parties[0].moi.hero.x, 1)
    print("RESULTAT " + json.dumps(vu))
    return 1 if vu["erreur"] else 0


if ROLE:
    sys.exit(jouer_un_role(ROLE))


# =====================================================================
# ==== Le parent : il lance les deux, puis compare ce que chacun a vu
# =====================================================================
ECHECS = []


def verifier(condition, message):
    if condition:
        print(f"   ok   {message}")
    else:
        print(f"   ECHEC {message}")
        ECHECS.append(message)


def lancer(role):
    return subprocess.Popen([sys.executable, __file__, DOSSIER_CODE, "--role", role],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def depouiller(nom, processus):
    sortie, erreurs = processus.communicate(timeout=120)
    ligne = next((l for l in sortie.splitlines() if l.startswith("RESULTAT ")), None)
    if ligne is None:
        print(f"--- {nom} n'a rien renvoye")
        print(sortie[-2000:])
        print(erreurs[-2000:])
        return None
    return json.loads(ligne[len("RESULTAT "):])


print("-- on lance une partie hebergee, puis une partie qui la rejoint")
processus_hote = lancer("hote")
processus_client = lancer("client")
cote_hote = depouiller("l'hote", processus_hote)
cote_client = depouiller("le client", processus_client)

verifier(cote_hote is not None, "la partie hebergee est allee au bout")
verifier(cote_client is not None, "la partie qui rejoint est allee au bout")

if cote_hote and cote_client:
    verifier(cote_hote["erreur"] is None, f"aucune erreur cote hote ({cote_hote['erreur']})")
    verifier(cote_client["erreur"] is None, f"aucune erreur cote client ({cote_client['erreur']})")
    verifier(cote_client["fin"] is None,
             f"le client n'a pas ete ejecte en cours de route ({cote_client['fin']})")
    verifier(cote_hote["joueurs_max"] == 2, f"l'hote a vu deux joueurs ({cote_hote['joueurs_max']})")
    verifier(cote_client["joueurs_max"] == 2, f"le client a vu deux joueurs ({cote_client['joueurs_max']})")
    verifier(cote_hote["pseudos"] == ["Alice", "Bob"], f"l'hote voit Alice et Bob ({cote_hote['pseudos']})")
    verifier(cote_client["pseudos"] == ["Alice", "Bob"], f"le client voit Alice et Bob ({cote_client['pseudos']})")
    # chacun s'est deplace de son cote : l'autre doit l'avoir vu bouger
    verifier(cote_client["autre_x"] is not None
             and abs(cote_client["autre_x"] - cote_hote["ma_position"]) < 50,
             f"le client voit Alice la ou elle est vraiment "
             f"({cote_client['autre_x']} vs {cote_hote.get('ma_position')})")
    verifier(cote_hote["autre_x"] is not None
             and abs(cote_hote["autre_x"] - cote_client["ma_position"]) < 50,
             f"l'hote voit Bob la ou il est vraiment "
             f"({cote_hote['autre_x']} vs {cote_client.get('ma_position')})")

print("-- le monde sauvegarde par l'hote contient les deux joueurs")
sys.path.insert(0, DOSSIER_CODE)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
from systeme import sauvegarde  # noqa: E402

try:
    etat = sauvegarde.charger(MONDE)
    pseudos = sorted(d.get("pseudo") for d in etat.get("joueurs", []))
    verifier(pseudos == ["Alice", "Bob"], f"la sauvegarde garde les deux joueurs ({pseudos})")
    bob = next((d for d in etat["joueurs"] if d.get("pseudo") == "Bob"), None)
    verifier(bob is not None and cote_client is not None
             and abs(bob["hero"]["x"] - cote_client["ma_position"]) < 200,
             "Bob est sauvegarde la ou il s'est arrete (il retrouvera ses affaires)")
except (OSError, ValueError) as erreur:
    verifier(False, f"la sauvegarde de l'hote est lisible ({erreur})")
finally:
    sauvegarde.supprimer(MONDE)

print()
if ECHECS:
    print(f"{len(ECHECS)} ECHEC(S)")
    sys.exit(1)
print("OK : deux vraies parties jouent ensemble")
