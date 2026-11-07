import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from joueur.eau import Eau
from joueur.faim import Faim
from joueur.hero import Hero
from joueur.inventory import Inventory
from joueur.oxygen import Oxygen
from joueur.vie import Vie
from monde.camera import Camera
from systeme.settings import EAU_MAX, FAIM_MAX, OXYGENE_MAX, VIE_MAX, ZOOM_MAX, ZOOM_MIN

# =============================================
# ==== Un joueur : tout ce qui lui appartient en propre, par opposition au monde, qui est partagé
# ==== (voir monde/partie.py). En solo il n'y en a qu'un ; en multijoueur il y en a un par
# ==== participant, celui de la machine où l'on joue étant `partie.moi`.
# =============================================


def plus_proche(joueurs, x, y):
    """Le joueur le plus proche du point (x, y), en pixels monde (None si la liste est vide).

    Les ennemis s'en servent pour choisir leur cible : en solo c'est toujours le même joueur,
    en multijoueur c'est celui qui s'est le plus approché.
    """
    if not joueurs:
        return None
    return min(joueurs, key=lambda j: (j.hero.x - x) ** 2 + (j.hero.y - y) ** 2)


class Joueur:
    """Le héros d'un participant, sa caméra, ses jauges et son inventaire.

    `pseudo` identifie le joueur d'une partie à l'autre : c'est sous ce nom qu'il est sauvegardé,
    et c'est lui qui le retrouve quand il se reconnecte.
    """

    def __init__(self, pseudo, x, y, largeur_fenetre, hauteur_fenetre):
        self.pseudo = pseudo
        self.id = 0  # identifiant dans la partie, donné par l'hôte en multijoueur
        self.hero = Hero(x, y)
        self.camera = Camera(largeur_fenetre, hauteur_fenetre, zoom_min=ZOOM_MIN, zoom_max=ZOOM_MAX)
        self.oxygene = Oxygen()
        self.eau = Eau()
        self.faim = Faim()
        self.vie = Vie()
        self.inventaire = Inventory(largeur_fenetre, hauteur_fenetre)
        # Vaisseau piloté (None : à pied). Le vaisseau lui-même appartient au monde (il reste
        # posé quand on en descend) ; seul « qui est dedans » est propre au joueur.
        self.pilote = None
        # Carte où se trouve le joueur : None pour l'espace, sinon le nom de la carte de la
        # planète sur laquelle il est descendu.
        self.carte = None
        # Multijoueur : de combien l'hôte a déplacé ce joueur malgré lui depuis le dernier
        # instantané (base poussée par ses réacteurs, trou noir). Comme chaque joueur fait
        # autorité sur sa propre position, l'hôte ne peut pas la lui imposer : il lui envoie
        # ce décalage, et le joueur l'applique chez lui. Voir reseau/protocole.py.
        self.poussee = [0.0, 0.0]
        self.connexion = None   # sa connexion, côté hôte (None : c'est nous, ou il est parti)
        self.derniere_nouvelle = 0.0  # quand on a eu de ses nouvelles (voir reseau/serveur.py)
        # Un joueur déconnecté reste dans la partie (il est sauvegardé et retrouvera ses
        # affaires en revenant) mais il n'est plus là : on ne le dessine plus, les aliens
        # ne le poursuivent plus, et il ne part plus dans les instantanés.
        self.present = True

    # ---- état vital ----
    def cause_mort(self):
        """Texte expliquant la mort du héros ("" s'il est toujours en vie)."""
        if self.vie.vide:
            return "Tué par les aliens"
        if self.oxygene.vide:
            return "Plus d'oxygène"
        if self.eau.vide:
            return "Mort de soif"
        if self.faim.vide:
            return "Mort de faim"
        return ""

    def ressusciter(self):
        """Remet les quatre jauges au maximum (réapparition après la mort)."""
        self.oxygene.value = OXYGENE_MAX
        self.eau.value = EAU_MAX
        self.faim.value = FAIM_MAX
        self.vie.value = VIE_MAX


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
