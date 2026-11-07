import random

import pygame

from monde.generation import CASES_PAR_MORCEAU, morceau, morceaux_de_terrain
from systeme.settings import (CALQUE_BASE, CALQUE_EPAVES, MAP_PATH, MONDE_DELAI_DEFAUT, MONDE_DELAI_MAX,
                              VIDE_GIDS)
from interface.ui import (COULEUR_ACCENT, COULEUR_BORDURE, COULEUR_BOUTON, COULEUR_TEXTE, COULEUR_TEXTE_GRIS,
                          COULEUR_TITRE, dessiner_bouton)

# =============================================
# ==== Réglages
# =============================================
RAYON_APERCU = 10                    # morceaux affichés de chaque côté de l'origine
TAILLE_APERCU = 2 * RAYON_APERCU * CASES_PAR_MORCEAU  # 1 pixel par case
LARGEUR_CHAMP = 640
HAUTEUR_CHAMP = 70
LONGUEUR_GRAINE = 16
TAILLE_PETIT_BOUTON = 70
LARGEUR_BOUTON = 300
HAUTEUR_BOUTON = 70
COULEUR_FOND_APERCU = (8, 10, 24)
COULEUR_TERRAIN = (90, 110, 150)  # comme la minimap
FOCUS = ("graine", "delai", "creer", "retour")


