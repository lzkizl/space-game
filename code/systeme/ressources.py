import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.settings import EAU_BOUTEILLE, FAIM_BAIE, RACINE, VIE_KIT


# =============================================
# ==== Ressources récupérées sur les météorites, et objets fabriqués
# =============================================
DOSSIER_ICONES = RACINE / "image" / "image"
DOSSIER_ICONES_RESSOURCES = DOSSIER_ICONES / "ressource"  # cherché en premier


class Ressource:
    def __init__(self, nom, icone, eau=0, faim=0, vie=0):
        self.nom = nom
        # même nom que les constructions (voir inventory.icone) : dans image/image/ressource/, sinon image/image/
        chemin = DOSSIER_ICONES_RESSOURCES / icone
        self.ICONE = chemin if chemin.exists() else DOSSIER_ICONES / icone
        self.EAU = eau    # eau rendue quand on la boit (0 = ne se boit pas)
        self.FAIM = faim  # faim rendue quand on la mange (0 = ne se mange pas)
        self.VIE = vie    # vie rendue quand on l'utilise (0 = ne soigne pas)


VERRE = Ressource("Verre", "verre.png")
FER = Ressource("Fer", "iron.png")
CUIVRE = Ressource("Cuivre", "cuivre.png")
GLACE = Ressource("Glace", "ice.png")
SOUFRE = Ressource("Soufre", "souffre.png")  # uniquement dans les astéroïdes de soufre
SHARD = Ressource("Shard", "shard.png")  # uniquement dans les astéroïdes de shard
TUNGSTENE = Ressource("Tungstène", "tungsten.png")  # dans les météorites (nécessaire au réacteur)
URANIUM = Ressource("Uranium", "uranium.png")  # uniquement dans les astéroïdes d'uranium (réacteur nucléaire)
BOUTEILLE = Ressource("Bouteille d'eau", "bouteille.png", eau=EAU_BOUTEILLE)
BAIE = Ressource("Baie", "baie.png", faim=FAIM_BAIE)  # produite par les plantes (voir plantes.py)
FIBRE = Ressource("Fibre", "fibre.png")  # produite par les plantes (voir plantes.py)
KIT_MEDICAL = Ressource("Kit médical", "kit_medical.png", vie=VIE_KIT)  # fabriqué avec des fibres
MUNITION = Ressource("Munition", "munition.png")  # chargée dans une tourelle (voir tourelles.py)
# fabriquée avec du tungstène et du cuivre ; chargée dans le canon électromagnétique (10 tirs chacune)
BALLE_PERFORMANTE = Ressource("Balle performante", "balle_performante.png")
OXYGENE = Ressource("Oxygène", "oxigene.png")  # sortie du four quand on y cuit de la glace ; alimente l'oxygénateur
HYDROGENE = Ressource("Hydrogène", "hydrogene.png")  # idem
BARRE_NUCLEAIRE = Ressource("Barre nucléaire", "barre_nucleaire.png")  # fabriquée avec de l'uranium ; brûlée par le réacteur nucléaire

# ressource -> (min, max) obtenus à chaque météorite récupérée
BUTIN_METEORITE = {
    VERRE: (1, 3),
    FER: (3, 7),
    CUIVRE: (1, 2),
    GLACE: (1, 2),
    TUNGSTENE: (0, 1),
}

# butin d'un astéroïde de soufre (plus rare qu'une météorite)
BUTIN_ASTEROIDE = {
    SOUFRE: (2, 5),
    FER: (1, 3),
}

# butin d'un astéroïde de shard (le plus rare)
BUTIN_SHARD = {
    SHARD: (1, 3),
    VERRE: (0, 1),
}

# butin d'un astéroïde d'uranium (rare)
BUTIN_URANIUM = {
    URANIUM: (1, 6),
    FER: (1, 3),
}

# uniquement dans les navettes échouées de la carte (voir coffres.Coffres.scan)
PROCESSEUR = Ressource("Processeur", "prosseceur.png")
RAM = Ressource("RAM", "ram.png")
# les clés USB ne se fabriquent pas : on les trouve (rarement) dans les navettes échouées (voir BUTIN_RARE_EPAVE)
CLE_USB = Ressource("Clé USB", "usb_1.png")  # rangée dans un boîtier, elle traduit les bits en lettres
# rangée dans un boîtier, elle pilote les réacteurs de la plateforme (voir propulsion.py)
CLE_USB_REACTEUR = Ressource("Clé USB réacteurs", "usb_reacteur.png")
# rangée dans un boîtier collé à une antenne, la radio pilote le télescope réglé sur sa fréquence
CLE_USB_SATELLITE = Ressource("Clé USB satellite", "usb_satellite.png")

# ressource -> (min, max) trouvés dans chaque navette échouée
BUTIN_EPAVE = {
    PROCESSEUR: (1, 2),
    RAM: (1, 3),
}

# en plus, très rarement : ressource -> (chance qu'elle y soit, min, max). Chacune est tirée à part
BUTIN_RARE_EPAVE = {
    SHARD: (0.06, 1, 2),
    CLE_USB: (0.04, 1, 1),
    CLE_USB_REACTEUR: (0.03, 1, 1),
    CLE_USB_SATELLITE: (0.03, 1, 1),
}

# uniquement dans les gisements de Mars (voir MINERAIS_BIOMES dans settings.py) ; servira à fabriquer
CARBURE_TUNGSTENE = Ressource("Carbure de tungstène", "carbure_tungstene.png")

RESSOURCES = list(BUTIN_METEORITE) + [SOUFRE, SHARD, URANIUM] + list(BUTIN_EPAVE)
MINERAIS = [CARBURE_TUNGSTENE]  # ressources qu'on ne trouve que dans les gisements des planètes
# pas dans les météorites : fabriqués (voir craft.py), produits par les plantes, ou trouvés dans les navettes
OBJETS_FABRIQUES = [BOUTEILLE, BAIE, FIBRE, KIT_MEDICAL, MUNITION, OXYGENE, HYDROGENE, CLE_USB, BARRE_NUCLEAIRE,
                    CLE_USB_REACTEUR, CLE_USB_SATELLITE, BALLE_PERFORMANTE]
