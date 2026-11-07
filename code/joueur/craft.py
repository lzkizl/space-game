import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import (antenne, base, base_robot, boitier, canon_electromagnetique, coffre, foreuse, four, oxygenateur,
                          panneau, plante, reacteur,
                          reacteur_nucleaire, table_recherche, telescope, tourelle, tourelle_plasma, vaisseau_joueur,
                          vaisseau_teleporteur)
from systeme.ressources import (BALLE_PERFORMANTE, BARRE_NUCLEAIRE, BOUTEILLE, CUIVRE, FER, FIBRE, GLACE, KIT_MEDICAL, MUNITION, SHARD,
                                SOUFRE, TUNGSTENE, URANIUM, VERRE)
from joueur.inventory import nom_objet
from systeme import ecran
from interface.ui import (COULEUR_ACCENT, COULEUR_ALERTE_TEXTE, COULEUR_BORDURE, COULEUR_BOUTON,
                COULEUR_BOUTON_SURVOL, COULEUR_TEXTE, COULEUR_TEXTE_GRIS, COULEUR_TITRE, dessiner_bouton,
                dessiner_infobulle, dessiner_panneau)

# =============================================
# ==== Recettes rangées par catégorie (un onglet chacune) :
# ==== (nom de la catégorie, [(objet fabriqué, nom affiché, {ingrédient: quantité}), ...])
# =============================================
CATEGORIES = [
    ("Structures", [
        (base, "Base", {FER: 5}),
        (coffre, "Coffre", {FER: 8, CUIVRE: 2}),
        (plante, "Plante", {GLACE: 3, FER: 2}),
        (antenne, "Antenne radio", {FER: 10, CUIVRE: 6, VERRE: 2}),
        (boitier, "Boîtier", {FER: 6, CUIVRE: 8, VERRE: 2}),
        (table_recherche, "Table de recherche", {FER: 15, CUIVRE: 8, VERRE: 6}),
    ]),
    ("Énergie", [
        (panneau, "Panneau solaire", {FER: 2, VERRE: 4}),
        (reacteur, "Réacteur", {FER: 20, CUIVRE: 10, VERRE: 5, TUNGSTENE: 5}),
        (reacteur_nucleaire, "Réacteur nucléaire",
         {FER: 120, CUIVRE: 60, VERRE: 40, TUNGSTENE: 30, SOUFRE: 15, URANIUM: 20}),
    ]),
    ("Machines", [
        (four, "Four", {FER: 10, CUIVRE: 4, VERRE: 2}),
        (oxygenateur, "Oxygénateur", {FER: 15, CUIVRE: 6, VERRE: 4}),
        (base_robot, "Station de robot", {FER: 10, CUIVRE: 5}),
        (vaisseau_joueur, "Vaisseau", {FER: 30, CUIVRE: 15, VERRE: 10}),
        (vaisseau_teleporteur, "Vaisseau téléporteur", {vaisseau_joueur: 1, TUNGSTENE: 20, SHARD: 5}),
        (telescope, "Télescope NASA", {panneau: 4, FER: 20, CUIVRE: 10, VERRE: 15, TUNGSTENE: 5}),
        (foreuse, "Foreuse", {FER: 25, CUIVRE: 10, TUNGSTENE: 4}),   # (se pose sur un gisement de la Terre ou de Mars)
    ]),
    ("Défense", [
        (tourelle, "Tourelle", {FER: 15, CUIVRE: 8, VERRE: 2}),
        (canon_electromagnetique, "Canon électromagnétique", {FER: 30, CUIVRE: 20, VERRE: 5, TUNGSTENE: 10}),
        (tourelle_plasma, "Tourelle plasma", {FER: 30, CUIVRE: 25, VERRE: 10, TUNGSTENE: 12, URANIUM: 4}),
        (MUNITION, "Munition", {FER: 1, CUIVRE: 1}),
        (BALLE_PERFORMANTE, "Balle performante", {TUNGSTENE: 1, CUIVRE: 3}),
    ]),
    ("Objets", [
        (BOUTEILLE, "Bouteille d'eau", {GLACE: 1}),
        (KIT_MEDICAL, "Kit médical", {FIBRE: 3, GLACE: 1}),
        # (les clés USB ne se fabriquent pas : on les trouve dans les navettes échouées)
    ]),
    ("Ressources", [  # ressources transformées, qui servent à faire marcher les machines
        (BARRE_NUCLEAIRE, "Barre nucléaire", {URANIUM: 4, TUNGSTENE: 1, VERRE: 1}),
    ]),
]
RECETTES = [recette for _, recettes in CATEGORIES for recette in recettes]  # toutes, sans les catégories

