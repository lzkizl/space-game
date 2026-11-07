import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from construction import (antenne, boitier, canon_electromagnetique, reacteur, tourelle_plasma, reacteur_nucleaire, telescope, vaisseau_joueur,
                          vaisseau_teleporteur)
from systeme.ressources import (BALLE_PERFORMANTE, BARRE_NUCLEAIRE, CUIVRE, FER, PROCESSEUR, RAM, SHARD, SOUFRE, TUNGSTENE, URANIUM,
                                VERRE)
from systeme import ecran
from interface.ui import (COULEUR_ACCENT, COULEUR_ALERTE_TEXTE, COULEUR_BORDURE, COULEUR_BOUTON, COULEUR_TEXTE,
                          COULEUR_TEXTE_GRIS, COULEUR_TITRE, dessiner_bouton, dessiner_infobulle, dessiner_panneau)


# =============================================
# ==== Arbre de recherche (table de recherche) : chaque recherche coûte des ressources (prises dans
# ==== l'inventaire) et débloque des recettes de la table de craft. Ce qu'il faut pour survivre (base,
# ==== coffre, plante, panneau solaire, four, oxygénateur, tourelle, station de robot...) n'est dans
# ==== aucune recherche : c'est débloqué dès le départ.
# =============================================
class Noeud:
    def __init__(self, cle, nom, colonne, ligne, cout, debloque, avant=()):
        self.cle = cle            # identifiant (sauvegardé)
        self.nom = nom
        self.colonne = colonne    # place dans l'arbre : colonne (de gauche à droite)...
        self.ligne = ligne        # ...et ligne (peut être entre deux : 1.5)
        self.cout = cout          # {ressource: quantité}
        self.debloque = debloque  # objets dont la recette est débloquée
        self.avant = avant        # clés des recherches à faire d'abord


RECHERCHES = [
    Noeud("electronique", "Électronique", 0, 1, {CUIVRE: 20, VERRE: 10, PROCESSEUR: 1}, [boitier, antenne]),
    Noeud("propulsion", "Propulsion", 0, 3, {FER: 30, CUIVRE: 10, TUNGSTENE: 5}, [reacteur]),
    Noeud("astronomie", "Astronomie", 1, 0, {VERRE: 20, TUNGSTENE: 5, RAM: 2}, [telescope], ("electronique",)),
    Noeud("defense", "Défense", 1, 1, {FER: 40, CUIVRE: 20, TUNGSTENE: 10, SHARD: 2},
          [canon_electromagnetique, BALLE_PERFORMANTE], ("electronique",)),
    Noeud("fission", "Fission nucléaire", 1, 2, {URANIUM: 10, TUNGSTENE: 10, SOUFRE: 5, SHARD: 2},
          [reacteur_nucleaire, BARRE_NUCLEAIRE], ("electronique",)),
    Noeud("vaisseau", "Vaisseau spatial", 1, 3, {FER: 40, CUIVRE: 20, TUNGSTENE: 8, SHARD: 1}, [vaisseau_joueur],
          ("propulsion",)),
    Noeud("plasma", "Plasma", 2, 1, {SHARD: 6, URANIUM: 8, TUNGSTENE: 15, CUIVRE: 30}, [tourelle_plasma],
          ("defense", "fission")),
    Noeud("teleportation", "Téléportation", 2, 2.5, {SHARD: 10, TUNGSTENE: 15, URANIUM: 5, PROCESSEUR: 2},
          [vaisseau_teleporteur], ("vaisseau", "fission")),
]
PAR_CLE = {noeud.cle: noeud for noeud in RECHERCHES}
NOEUD_DE = {objet: noeud for noeud in RECHERCHES for objet in noeud.debloque}  # objet -> sa recherche

LARGEUR_NOEUD = 420
HAUTEUR_NOEUD = 236
ECART_COLONNES = 80     # place pour les traits entre une recherche et celles qu'elle débloque
ECART_LIGNES = 24
MARGE_PANNEAU = 30
HAUTEUR_ENTETE = 120
HAUTEUR_PIED = 60
HAUTEUR_BOUTON = 44
TAILLE_ICONE = 40       # icône d'un objet débloqué
TAILLE_PUCE = 30        # icône d'une ressource du coût
DUREE_MESSAGE = 2500    # millisecondes

