# =============================================
# ==== Le protocole : quels messages s'échangent l'hôte et les clients.
# ====
# ==== Modèle « non dédié », comme ARK : celui qui crée la partie l'héberge ET y joue.
# ==== L'hôte fait autorité sur le monde (ennemis, propulsion, production). Chaque joueur
# ==== fait autorité sur SA position : il la calcule chez lui et l'annonce. C'est beaucoup
# ==== plus simple qu'une vraie prédiction réseau, et ça ne se voit pas en coopératif.
# ====
# ==== Les clés sont courtes exprès : un instantané part 20 fois par seconde vers chaque
# ==== joueur, "x" au lieu de "position_x" fait une vraie différence sur le débit.
# =============================================
VERSION = 1

# ---- client -> hôte ----
BONJOUR = "bonjour"        # {pseudo, version} : première chose qu'un client envoie
MOUVEMENT = "mvt"          # {x, y, d, a, n, pi, z} : où j'en suis (je fais autorité là-dessus),
                           #                          avec mon zoom (ce que j'ai sous les yeux)
TUILES = "tuiles"          # {l: [[calque, tx, ty, gid], ...]} : ce que j'ai construit / démoli
STRUCTURES_CLIENT = "struct_client"  # {d: ...} : contenu des structures modifié par un client
AU_REVOIR = "aurevoir"     # {} : je me déconnecte proprement

# ---- hôte -> client ----
BIENVENUE = "bienvenue"    # {id, monde} : ton identifiant + le monde entier
INSTANTANE = "inst"        # {j, al, ve, ti, tn, ro} : joueurs, ennemis et position des robots,
                           #                           20 fois par seconde
STRUCTURES = "struct"      # {co, ro} : contenu des conteneurs et stock des robots, 2 fois par seconde

# Ce qui bouge vite va dans l'INSTANTANE (20 Hz), ce qui change rarement dans STRUCTURES (2 Hz).
# Un robot a les deux : sa position file à 600 pixels par seconde (instantané), son stock ne
# change qu'en rentrant à la base (structures).
REFUS = "refus"            # {raison} : tu ne peux pas entrer (version différente, partie pleine)
FIN = "fin"                # {raison} : l'hôte s'arrête

# TUILES circule dans les deux sens : du client vers l'hôte quand il construit, de l'hôte
# vers tous les autres pour que le changement se voie partout.

JOUEURS_MAX = 16
HERTZ_INSTANTANE = 20      # instantanés par seconde
HERTZ_STRUCTURES = 2       # envois du contenu des conteneurs par seconde
DELAI_SILENCE = 15.0       # secondes sans rien recevoir avant de considérer la connexion morte

# Au-delà de cette distance (en pixels monde) de la caméra d'un joueur, on ne lui envoie
# pas un ennemi : il ne peut pas le voir. C'est ce qui permet de tenir à 8 joueurs et plus
# sans que le débit de l'hôte explose.
MARGE_INTERET = 1200


def dans_la_vue(camera, x, y, marge=MARGE_INTERET):
    """True si le point est dans la vue de cette caméra, élargie de `marge`."""
    return (camera.x - marge <= x <= camera.x + camera.screen_width + marge
            and camera.y - marge <= y <= camera.y + camera.screen_height + marge)
