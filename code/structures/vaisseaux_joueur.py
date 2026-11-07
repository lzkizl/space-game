import math

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import vaisseau_joueur
from structures.coffres import Coffre
from systeme.settings import (COULEUR_ALERTE, COULEUR_DECONSTRUCTION, COULEUR_DECONSTRUCTION_BORDURE,
                              COULEUR_TEXTE, COULEUR_ZONE, COULEUR_ZONE_BORDURE,
                              COULEUR_ZONE_REFUSEE, COULEUR_ZONE_REFUSEE_BORDURE)

# =============================================
# ==== Les vaisseaux du joueur posés dans le monde (voir construction/vaisseau_joueur.py).
# ==== Un vaisseau garde la position du héros quand on est dedans (x, y = coin haut gauche
# ==== du sprite du héros) : caméra, minimap, aliens... suivent donc le héros sans rien changer.
# =============================================
CARBURANTS = tuple(vaisseau_joueur.CASE_OBJET.items())  # [(objet, case), ...]
COULEUR_H = (235, 110, 90)
COULEUR_O = (70, 160, 230)
COULEUR_TELEPORTATION = (150, 80, 255)
DUREE_ECLAIR = 600  # millisecondes de l'éclair violet après une téléportation


def angle_nez(dx, dy):
    """Angle (degrés, pour pygame.transform.rotate) du nez qui pointe dans la direction (dx, dy) :
    Q = gauche (90), D = droite (-90), Z = haut (0), S = bas (180)."""
    return -math.degrees(math.atan2(dx, -dy))


class VaisseauJoueur:
    def __init__(self, x, y, modele=vaisseau_joueur):
        self.x = x
        self.y = y
        self.modele = modele  # vaisseau_joueur ou vaisseau_teleporteur (ses réglages, son image)
        self.coffre = Coffre(0, 0, modele)  # son inventaire (le carburant en réserve)
        self.reserves = [0.0, 0.0]  # hydrogène et oxygène déjà tirés des objets
        self.angle = 0  # inclinaison en degrés (sens inverse des aiguilles) ; 0 = nez vers le haut

    def centre(self, hero):
        image = hero.images["immobile", "bas"][0]
        return self.x + image.get_width() / 2, self.y + image.get_height() / 2

    def rect(self, hero):
        t = self.modele.TAILLE
        rect = pygame.Rect(0, 0, t, t)
        rect.center = self.centre(hero)
        return rect

    def peut_voler(self):
        return all(r > 0 or self.coffre.objets[i] is not None for i, r in enumerate(self.reserves))

    def bruler(self, dt):
        """Brûle du carburant (un objet entamé quand la réserve de la case est vide)."""
        for i in range(len(self.reserves)):
            if self.reserves[i] <= 0 and self.coffre.objets[i] is not None:
                self.reserves[i] += self.modele.UNITES_PAR_OBJET
                self.coffre.nombres[i] -= 1
                if self.coffre.nombres[i] <= 0:
                    self.coffre.objets[i], self.coffre.nombres[i] = None, 0
            self.reserves[i] = max(0.0, self.reserves[i] - self.modele.CONSO_PAR_SEC * dt)

    @property
    def shards(self):
        """Shards rangés dans le vaisseau (téléporteur seulement : None pour un vaisseau simple)."""
        if not getattr(self.modele, "TELEPORTEUR", False):
            return None
        return self.coffre.nombres[self.modele.CASE_SHARD]