COULEUR_CARTE = (24, 24, 40)
COULEUR_FAITE = (110, 200, 140)
COULEUR_VERROU = (70, 70, 90)
COULEUR_CACHEE = (6, 6, 10)  # carte d'une recherche pas encore accessible


class Recherche:
    """Menu de la table de recherche (ouvert par un clic sur une table posée) et les recherches faites.
    Echap, Tab ou un clic hors du panneau le ferment."""

    def __init__(self, screen_width, screen_height):
        self.ouvert = False
        self.faites = set()  # clés des recherches faites (sauvegardé)
        self.message = ""
        self.message_fin = 0
        self.police_titre = pygame.font.Font(None, 80)
        self.police = pygame.font.Font(None, 38)
        self.police_petite = pygame.font.Font(None, 28)
        self._puces = {}  # (objet, taille) -> petite icône

        colonnes = max(n.colonne for n in RECHERCHES) + 1
        lignes = max(n.ligne for n in RECHERCHES) + 1
        largeur_noeud = min(LARGEUR_NOEUD, (screen_width - 40 - 2 * MARGE_PANNEAU - (colonnes - 1) * ECART_COLONNES)
                            // colonnes)
        hauteur_noeud = min(HAUTEUR_NOEUD, int((screen_height - 40 - HAUTEUR_ENTETE - HAUTEUR_PIED
                                                - (lignes - 1) * ECART_LIGNES) // lignes))
        largeur = colonnes * largeur_noeud + (colonnes - 1) * ECART_COLONNES + 2 * MARGE_PANNEAU
        hauteur = HAUTEUR_ENTETE + int(lignes * hauteur_noeud + (lignes - 1) * ECART_LIGNES) + HAUTEUR_PIED
        self.panneau = pygame.Rect(0, 0, largeur, hauteur)
        self.panneau.center = (screen_width // 2, screen_height // 2)
        self.cartes = {}  # clé -> (carte, bouton)
        for noeud in RECHERCHES:
            x = self.panneau.x + MARGE_PANNEAU + noeud.colonne * (largeur_noeud + ECART_COLONNES)
            y = self.panneau.y + HAUTEUR_ENTETE + round(noeud.ligne * (hauteur_noeud + ECART_LIGNES))
            carte = pygame.Rect(x, y, largeur_noeud, hauteur_noeud)
            bouton = pygame.Rect(carte.x + 14, carte.bottom - 14 - HAUTEUR_BOUTON, carte.width - 28, HAUTEUR_BOUTON)
            self.cartes[noeud.cle] = (carte, bouton)

    # ---- état ----
    def debloque(self, objet):
        """True si on peut fabriquer cet objet : il n'est dans aucune recherche, ou sa recherche est faite."""
        noeud = NOEUD_DE.get(objet)
        return noeud is None or noeud.cle in self.faites

    @staticmethod
    def recherche_de(objet):
        """La recherche qui débloque cet objet (None : débloqué dès le départ)."""
        return NOEUD_DE.get(objet)

    def accessible(self, noeud):
        """True si les recherches d'avant sont faites (et pas encore celle-ci)."""
        return noeud.cle not in self.faites and all(cle in self.faites for cle in noeud.avant)

    def visible(self, noeud):
        """On ne voit que les recherches faites et celles qu'on peut faire maintenant : les suivantes sont
        des cartes noires (voir _dessiner_cachee)."""
        return noeud.cle in self.faites or self.accessible(noeud)

    def possible(self, noeud, inventaire):
        return self.accessible(noeud) and all(inventaire.compter(objet) >= n for objet, n in noeud.cout.items())

    def rechercher(self, noeud, inventaire):
        if not self.possible(noeud, inventaire):
            return
        for objet, n in noeud.cout.items():
            inventaire.retirer(objet, n)
        self.faites.add(noeud.cle)
        self.message = f"Recherche terminée : {noeud.nom}"
        self.message_fin = pygame.time.get_ticks() + DUREE_MESSAGE

    # ---- sauvegarde ----
    def exporter(self):
        return sorted(self.faites)

    def importer(self, cles):
        self.faites = {cle for cle in cles if cle in PAR_CLE}  # (une recherche retirée du jeu est oubliée)

    # ---- évènements ----
    def ouvrir(self, inventaire):
        """Ouvre la table (appelé quand on clique sur une table de recherche posée)."""
        self.ouvert = True
        inventaire.ouvert = False

    def handle_event(self, event, inventaire):
        """Renvoie True si l'évènement est consommé (tout clic l'est quand le menu est ouvert)."""
        if not self.ouvert:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.ouvert = False  # (Echap ne doit pas ouvrir la pause)
                return True
            if event.key == pygame.K_TAB:
                self.ouvert = False  # Tab ouvre l'inventaire à la place
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panneau.collidepoint(event.pos):
                self.ouvert = False
                return True
            for noeud in RECHERCHES:
                if self.visible(noeud) and self.cartes[noeud.cle][1].collidepoint(event.pos):
                    self.rechercher(noeud, inventaire)
            return True
        return False

    # ---- dessin ----
    def _puce(self, inventaire, objet, taille):
        if (objet, taille) not in self._puces:
            self._puces[objet, taille] = pygame.transform.smoothscale(inventaire.icone(objet), (taille, taille))
        return self._puces[objet, taille]

    def _dessiner_liens(self, screen):
        """Un trait coudé de chaque recherche vers celles qu'elle permet (vert une fois faite)."""
        for noeud in RECHERCHES:
            arrivee = self.cartes[noeud.cle][0]
            for cle in noeud.avant:
                depart = self.cartes[cle][0]
                couleur = COULEUR_FAITE if cle in self.faites else COULEUR_VERROU
                x1, y1 = depart.right, depart.centery
                x2, y2 = arrivee.left, arrivee.centery
                xm = (x1 + x2) // 2
                pygame.draw.lines(screen, couleur, False, [(x1, y1), (xm, y1), (xm, y2), (x2, y2)], 4)
                pygame.draw.polygon(screen, couleur, [(x2, y2), (x2 - 12, y2 - 8), (x2 - 12, y2 + 8)])

    def _dessiner_cachee(self, screen, noeud):
        """Une recherche qu'on ne peut pas encore faire : une carte noire avec un « ? », sans rien dire d'elle."""
        carte = self.cartes[noeud.cle][0]
        pygame.draw.rect(screen, COULEUR_CACHEE, carte, border_radius=16)
        pygame.draw.rect(screen, COULEUR_VERROU, carte, 2, border_radius=16)
        texte = self.police_titre.render("?", True, COULEUR_VERROU)
        screen.blit(texte, texte.get_rect(center=carte.center))

    def _dessiner_noeud(self, screen, inventaire, noeud, souris):
        """Une carte : nom, ce qu'elle débloque, son coût, et le bouton (ou son état). Renvoie le texte de
        l'infobulle si la souris est sur une icône."""
        from joueur.inventory import nom_objet  # (ici : évite un import circulaire)
        carte, bouton = self.cartes[noeud.cle]
        faite = noeud.cle in self.faites
        bulle = None
        pygame.draw.rect(screen, COULEUR_CARTE, carte, border_radius=16)
        pygame.draw.rect(screen, COULEUR_FAITE if faite else COULEUR_ACCENT, carte, 3, border_radius=16)
        screen.blit(self.police.render(noeud.nom, True, COULEUR_TITRE), (carte.x + 16, carte.y + 14))

        # ce qu'elle débloque
        x, y = carte.x + 16, carte.y + 50
        texte = self.police_petite.render("Débloque :", True, COULEUR_TEXTE_GRIS)
        screen.blit(texte, texte.get_rect(midleft=(x, y + TAILLE_ICONE // 2)))
        x += texte.get_width() + 10
        for objet in noeud.debloque:
            zone = pygame.Rect(x, y, TAILLE_ICONE, TAILLE_ICONE)
            pygame.draw.rect(screen, COULEUR_BOUTON, zone.inflate(6, 6), border_radius=8)
            screen.blit(self._puce(inventaire, objet, TAILLE_ICONE), zone)
            if zone.collidepoint(souris):
                bulle = nom_objet(objet)
            x = zone.right + 12

        # son coût : icône + possédé/nécessaire, en rouge s'il en manque (sur 2 lignes si besoin)
        if not faite:
            x0 = carte.x + 16
            x, y = x0, carte.y + 102
            for objet, n in noeud.cout.items():
                possede = inventaire.compter(objet)
                couleur = COULEUR_TEXTE if possede >= n else COULEUR_ALERTE_TEXTE
                texte = self.police_petite.render(f"{min(possede, 999)}/{n}", True, couleur)
                zone = pygame.Rect(x, y, TAILLE_PUCE + 6 + texte.get_width(), TAILLE_PUCE)
                if zone.right > carte.right - 10:
                    x, y = x0, y + TAILLE_PUCE + 6
                    zone.topleft = (x, y)
                screen.blit(self._puce(inventaire, objet, TAILLE_PUCE), zone.topleft)
                screen.blit(texte, texte.get_rect(midleft=(zone.x + TAILLE_PUCE + 6, zone.centery)))
                if zone.collidepoint(souris):
                    bulle = nom_objet(objet)
                x = zone.right + 16

        # bouton, ou l'état de la recherche
        if faite:
            texte = self.police.render("Recherche faite", True, COULEUR_FAITE)
            screen.blit(texte, texte.get_rect(center=bouton.center))
        else:
            ok = self.possible(noeud, inventaire)
            dessiner_bouton(screen, self.police, bouton, "Rechercher", ok and bouton.collidepoint(souris))
            if not ok:  # grisé : il manque des ressources
                voile = pygame.Surface(bouton.size, pygame.SRCALPHA)
                pygame.draw.rect(voile, (0, 0, 0, 140), voile.get_rect(), border_radius=14)
                screen.blit(voile, bouton)
        return bulle

    def draw(self, screen, inventaire):
        if not self.ouvert:
            return
        dessiner_panneau(screen, self.panneau)
        titre = self.police_titre.render("Recherche", True, COULEUR_TITRE)
        screen.blit(titre, (self.panneau.x + MARGE_PANNEAU, self.panneau.y + 28))
        faites = len(self.faites)
        bilan = self.police.render(f"{faites} recherche{'s' if faites > 1 else ''} faite{'s' if faites > 1 else ''}",
                                   True, COULEUR_ACCENT)  # (sans le total : les suivantes restent une surprise)
        screen.blit(bilan, bilan.get_rect(topright=(self.panneau.right - MARGE_PANNEAU, self.panneau.y + 34)))
        aide = self.police_petite.render("Echap pour fermer", True, COULEUR_TEXTE_GRIS)
        screen.blit(aide, aide.get_rect(topright=(self.panneau.right - MARGE_PANNEAU, self.panneau.y + 70)))
        pygame.draw.line(screen, COULEUR_BORDURE, (self.panneau.x + MARGE_PANNEAU, self.panneau.y + HAUTEUR_ENTETE - 14),
                         (self.panneau.right - MARGE_PANNEAU, self.panneau.y + HAUTEUR_ENTETE - 14), 2)

        souris = ecran.souris()
        self._dessiner_liens(screen)
        bulle = None
        for noeud in RECHERCHES:
            if self.visible(noeud):
                bulle = self._dessiner_noeud(screen, inventaire, noeud, souris) or bulle
            else:
                self._dessiner_cachee(screen, noeud)
        if bulle:
            dessiner_infobulle(screen, self.police_petite, bulle, souris)

        if self.message and pygame.time.get_ticks() < self.message_fin:
            image = self.police.render(self.message, True, COULEUR_FAITE)
            screen.blit(image, image.get_rect(midbottom=(self.panneau.centerx, self.panneau.bottom - 16)))
        else:
            image = self.police_petite.render("Chaque recherche débloque des recettes de la table de craft", True,
                                              COULEUR_TEXTE_GRIS)
            screen.blit(image, image.get_rect(midbottom=(self.panneau.centerx, self.panneau.bottom - 20)))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
