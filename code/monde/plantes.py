import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structures.building import case_sous_souris
from construction import plante as construction_plante
from systeme.ressources import BAIE, FIBRE
from systeme.settings import BAIE_DELAI, BAIE_STOCK_MAX, FIBRE_DELAI, FIBRE_STOCK_MAX

GID_PLANTE = construction_plante.TUILES[0][2]


class Plante:
    """Une plante posée : alimentée en énergie, elle produit une baie toutes les
    BAIE_DELAI secondes et une fibre toutes les FIBRE_DELAI secondes, gardées dans son
    inventaire (BAIE_STOCK_MAX / FIBRE_STOCK_MAX au plus)."""

    titre = "Plante"
    cases = [BAIE, FIBRE]

    def __init__(self, tx, ty):
        self.tx = tx
        self.ty = ty
        self.stock = {BAIE: 0, FIBRE: 0}
        self.chrono = 0  # temps écoulé depuis la dernière baie
        self.chrono_fibre = 0  # ... et depuis la dernière fibre


class Plantes:
    """Les plantes du monde : une `Plante` par tuile de plante posée sur la carte."""

    def __init__(self):
        self.plantes = {}  # (tx, ty) -> Plante

    # ---- apparition / disparition ----
    def scan(self, game_map):
        """Crée une Plante pour chaque tuile de plante de la carte qui n'en a pas encore
        (plantes déjà dessinées dans la carte, ou monde sans données de plantes)."""
        taille = game_map.chunk_size
        for (cx, cy), grille in game_map.layers[construction_plante.CALQUE].items():
            for y, ligne in enumerate(grille):
                for x, gid in enumerate(ligne):
                    if gid == GID_PLANTE:
                        cle = (cx * taille + x, cy * taille + y)
                        self.plantes.setdefault(cle, Plante(*cle))

    def ajouter(self, tx, ty):
        self.plantes[(tx, ty)] = Plante(tx, ty)

    def deplacer(self, trajet):
        """La base a bougé : {ancienne case: nouvelle case}."""
        anciennes = self.plantes
        self.plantes = {}
        for cle, plante in anciennes.items():
            plante.tx, plante.ty = trajet.get(cle, cle)
            self.plantes[(plante.tx, plante.ty)] = plante

    def retirer(self, tx, ty, inventaire):
        """La plante part : ses baies vont dans l'inventaire (celles qui ne rentrent pas
        sont perdues). Renvoie la plante retirée (ou None)."""
        plante = self.plantes.pop((tx, ty), None)
        if plante is not None:
            for ressource, quantite in plante.stock.items():
                if quantite:
                    inventaire.ajouter_objet(ressource, quantite)
        return plante

    # ---- production ----
    def update(self, dt, energie):
        """Sans assez d'énergie, les plantes ne produisent rien."""
        if not energie.suffisante:
            return
        for plante in self.plantes.values():
            plante.chrono += dt
            while plante.chrono >= BAIE_DELAI:
                plante.chrono -= BAIE_DELAI
                plante.stock[BAIE] = min(BAIE_STOCK_MAX, plante.stock[BAIE] + 1)
            if plante.stock[BAIE] >= BAIE_STOCK_MAX:
                plante.chrono = 0  # réserve pleine : on ne stocke pas de temps d'avance
            plante.chrono_fibre += dt
            while plante.chrono_fibre >= FIBRE_DELAI:
                plante.chrono_fibre -= FIBRE_DELAI
                plante.stock[FIBRE] = min(FIBRE_STOCK_MAX, plante.stock[FIBRE] + 1)
            if plante.stock[FIBRE] >= FIBRE_STOCK_MAX:
                plante.chrono_fibre = 0

    # ---- souris ----
    def sous_souris(self, game_map, camera, pos_vue):
        """La plante sur la case sous la souris (ou None)."""
        return self.plantes.get(case_sous_souris(game_map, camera, pos_vue))

    # ---- sauvegarde ----
    def exporter(self):
        return [{"tx": p.tx, "ty": p.ty, "baies": p.stock[BAIE], "chrono": p.chrono,
                 "fibres": p.stock[FIBRE], "chrono_fibre": p.chrono_fibre}
                for p in self.plantes.values()]

    def importer(self, donnees):
        self.plantes = {}
        for d in donnees:
            plante = Plante(d["tx"], d["ty"])
            plante.stock[BAIE] = d["baies"]
            plante.chrono = d["chrono"]
            plante.stock[FIBRE] = d.get("fibres", 0)  # absent des anciennes sauvegardes
            plante.chrono_fibre = d.get("chrono_fibre", 0)
            self.plantes[(plante.tx, plante.ty)] = plante


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