class VaisseauxJoueur:
    """Tous les vaisseaux posés dans le monde. Ils appartiennent au monde (ils restent où ils sont
    quand on en descend) ; « qui est dedans » appartient au joueur, c'est `Joueur.pilote`.

    `joueurs` : les joueurs de la partie, pour savoir quels vaisseaux sont occupés (en solo, un seul).
    """

    def __init__(self, joueurs=()):
        self.liste = []
        # on garde LA liste des joueurs, pas une copie : en multijoueur elle change (arrivées,
        # départs) et une copie ferait croire qu'un vaisseau est occupé par un joueur parti
        self.joueurs = joueurs if isinstance(joueurs, list) else list(joueurs)
        self.message = ""
        self.message_fin = 0
        self.police = pygame.font.Font(None, 30)
        self._images = {}  # modèle -> son image à la taille du monde
        self.orientation = 0  # inclinaison du prochain vaisseau posé
        self.eclair_fin = 0  # fin de l'éclair violet de la dernière téléportation

    def _dire(self, texte):
        self.message = texte
        self.message_fin = pygame.time.get_ticks() + 2000

    def occupes(self):
        """Les vaisseaux dans lesquels un joueur est assis."""
        return {j.pilote for j in self.joueurs if j.pilote is not None}

    def index(self, vaisseau):
        """Position du vaisseau dans la liste (-1 s'il n'y est pas) : sert à la sauvegarde."""
        return self.liste.index(vaisseau) if vaisseau in self.liste else -1

    def par_index(self, i):
        """Vaisseau à cette position dans la liste (None hors liste) : sert au chargement."""
        return self.liste[i] if 0 <= i < len(self.liste) else None

    # ---- poser / monter / descendre ----
    def _candidat(self, monde_x, monde_y, hero, game_map, modele):
        """(vaisseau à poser sous le point visé, True si c'est possible : pas trop loin du héros
        et pas de collision)."""
        image = hero.images["immobile", "bas"][0]
        vaisseau = VaisseauJoueur(monde_x - image.get_width() / 2, monde_y - image.get_height() / 2, modele)
        vaisseau.angle = self.orientation
        hx, hy = hero.x + image.get_width() / 2, hero.y + image.get_height() / 2
        ok = (math.hypot(monde_x - hx, monde_y - hy) <= modele.PORTEE
              and not game_map.collides(vaisseau.rect(hero)))
        return vaisseau, ok

    def poser(self, monde_x, monde_y, hero, game_map, modele=vaisseau_joueur):
        """Pose un vaisseau (du modèle sélectionné dans l'inventaire) sous le point visé (en pixels
        monde), sur la plateforme et pas trop loin du héros. Renvoie True si c'est posé."""
        vaisseau, ok = self._candidat(monde_x, monde_y, hero, game_map, modele)
        if ok:
            self.liste.append(vaisseau)
        return ok

    def orienter(self, keys):
        """Avant la pose : Z / Q / S / D (ou deux ensemble) tournent le nez du vaisseau."""
        dx = keys[pygame.K_d] - keys[pygame.K_q]
        dy = keys[pygame.K_s] - keys[pygame.K_z]
        if dx or dy:
            self.orientation = angle_nez(dx, dy)

    def apercu(self, screen, camera_offset, monde_x, monde_y, hero, game_map, modele=vaisseau_joueur):
        """Carré vert (pose possible) ou rouge (impossible) sous la souris, avec le vaisseau
        incliné comme il sera posé."""
        vaisseau, ok = self._candidat(monde_x, monde_y, hero, game_map, modele)
        couleur, bordure = (COULEUR_ZONE, COULEUR_ZONE_BORDURE) if ok else (
            COULEUR_ZONE_REFUSEE, COULEUR_ZONE_REFUSEE_BORDURE)
        rect = vaisseau.rect(hero).move(-camera_offset[0], -camera_offset[1])
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        surface.fill(couleur)
        screen.blit(surface, rect)
        pygame.draw.rect(screen, bordure, rect, 3)
        image = pygame.transform.rotate(self._icone(modele), vaisseau.angle)
        image.set_alpha(170)
        screen.blit(image, image.get_rect(center=rect.center))

    def sous_souris(self, monde_x, monde_y, hero):
        for vaisseau in reversed(self.liste):
            if vaisseau.rect(hero).collidepoint(monde_x, monde_y):
                return vaisseau
        return None

    def _enlevable(self, vaisseau, joueur):
        """(True, "") si l'outil de déconstruction peut reprendre ce vaisseau, sinon (False, la raison)."""
        if vaisseau is joueur.pilote:
            return False, "On ne peut pas enlever le vaisseau qu'on pilote"
        if vaisseau in self.occupes():
            return False, "Quelqu'un est dedans"
        if not self.proche(vaisseau, joueur.hero):
            return False, "Trop loin du vaisseau"
        if not vaisseau.coffre.vide:
            return False, "Vide d'abord son carburant (clic droit dessus)"
        return True, ""

    def enlever(self, monde_x, monde_y, joueur, inventaire):
        """Outil de déconstruction : le vaisseau sous le point visé retourne dans l'inventaire (s'il est
        proche, pas piloté, et que son carburant a été repris). Renvoie le vaisseau enlevé, ou None."""
        vaisseau = self.sous_souris(monde_x, monde_y, joueur.hero)
        if vaisseau is None:
            return None
        ok, raison = self._enlevable(vaisseau, joueur)
        if ok and inventaire.place_pour(vaisseau.modele) < 1:
            ok, raison = False, "Inventaire plein"
        if not ok:
            self._dire(raison)
            return None
        self.liste.remove(vaisseau)
        inventaire.ajouter_objet(vaisseau.modele)
        return vaisseau

    def apercu_enlever(self, screen, camera_offset, monde_x, monde_y, joueur):
        """Outil de déconstruction : entoure le vaisseau sous la souris, en orange si on peut l'enlever,
        en rouge sinon. Renvoie True s'il y a un vaisseau sous la souris."""
        hero = joueur.hero
        vaisseau = self.sous_souris(monde_x, monde_y, hero)
        if vaisseau is None:
            return False
        ok, _ = self._enlevable(vaisseau, joueur)
        couleur, bordure = (COULEUR_DECONSTRUCTION, COULEUR_DECONSTRUCTION_BORDURE) if ok else (
            COULEUR_ZONE_REFUSEE, COULEUR_ZONE_REFUSEE_BORDURE)
        rect = vaisseau.rect(hero).move(-camera_offset[0], -camera_offset[1])
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        surface.fill(couleur)
        screen.blit(surface, rect)
        pygame.draw.rect(screen, bordure, rect, 3)
        return True

    def proche(self, vaisseau, hero):
        image = hero.images["immobile", "bas"][0]
        hx, hy = hero.x + image.get_width() / 2, hero.y + image.get_height() / 2
        return math.hypot(vaisseau.centre(hero)[0] - hx, vaisseau.centre(hero)[1] - hy) <= vaisseau.modele.PORTEE

    def monter(self, vaisseau, joueur):
        hero = joueur.hero
        if not self.proche(vaisseau, hero):
            self._dire("Trop loin du vaisseau")
            return False
        if vaisseau in self.occupes():
            self._dire("Quelqu'un est déjà dedans")
            return False
        joueur.pilote = vaisseau
        hero.x, hero.y = vaisseau.x, vaisseau.y
        return True

    def descendre(self, joueur, game_map):
        """Le héros sort sur place : impossible au-dessus du vide (il y resterait coincé)."""
        hero, vaisseau = joueur.hero, joueur.pilote
        if vaisseau is None:
            return False
        if game_map.collides(hero.hitbox(hero.x, hero.y)):
            self._dire("Impossible de descendre ici : pose-toi sur une base")
            return False
        vaisseau.x, vaisseau.y = hero.x, hero.y
        joueur.pilote = None
        return True

    # ---- vol ----
    def update(self, dt, keys, joueur):
        """Le vaisseau piloté vole (ZQSD), sans tenir compte du vide, tant qu'il a de l'hydrogène
        ET de l'oxygène."""
        hero, vaisseau = joueur.hero, joueur.pilote
        if vaisseau is None:
            return
        dx = keys[pygame.K_d] - keys[pygame.K_q]
        dy = keys[pygame.K_s] - keys[pygame.K_z]
        if dx or dy:
            if vaisseau.peut_voler():
                norme = math.hypot(dx, dy)
                vaisseau.x += dx / norme * vaisseau.modele.VITESSE * dt
                vaisseau.y += dy / norme * vaisseau.modele.VITESSE * dt
                vaisseau.bruler(dt)
                vaisseau.angle = angle_nez(dx, dy)  # le nez suit la direction
            else:
                self._dire("Panne : il faut de l'hydrogène et de l'oxygène")
        hero.x, hero.y = vaisseau.x, vaisseau.y

    # ---- téléportation ----
    def shards_a_bord(self, joueur):
        """Shards du vaisseau piloté si c'est un téléporteur, sinon None (pas de téléportation)."""
        return None if joueur.pilote is None else joueur.pilote.shards

    def teleporter(self, tx, ty, game_map, joueur):
        """Le vaisseau téléporteur piloté (et le héros dedans) saute au milieu de la case (tx, ty),
        contre des shards. Renvoie True si c'est fait."""
        hero, vaisseau = joueur.hero, joueur.pilote
        if vaisseau is None or vaisseau.shards is None:
            return False
        modele = vaisseau.modele
        if vaisseau.shards < modele.SHARDS_PAR_SAUT:
            self._dire("Il faut un shard dans le vaisseau pour se téléporter")
            return False
        vaisseau.coffre.nombres[modele.CASE_SHARD] -= modele.SHARDS_PAR_SAUT
        if vaisseau.coffre.nombres[modele.CASE_SHARD] <= 0:
            vaisseau.coffre.objets[modele.CASE_SHARD], vaisseau.coffre.nombres[modele.CASE_SHARD] = None, 0
        image = hero.images["immobile", "bas"][0]
        vaisseau.x = (tx + 0.5) * game_map.tilewidth - image.get_width() / 2
        vaisseau.y = (ty + 0.5) * game_map.tileheight - image.get_height() / 2
        hero.x, hero.y = vaisseau.x, vaisseau.y
        self.eclair_fin = pygame.time.get_ticks() + DUREE_ECLAIR
        self._dire("Téléportation !")
        return True

    # ---- dessin ----
    def _icone(self, modele):
        if modele not in self._images:
            image = pygame.image.load(modele.ICONE).convert_alpha()
            self._images[modele] = pygame.transform.smoothscale(image, (modele.TAILLE,) * 2)
        return self._images[modele]

    def draw(self, screen, camera_offset, hero, vaisseaux=None):
        """Dessine les vaisseaux (tous, ou seulement ceux de la liste `vaisseaux`)."""
        for vaisseau in self.liste if vaisseaux is None else vaisseaux:
            image = pygame.transform.rotate(self._icone(vaisseau.modele), vaisseau.angle)
            centre = vaisseau.centre(hero)
            screen.blit(image, image.get_rect(center=(centre[0] - camera_offset[0], centre[1] - camera_offset[1])))

    def draw_hud(self, screen, joueur, inventaire_ouvert=False):
        """Jauges de carburant et aide, en bas à droite, quand on pilote (et l'éclair violet juste
        après une téléportation). `joueur` : celui de cette machine."""
        pilote = joueur.pilote
        reste = self.eclair_fin - pygame.time.get_ticks()
        if reste > 0:
            voile = pygame.Surface(screen.get_size())
            voile.fill(COULEUR_TELEPORTATION)
            voile.set_alpha(round(200 * reste / DUREE_ECLAIR))
            screen.blit(voile, (0, 0))
        if pilote is not None:
            largeur, hauteur = screen.get_size()
            unites = pilote.modele.UNITES_PAR_OBJET
            for i, (nom, couleur) in enumerate((("Hydrogène", COULEUR_H), ("Oxygène", COULEUR_O))):
                plein = min(1.0, (pilote.reserves[i] + pilote.coffre.nombres[i] * unites) / unites)
                zone = pygame.Rect(largeur - 330, hauteur - 130 + i * 34, 280, 22)
                pygame.draw.rect(screen, (20, 20, 30), zone, border_radius=8)
                pygame.draw.rect(screen, couleur, (zone.x, zone.y, int(zone.width * plein), zone.height),
                                 border_radius=8)
                pygame.draw.rect(screen, (150, 150, 170), zone, 2, border_radius=8)
                texte = self.police.render(nom, True, COULEUR_TEXTE)
                screen.blit(texte, texte.get_rect(midright=(zone.x - 8, zone.centery)))
            aide = "ZQSD : voler   F : carburant   E : descendre"
            if pilote.shards is not None:
                texte = self.police.render(f"Shards : {pilote.shards}", True, COULEUR_TELEPORTATION)
                screen.blit(texte, texte.get_rect(bottomright=(largeur - 50, hauteur - 136)))
                aide = "ZQSD : voler   F : téléportation (et carburant)   E : descendre"
            aide = self.police.render(aide, True, COULEUR_TEXTE)
            screen.blit(aide, aide.get_rect(bottomright=(largeur - 50, hauteur - 40)))
        if self.message and pygame.time.get_ticks() < self.message_fin:
            texte = self.police.render(self.message, True, COULEUR_ALERTE)
            screen.blit(texte, texte.get_rect(midbottom=(screen.get_width() // 2, screen.get_height() - 140)))

    # ---- sauvegarde ----
    def exporter(self, ids):
        return {"liste": [{"x": v.x, "y": v.y, "type": v.modele.__name__, "objets": ids(v.coffre.objets),
                           "nombres": v.coffre.nombres, "reserves": v.reserves, "angle": v.angle}
                          for v in self.liste]}
        # (qui pilote quoi est sauvegardé avec chaque joueur, voir systeme/sauvegarde.py)

    def importer_reseau(self, donnees, objets, ignorer=()):
        """Multijoueur : recopie les vaisseaux envoyés par l'hôte en gardant les objets déjà là.
        Reconstruire la liste à chaque envoi casserait les panneaux ouverts dessus et le vaisseau
        que l'on pilote ; ici on met à jour en place tant que c'est le même vaisseau.

        `ignorer` : places dans la liste dont on vient de changer le contenu ici (notre version
        l'emporte le temps de l'aller-retour, voir monde/partie.py)."""
        envoyes = donnees.get("liste", [])
        for i, d in enumerate(envoyes):
            if i in ignorer or not isinstance(d, dict):
                continue
            modele = objets.get(d.get("type"), vaisseau_joueur)
            if i < len(self.liste) and self.liste[i].modele is modele:
                vaisseau = self.liste[i]
            else:
                vaisseau = VaisseauJoueur(d["x"], d["y"], modele)
                if i < len(self.liste):
                    self.liste[i] = vaisseau
                else:
                    self.liste.append(vaisseau)
            vaisseau.x, vaisseau.y = d["x"], d["y"]
            vaisseau.angle = d.get("angle", 0)
            vaisseau.coffre.objets[:] = [objets.get(o) for o in d["objets"]]
            vaisseau.coffre.nombres[:] = d["nombres"]
            vaisseau.reserves[:] = d.get("reserves", [0.0, 0.0])
        # Ceux qui ont été repris par quelqu'un disparaissent... sauf un vaisseau qu'un joueur d'ici
        # est en train de piloter : il vient peut-être d'être posé et l'hôte ne le connaît pas
        # encore. Le retirer de la liste laisserait son pilote nulle part (ni héros ni vaisseau
        # dessinés), le temps que l'hôte le renvoie.
        occupes = self.occupes()
        self.liste[len(envoyes):] = [v for v in self.liste[len(envoyes):] if v in occupes]

    def importer(self, donnees, objets):
        self.liste.clear()
        for d in donnees.get("liste", []):
            # "type" : absent des sauvegardes d'avant le téléporteur (vaisseau simple)
            vaisseau = VaisseauJoueur(d["x"], d["y"], objets.get(d.get("type"), vaisseau_joueur))
            vaisseau.coffre.objets[:] = [objets.get(i) for i in d["objets"]]
            vaisseau.coffre.nombres[:] = d["nombres"]
            vaisseau.reserves[:] = d.get("reserves", [0.0, 0.0])
            vaisseau.angle = d.get("angle", 0)
            self.liste.append(vaisseau)


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