class ReglagesMonde:
    """Page après le nom du monde : la graine (même graine = même monde, avec un aperçu du
    terrain généré) et le temps minimum avant les premières attaques de monstres.
    `evenement` renvoie "retour", None, ou {"graine", "delai"} quand on crée le monde."""

    def __init__(self, largeur, hauteur, chemin_carte=MAP_PATH):
        self.largeur = largeur
        self.hauteur = hauteur
        self.police_titre = pygame.font.Font(None, 100)
        self.police = pygame.font.Font(None, 48)
        self.police_petite = pygame.font.Font(None, 34)
        # les mêmes morceaux que le jeu (voir Map.morceaux_terrain) : l'aperçu doit montrer le monde
        # qu'on aura vraiment, pas les morceaux faits de tuiles transparentes
        self.morceaux = morceaux_de_terrain(chemin_carte, (CALQUE_BASE, CALQUE_EPAVES))

        cx = largeur // 2
        self.rect_apercu = pygame.Rect(0, 0, TAILLE_APERCU, TAILLE_APERCU)
        self.rect_apercu.midtop = (cx, int(hauteur * 0.22))
        y = self.rect_apercu.bottom
        self.y_lab_graine = y + 20
        self.rect_graine = pygame.Rect(0, 0, LARGEUR_CHAMP, HAUTEUR_CHAMP)
        self.rect_graine.center = (cx, y + 74)
        self.y_lab_delai = self.rect_graine.bottom + 26
        self.rect_moins = pygame.Rect(0, 0, TAILLE_PETIT_BOUTON, TAILLE_PETIT_BOUTON)
        self.rect_moins.center = (cx - 150, self.y_lab_delai + 52)
        self.rect_plus = pygame.Rect(0, 0, TAILLE_PETIT_BOUTON, TAILLE_PETIT_BOUTON)
        self.rect_plus.center = (cx + 150, self.y_lab_delai + 52)
        self.rect_creer = pygame.Rect(0, 0, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        self.rect_creer.center = (cx - 170, self.rect_plus.bottom + 90)
        self.rect_retour = pygame.Rect(0, 0, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        self.rect_retour.center = (cx + 170, self.rect_plus.bottom + 90)

        self.graine = ""
        self.delai = MONDE_DELAI_DEFAUT
        self.focus = 0
        self._graine_apercu = None  # graine dont l'aperçu est dessiné
        self._image_apercu = None

    def ouvrir(self):
        self.graine = str(random.randrange(1, 10 ** 9))  # une graine proposée, modifiable
        self.delai = MONDE_DELAI_DEFAUT
        self.focus = 0

    # ---- génération de l'aperçu ----
    def _generer_apercu(self, graine):
        """Image du terrain généré autour de l'origine, pour cette graine (1 pixel par case)."""
        cote = TAILLE_APERCU
        tampon = bytearray(bytes(COULEUR_FOND_APERCU) * (cote * cote))
        for j in range(-RAYON_APERCU, RAYON_APERCU):
            for i in range(-RAYON_APERCU, RAYON_APERCU):
                grille = morceau(graine, (i, j), self.morceaux)
                if grille is None:
                    continue
                x0 = (i + RAYON_APERCU) * CASES_PAR_MORCEAU
                y0 = (j + RAYON_APERCU) * CASES_PAR_MORCEAU
                for ly, ligne in enumerate(grille):
                    for lx, gid in enumerate(ligne):
                        if gid not in VIDE_GIDS:
                            p = ((y0 + ly) * cote + x0 + lx) * 3
                            tampon[p:p + 3] = bytes(COULEUR_TERRAIN)
        return pygame.image.frombuffer(bytes(tampon), (cote, cote), "RGB")

    # ---- évènements ----
    def _changer_delai(self, pas):
        self.delai = max(0, min(MONDE_DELAI_MAX, self.delai + pas))

    def _creer(self):
        graine = self.graine.strip() or str(random.randrange(1, 10 ** 9))  # graine vide : aléatoire
        return {"graine": graine, "delai": self.delai}

    def evenement(self, event):
        if event.type == pygame.KEYDOWN:
            cible = FOCUS[self.focus]
            if event.key == pygame.K_ESCAPE:
                return "retour"
            if event.key == pygame.K_UP:
                self.focus = (self.focus - 1) % len(FOCUS)
            elif event.key == pygame.K_DOWN:
                self.focus = (self.focus + 1) % len(FOCUS)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "retour" if cible == "retour" else self._creer()
            elif cible == "delai" and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._changer_delai(-1 if event.key == pygame.K_LEFT else 1)
            elif cible == "graine":
                if event.key == pygame.K_BACKSPACE:
                    self.graine = self.graine[:-1]
                elif event.unicode and event.unicode.isprintable() and len(self.graine) < LONGUEUR_GRAINE:
                    self.graine += event.unicode
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.rect_graine.collidepoint(pos):
                self.focus = 0
            elif self.rect_moins.collidepoint(pos) or self.rect_plus.collidepoint(pos):
                self.focus = 1
                self._changer_delai(-1 if self.rect_moins.collidepoint(pos) else 1)
            elif self.rect_creer.collidepoint(pos):
                return self._creer()
            elif self.rect_retour.collidepoint(pos):
                return "retour"
        return None

    # ---- dessin ----
    def _texte(self, screen, texte, centre, police=None, couleur=COULEUR_TEXTE_GRIS):
        image = (police or self.police_petite).render(texte, True, couleur)
        screen.blit(image, image.get_rect(center=centre))

    def dessiner(self, screen, souris):
        cx = self.largeur // 2
        titre = self.police_titre.render("Réglages du monde", True, COULEUR_TITRE)
        screen.blit(titre, titre.get_rect(center=(cx, int(self.hauteur * 0.14))))

        # aperçu : régénéré seulement quand la graine change
        if self.graine.strip() != self._graine_apercu:
            self._graine_apercu = self.graine.strip()
            self._image_apercu = self._generer_apercu(self._graine_apercu) if self._graine_apercu else None
        pygame.draw.rect(screen, COULEUR_FOND_APERCU, self.rect_apercu)
        if self._image_apercu is not None:
            screen.blit(self._image_apercu, self.rect_apercu)
        else:
            self._texte(screen, "Graine vide : un monde aléatoire sera créé", self.rect_apercu.center)
        pygame.draw.rect(screen, COULEUR_BORDURE, self.rect_apercu.inflate(6, 6), 3, border_radius=8)

        # graine
        self._texte(screen, "Graine (même graine = même monde)", (cx, self.y_lab_graine))
        survol = self.focus == 0
        pygame.draw.rect(screen, COULEUR_BOUTON, self.rect_graine, border_radius=14)
        pygame.draw.rect(screen, COULEUR_ACCENT if survol else COULEUR_BORDURE, self.rect_graine, 3, border_radius=14)
        if self.graine:
            curseur = "|" if survol and (pygame.time.get_ticks() // 500) % 2 == 0 else ""
            image = self.police.render(self.graine + curseur, True, COULEUR_TEXTE)
        else:
            image = self.police.render("aléatoire", True, COULEUR_TEXTE_GRIS)
        screen.blit(image, image.get_rect(midleft=(self.rect_graine.x + 28, self.rect_graine.centery)))

        # délai avant les premières attaques
        self._texte(screen, "Temps minimum avant les premières attaques de monstres", (cx, self.y_lab_delai))
        dessiner_bouton(screen, self.police, self.rect_moins, "-", self.rect_moins.collidepoint(souris))
        dessiner_bouton(screen, self.police, self.rect_plus, "+", self.rect_plus.collidepoint(souris))
        valeur = f"{self.delai} min" if self.delai else "normal (aléatoire)"
        self._texte(screen, valeur, (cx, self.rect_moins.centery), self.police, COULEUR_TITRE)
        if self.focus == 1:
            pygame.draw.rect(screen, COULEUR_ACCENT, self.rect_moins.union(self.rect_plus).inflate(12, 12), 2,
                             border_radius=14)

        dessiner_bouton(screen, self.police, self.rect_creer, "Créer le monde",
                        self.rect_creer.collidepoint(souris) or self.focus == 2)
        dessiner_bouton(screen, self.police, self.rect_retour, "Retour",
                        self.rect_retour.collidepoint(souris) or self.focus == 3)
        self._texte(screen, "Entrée : créer   ·   Échap : retour   ·   haut/bas : choisir",
                    (cx, self.rect_creer.bottom + 40))