LARGEUR_CARTE = 460     # une recette = une carte (icône, nom, ingrédients, bouton Fabriquer)
HAUTEUR_CARTE = 176     # (place pour une 2e ligne d'ingrédients au-dessus du bouton)
ESPACE = 16
MARGE_PANNEAU = 30
HAUTEUR_ENTETE = 180    # titre + onglets
Y_ONGLETS = 96          # haut des onglets, depuis le haut du panneau
HAUTEUR_ONGLET = 50
ESPACE_ONGLETS = 10
HAUTEUR_PIED = 60
HAUTEUR_BOUTON = 44
TAILLE_PUCE = 30        # icône d'un ingrédient
DUREE_MESSAGE = 2000  # millisecondes

COULEUR_CARTE = (24, 24, 40)
COULEUR_PRET = (110, 200, 140)


class Craft:
    """Menu de la table de craft (ouvert par un clic sur une table posée) : les recettes sont
    rangées en onglets (clic, flèches gauche/droite ou 1 à 5). Chaque recette prend ses
    ingrédients dans l'inventaire et y met l'objet fabriqué (un exemplaire par clic)."""

    def __init__(self, screen_width, screen_height):
        self.ouvert = False
        self.onglet = 0  # catégorie affichée (gardée d'une ouverture à l'autre)
        self.message = ""
        self.message_fin = 0
        self.police_titre = pygame.font.Font(None, 80)
        self.police = pygame.font.Font(None, 40)
        self.police_petite = pygame.font.Font(None, 30)
        self._puces = {}  # ingrédient -> petite icône
        self.recherches = None  # l'arbre de recherche (donné par le jeu) ; None : tout est débloqué

        # le panneau a la même taille pour tous les onglets : celle de la plus grande catégorie.
        # Les cartes sont rangées en colonnes : le plus petit nombre (2 à 4) qui tient dans l'écran
        nb_max = max(len(recettes) for _, recettes in CATEGORIES)
        colonnes = 4
        for essai in (2, 3, 4):
            rangs = -(-nb_max // essai)
            if HAUTEUR_ENTETE + rangs * (HAUTEUR_CARTE + ESPACE) + HAUTEUR_PIED <= screen_height - 40:
                colonnes = essai
                break
        rangs = -(-nb_max // colonnes)
        largeur_carte = min(LARGEUR_CARTE, (screen_width - 40 - 2 * MARGE_PANNEAU - (colonnes - 1) * ESPACE) // colonnes)
        hauteur_carte = min(HAUTEUR_CARTE, (screen_height - 40 - HAUTEUR_ENTETE - HAUTEUR_PIED) // rangs - ESPACE)
        largeur = colonnes * largeur_carte + (colonnes - 1) * ESPACE + 2 * MARGE_PANNEAU
        hauteur = HAUTEUR_ENTETE + rangs * (hauteur_carte + ESPACE) - ESPACE + HAUTEUR_PIED
        self.panneau = pygame.Rect(0, 0, largeur, hauteur)
        self.panneau.center = (screen_width // 2, screen_height // 2)

        # onglets : toute la largeur utile, partagée entre les catégories
        utile = largeur - 2 * MARGE_PANNEAU
        largeur_onglet = (utile - (len(CATEGORIES) - 1) * ESPACE_ONGLETS) // len(CATEGORIES)
        self.onglets = [pygame.Rect(self.panneau.x + MARGE_PANNEAU + i * (largeur_onglet + ESPACE_ONGLETS),
                                    self.panneau.y + Y_ONGLETS, largeur_onglet, HAUTEUR_ONGLET)
                        for i in range(len(CATEGORIES))]

        self.lignes = []  # (carte, bouton) pour chaque place de recette (les premières servent)
        for i in range(nb_max):
            rang, colonne = divmod(i, colonnes)              # on remplit une rangée après l'autre
            x = self.panneau.x + MARGE_PANNEAU + colonne * (largeur_carte + ESPACE)
            y = self.panneau.y + HAUTEUR_ENTETE + rang * (hauteur_carte + ESPACE)
            carte = pygame.Rect(x, y, largeur_carte, hauteur_carte)
            bouton = pygame.Rect(carte.x + 14, carte.bottom - 14 - HAUTEUR_BOUTON, carte.width - 28, HAUTEUR_BOUTON)
            self.lignes.append((carte, bouton))

    @property
    def recettes(self):
        """Recettes de l'onglet affiché (celles qui attendent une recherche n'y sont pas)."""
        return [recette for recette in CATEGORIES[self.onglet][1] if self.debloquee(recette[0])]

    @staticmethod
    def possible(inventaire, ingredients):
        return all(inventaire.compter(objet) >= n for objet, n in ingredients.items())

    def debloquee(self, objet):
        """False si la recette attend une recherche (table de recherche)."""
        return self.recherches is None or self.recherches.debloque(objet)

    def fabriquer(self, inventaire, objet, ingredients):
        if not self.debloquee(objet) or not self.possible(inventaire, ingredients):
            return
        for ingredient, n in ingredients.items():
            inventaire.retirer(ingredient, n)
        if inventaire.place_pour(objet) >= 1:
            inventaire.ajouter_objet(objet)
            return
        for ingredient, n in ingredients.items():  # plus de place : on rend les ingrédients
            inventaire.ajouter_objet(ingredient, n)
        self.message = "Inventaire plein"
        self.message_fin = pygame.time.get_ticks() + DUREE_MESSAGE

    # ---- évènements ----
    def ouvrir(self, inventaire):
        """Ouvre la table (appelé quand on clique sur une table de craft posée)."""
        self.ouvert = True
        inventaire.ouvert = False

    def handle_event(self, event, inventaire):
        """C / Echap ferment la table, un clic hors du panneau aussi. Quand elle est
        ouverte, tout clic est absorbé. Renvoie True si l'évènement est consommé."""
        if not self.ouvert:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_c, pygame.K_ESCAPE):
                self.ouvert = False  # (Echap ne doit pas ouvrir la pause)
                return True
            if event.key == pygame.K_TAB:
                self.ouvert = False  # Tab ouvre l'inventaire à la place
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.onglet = (self.onglet + (1 if event.key == pygame.K_RIGHT else -1)) % len(CATEGORIES)
                return True
            if pygame.K_1 <= event.key < pygame.K_1 + len(CATEGORIES):
                self.onglet = event.key - pygame.K_1
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panneau.collidepoint(event.pos):
                self.ouvert = False
                return True
            for i, rect in enumerate(self.onglets):
                if rect.collidepoint(event.pos):
                    self.onglet = i
                    return True
            for (objet, _, ingredients), (_, bouton) in zip(self.recettes, self.lignes):
                if bouton.collidepoint(event.pos):
                    self.fabriquer(inventaire, objet, ingredients)
            return True
        return False

    # ---- dessin ----
    def _puce(self, inventaire, ingredient):
        if ingredient not in self._puces:
            self._puces[ingredient] = pygame.transform.smoothscale(inventaire.icone(ingredient),
                                                                   (TAILLE_PUCE, TAILLE_PUCE))
        return self._puces[ingredient]

    def _dessiner_onglets(self, screen, inventaire, souris):
        """Un onglet par catégorie ; la pastille verte compte ce qu'on peut y fabriquer."""
        for i, (rect, (nom, recettes)) in enumerate(zip(self.onglets, CATEGORIES)):
            actif = i == self.onglet
            fond = COULEUR_BOUTON_SURVOL if actif or rect.collidepoint(souris) else COULEUR_BOUTON
            pygame.draw.rect(screen, fond, rect, border_radius=12)
            pygame.draw.rect(screen, COULEUR_ACCENT if actif else COULEUR_BORDURE, rect, 3 if actif else 2,
                             border_radius=12)
            image = self.police_petite.render(nom, True, COULEUR_TITRE if actif else COULEUR_TEXTE_GRIS)
            screen.blit(image, image.get_rect(center=rect.center))

            prets = sum(self.debloquee(objet) and self.possible(inventaire, ingredients)
                        for objet, _, ingredients in recettes)  # (les recettes à rechercher ne comptent pas)
            if prets:
                centre = (rect.right - 14, rect.y + 14)
                pygame.draw.circle(screen, COULEUR_PRET, centre, 11)
                chiffre = self.police_petite.render(str(prets), True, (10, 30, 15))
                screen.blit(chiffre, chiffre.get_rect(center=(centre[0], centre[1] + 1)))

    def draw(self, screen, inventaire):
        if not self.ouvert:
            return
        dessiner_panneau(screen, self.panneau)
        titre = self.police_titre.render("Fabrication", True, COULEUR_TITRE)
        screen.blit(titre, (self.panneau.x + MARGE_PANNEAU, self.panneau.y + 28))
        aide = self.police_petite.render(f"Flèches ou 1-{len(CATEGORIES)} : catégorie   ·   Echap pour fermer", True,
                                         COULEUR_TEXTE_GRIS)
        screen.blit(aide, aide.get_rect(topright=(self.panneau.right - MARGE_PANNEAU, self.panneau.y + 44)))
        souris = ecran.souris()
        self._dessiner_onglets(screen, inventaire, souris)
        pygame.draw.line(screen, COULEUR_BORDURE, (self.panneau.x + MARGE_PANNEAU, self.panneau.y + HAUTEUR_ENTETE - 14),
                         (self.panneau.right - MARGE_PANNEAU, self.panneau.y + HAUTEUR_ENTETE - 14), 2)
        bulle = None

        if not self.recettes:  # tout cet onglet attend des recherches
            image = self.police.render("Rien à fabriquer ici pour l'instant : fais des recherches", True,
                                       COULEUR_TEXTE_GRIS)
            screen.blit(image, image.get_rect(midtop=(self.panneau.centerx, self.panneau.y + HAUTEUR_ENTETE + 40)))

        for (objet, nom, ingredients), (carte, bouton) in zip(self.recettes, self.lignes):
            ok = self.possible(inventaire, ingredients)
            pygame.draw.rect(screen, COULEUR_CARTE, carte, border_radius=16)
            pygame.draw.rect(screen, COULEUR_PRET if ok else COULEUR_BORDURE, carte, 2, border_radius=16)

            # icône dans une pastille, puis le nom
            pastille = pygame.Rect(0, 0, 76, 76)
            pastille.topleft = (carte.x + 14, carte.y + 14)
            pygame.draw.rect(screen, COULEUR_BOUTON, pastille, border_radius=14)
            icone = inventaire.icone(objet)
            screen.blit(icone, icone.get_rect(center=pastille.center))
            image = self.police.render(nom, True, COULEUR_TEXTE if ok else COULEUR_TEXTE_GRIS)
            screen.blit(image, (pastille.right + 16, carte.y + 16))

            # ingrédients : icône + possédé/nécessaire, en rouge s'il en manque
            x = pastille.right + 16
            y = carte.y + 52
            for ingredient, n in ingredients.items():
                possede = inventaire.compter(ingredient)
                couleur = COULEUR_TEXTE if possede >= n else COULEUR_ALERTE_TEXTE
                puce = self._puce(inventaire, ingredient)
                texte = self.police_petite.render(f"{min(possede, 999)}/{n}", True, couleur)
                zone = pygame.Rect(x, y, TAILLE_PUCE + 6 + texte.get_width(), TAILLE_PUCE)
                if zone.right > carte.right - 10:  # plus de place : on passe à la ligne
                    x, y = pastille.right + 16, y + TAILLE_PUCE + 4
                    zone.topleft = (x, y)
                screen.blit(puce, zone.topleft)
                screen.blit(texte, texte.get_rect(midleft=(zone.x + TAILLE_PUCE + 6, zone.centery)))
                if zone.collidepoint(souris):
                    bulle = nom_objet(ingredient)  # (un ingrédient peut être une construction : panneau...)
                x = zone.right + 16

            dessiner_bouton(screen, self.police, bouton, "Fabriquer", ok and bouton.collidepoint(souris))
            if not ok:  # grisé : voile sur le bouton
                voile = pygame.Surface(bouton.size, pygame.SRCALPHA)
                pygame.draw.rect(voile, (0, 0, 0, 140), voile.get_rect(), border_radius=14)
                screen.blit(voile, bouton)

        if bulle:
            dessiner_infobulle(screen, self.police_petite, bulle, souris)

        if self.message and pygame.time.get_ticks() < self.message_fin:
            image = self.police.render(self.message, True, COULEUR_ACCENT)
            screen.blit(image, image.get_rect(midbottom=(self.panneau.centerx, self.panneau.bottom - 14)))
        else:
            image = self.police_petite.render("Rouge : ingrédient manquant  ·  contour vert : on peut fabriquer", True,
                                              COULEUR_TEXTE_GRIS)
            screen.blit(image, image.get_rect(midbottom=(self.panneau.centerx, self.panneau.bottom - 18)))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
