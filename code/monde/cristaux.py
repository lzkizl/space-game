import math
import random

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme.ressources import CARBURE_TUNGSTENE, CUIVRE, FER, SHARD
from systeme.settings import CRISTAL_PORTEE, CRISTAL_SHARDS, MINERAI_QUANTITE, RACINE

# =============================================
# ==== Cristaux lumineux des planètes : tirés avec le sol de chaque biome (voir CRISTAUX_BIOMES et
# ==== Map._sol). Ils éclairent le sol autour d'eux (une lueur qui pulse). Sur une planète, E à côté d'un
# ==== cristal en détache un shard : il rétrécit, et disparaît après son dernier shard. Ce qui a été
# ==== récolté est sauvegardé (le reste se retrouve à partir de la carte : rien à garder).
# ==== Les gisements de minerai (MINERAIS_BIOMES) sont tirés de la même façon, sans lumière. Ils ne se
# ==== récoltent pas à la main : une foreuse posée dessus en extrait le minerai (voir structures/foreuses.py),
# ==== et ils rétrécissent de la même façon.
# =============================================
DOSSIER_IMAGES = RACINE / "image" / "image"
PIED = 0.93                 # hauteur du pied dans l'image (part de sa hauteur, depuis le haut)
COULEURS = {"violet": (160, 96, 250), "bleu": (70, 190, 255), "rose": (255, 110, 200),
            "rouge": (255, 55, 25), "ambre": (255, 155, 20)}
# gisement -> (ressource minée, couleur des éclats)
MINERAIS = {
    "fer": (FER, (176, 92, 58)),
    "cuivre": (CUIVRE, (214, 124, 60)),
    "carbure": (CARBURE_TUNGSTENE, (150, 162, 196)),
}
TAILLE_MIN = 0.55           # taille d'un cristal presque vide (part de sa taille entière)
RAYON_LUEUR = 150           # rayon de la lumière sur le sol (pixels monde)
FORCE_LUEUR = 0.55          # lumière au centre (1 = la couleur du cristal ajoutée telle quelle)
NIVEAUX_LUEUR = 12          # intensités de la lueur préparées à l'avance (elle pulse entre elles)
HAUTEUR_LUEUR = 34          # la lueur est centrée un peu au-dessus du pied
ECLATS_PAR_COUP = 14        # éclats qui volent quand on récolte
DUREE_ECLAT = 0.7           # secondes
DUREE_TEXTE = 1.3           # « +1 Shard » qui monte au-dessus du cristal
COULEUR_AIDE = (255, 255, 255)


class Cristaux:
    def __init__(self):
        self.recoltes = {}   # carte -> {(tx, ty): shards restants} : seulement les cristaux déjà touchés
        self.temps = 0.0     # (pour faire pulser les lueurs)
        self.eclats = []     # [x, y, vx, vy, temps restant, couleur] : éclats qui volent (pixels monde)
        self.textes = []     # [x, y, texte, temps restant] : « +1 Shard » (pixels monde)
        self._images = {}    # (couleur, taille) -> image
        self._lueurs = {}    # (couleur, niveau) -> lueur
        self._police = None

    # ---- état d'un cristal ----
    @staticmethod
    def _shards_au_depart(nom_carte, tx, ty, couleur):
        quantite = MINERAI_QUANTITE if couleur in MINERAIS else CRISTAL_SHARDS
        return random.Random(f"cristal:{nom_carte}:{tx}:{ty}").randint(*quantite)

    def _restants(self, nom_carte, tx, ty, couleur):
        """(shards restants, shards au départ) du cristal (ou du gisement) de la case (tx, ty)."""
        depart = self._shards_au_depart(nom_carte, tx, ty, couleur)
        return self.recoltes.get(nom_carte, {}).get((tx, ty), depart), depart

    def restants(self, nom_carte, tx, ty, couleur):
        """Ce qui reste dans le cristal (ou le gisement) de la case (tx, ty)."""
        return self._restants(nom_carte, tx, ty, couleur)[0]

    def miner(self, nom_carte, tx, ty, minerai):
        """Une foreuse extrait un morceau du gisement de la case (tx, ty). Renvoie True s'il en restait."""
        restants = self.restants(nom_carte, tx, ty, minerai)
        if restants <= 0:
            return False
        self.recoltes.setdefault(nom_carte, {})[(tx, ty)] = restants - 1
        return True

    def autour(self, carte, gauche, haut, droite, bas):
        """[(tx, ty, couleur, restants, au départ), ...] : les cristaux (et gisements) pas encore vides dont la
        case est dans ce rectangle (pixels monde). Pour un gisement, `couleur` est son minerai ("fer"...)."""
        taille = carte.chunk_size * carte.tilewidth
        trouves = []
        for cy in range(int(haut // taille), int(bas // taille) + 1):
            for cx in range(int(gauche // taille), int(droite // taille) + 1):
                for tx, ty, couleur in carte.cristaux((cx, cy)):
                    restants, depart = self._restants(carte.nom, tx, ty, couleur)
                    if restants > 0:
                        trouves.append((tx, ty, couleur, restants, depart))
        return trouves

    def _visibles(self, carte, camera, marge=RAYON_LUEUR):
        return self.autour(carte, camera.x - marge, camera.y - marge,
                           camera.x + camera.screen_width + marge, camera.y + camera.screen_height + marge)

    @staticmethod
    def _pied(carte, tx, ty):
        return (tx + 0.5) * carte.tilewidth, (ty + 1) * carte.tileheight

    def proche(self, carte, hero, minerais=False):
        """Le cristal le plus proche du héros, s'il est assez près pour être récolté (sinon None). `minerais` :
        le gisement de minerai le plus proche, à la place."""
        hx, hy = hero.hitbox(hero.x, hero.y).center
        meilleur, distance_min = None, CRISTAL_PORTEE
        for cristal in self.autour(carte, hx - CRISTAL_PORTEE, hy - CRISTAL_PORTEE,
                                   hx + CRISTAL_PORTEE, hy + CRISTAL_PORTEE + carte.tileheight):
            if (cristal[2] in MINERAIS) != minerais:
                continue
            x, y = self._pied(carte, cristal[0], cristal[1])
            distance = math.hypot(x - hx, y - HAUTEUR_LUEUR - hy)
            if distance <= distance_min:
                meilleur, distance_min = cristal, distance
        return meilleur

    # ---- récolte ----
    def recolter(self, carte, hero, inventaire):
        """E : détache un shard du cristal le plus proche (s'il y en a un à portée). Renvoie True si un
        cristal était à portée (même si l'inventaire est plein)."""
        cristal = self.proche(carte, hero)
        if cristal is None:
            return False
        tx, ty, couleur, restants, _ = cristal
        x, y = self._pied(carte, tx, ty)
        if inventaire.ajouter_objet(SHARD, 1):
            self.textes.append([x, y - 120, "Inventaire plein", DUREE_TEXTE])
            return True
        self.recoltes.setdefault(carte.nom, {})[(tx, ty)] = restants - 1
        self.textes.append([x, y - 120, "+1 Shard", DUREE_TEXTE])
        teinte = COULEURS[couleur]
        clair = tuple(min(255, c + 90) for c in teinte)
        for _ in range(ECLATS_PAR_COUP):
            angle = random.uniform(math.pi * 1.1, math.pi * 1.9)  # vers le haut, en éventail
            vitesse = random.uniform(150, 420)
            self.eclats.append([x + random.uniform(-15, 15), y - random.uniform(20, 70),
                                math.cos(angle) * vitesse, math.sin(angle) * vitesse,
                                DUREE_ECLAT * random.uniform(0.6, 1.0), random.choice((teinte, clair))])
        return True

    def update(self, dt):
        self.temps += dt
        for eclat in self.eclats:
            eclat[0] += eclat[2] * dt
            eclat[1] += eclat[3] * dt
            eclat[3] += 900 * dt  # ils retombent
            eclat[4] -= dt
        self.eclats = [e for e in self.eclats if e[4] > 0]
        for texte in self.textes:
            texte[1] -= 60 * dt
            texte[3] -= dt
        self.textes = [t for t in self.textes if t[3] > 0]

    # ---- images ----
    def _image(self, couleur, taille):
        """Image du cristal (ou du gisement), réduite selon ce qu'il lui reste (taille arrondie : peu d'images
        différentes)."""
        taille = round(taille * 20) / 20
        cle = (couleur, taille)
        if cle not in self._images:
            nom = f"minerai_{couleur}.png" if couleur in MINERAIS else f"cristal_{couleur}.png"
            image = pygame.image.load(DOSSIER_IMAGES / nom).convert_alpha()
            if taille != 1:
                image = pygame.transform.smoothscale(
                    image, (round(image.get_width() * taille), round(image.get_height() * taille)))
            self._images[cle] = image
        return self._images[cle]

    def _lueur(self, couleur, niveau):
        """Lumière ronde (à ajouter au sol : noir = rien), de plus en plus faible vers le bord."""
        cle = (couleur, niveau)
        if cle not in self._lueurs:
            petit = pygame.Surface((64, 64))
            force = FORCE_LUEUR * niveau / NIVEAUX_LUEUR
            for y in range(64):
                for x in range(64):
                    d = math.hypot(x - 31.5, y - 31.5) / 32
                    v = max(0.0, 1 - d) ** 2 * force
                    petit.set_at((x, y), tuple(round(c * v) for c in COULEURS[couleur]))
            self._lueurs[cle] = pygame.transform.smoothscale(petit, (RAYON_LUEUR * 2, RAYON_LUEUR * 2))
        return self._lueurs[cle]

    def images(self, carte, camera):
        """[(pied, x, image), ...] des cristaux autour de la vue (pixels monde, pied en bas au milieu) : le
        décor les dessine avec les arbres, triés par pied (voir Decors.draw)."""
        liste = []
        for tx, ty, couleur, restants, depart in self._visibles(carte, camera, marge=carte.tilewidth):
            x, pied = self._pied(carte, tx, ty)
            liste.append((pied, x, self._image(couleur, TAILLE_MIN + (1 - TAILLE_MIN) * restants / depart)))
        return liste

    # ---- dessin ----
    def draw_lueurs(self, vue, camera, carte):
        """La lumière des cristaux sur le sol (à dessiner sur le sol, avant le héros et les décors)."""
        for tx, ty, couleur, restants, depart in self._visibles(carte, camera):
            if couleur in MINERAIS:
                continue  # (un gisement de minerai n'éclaire pas)
            x, y = self._pied(carte, tx, ty)
            pulsation = 0.8 + 0.2 * math.sin(self.temps * 2.2 + tx * 1.7 + ty * 2.3)
            force = pulsation * (0.5 + 0.5 * restants / depart)
            niveau = max(1, round(force * NIVEAUX_LUEUR))
            vue.blit(self._lueur(couleur, niveau),
                     (round(x - RAYON_LUEUR - camera.x), round(y - HAUTEUR_LUEUR - RAYON_LUEUR - camera.y)),
                     special_flags=pygame.BLEND_RGB_ADD)

    def draw_eclats(self, vue, camera):
        for x, y, _, _, reste, couleur in self.eclats:
            rayon = max(1, round(5 * reste / DUREE_ECLAT))
            pygame.draw.circle(vue, couleur, (round(x - camera.x), round(y - camera.y)), rayon)

    def draw_interface(self, screen, camera, carte, hero, libre=True):
        """« E : récolter » au-dessus du cristal à portée (si `libre` : aucun menu ouvert), et les « +1 Shard »
        (à la taille de l'écran : pas flous quand on zoome)."""
        if self._police is None:
            self._police = pygame.font.Font(None, 30)

        def ecran(x, y):
            return round((x - camera.x) * camera.zoom), round((y - camera.y) * camera.zoom)

        if libre:
            # à côté d'un cristal : E pour le récolter ; d'un gisement : ce qu'il contient (il faut une foreuse)
            cristal = self.proche(carte, hero) or self.proche(carte, hero, minerais=True)
            if cristal is not None:
                tx, ty, couleur, restants, _ = cristal
                x, y = self._pied(carte, tx, ty)
                if couleur in MINERAIS:
                    aide = f"Gisement de {MINERAIS[couleur][0].nom.lower()} ({restants}) : à extraire avec une foreuse"
                else:
                    aide = f"E : récolter ({restants})"
                texte = self._police.render(aide, True, COULEUR_AIDE)
                bulle = texte.get_rect().inflate(18, 10)
                bulle.midbottom = ecran(x, y - 150)
                fond = pygame.Surface(bulle.size, pygame.SRCALPHA)
                pygame.draw.rect(fond, (10, 10, 20, 200), fond.get_rect(), border_radius=8)
                screen.blit(fond, bulle)
                screen.blit(texte, texte.get_rect(center=bulle.center))
        for x, y, texte, reste in self.textes:
            image = self._police.render(texte, True, (230, 200, 255))
            image.set_alpha(round(255 * min(1.0, reste / (DUREE_TEXTE * 0.4))))
            screen.blit(image, image.get_rect(center=ecran(x, y)))

    # ---- sauvegarde ----
    def exporter(self):
        return {nom: [[tx, ty, n] for (tx, ty), n in cases.items()] for nom, cases in self.recoltes.items()}

    def importer(self, donnees):
        self.recoltes = {nom: {(tx, ty): n for tx, ty, n in cases} for nom, cases in donnees.items()}


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
