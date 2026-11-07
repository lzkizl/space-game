import random
import time

import pygame

import sys
from pathlib import Path

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systeme import ecran
from systeme import preferences
from systeme import sauvegarde
from systeme import son
from reseau.transport import PORT_DEFAUT
from systeme.settings import FPS
from interface.parametres import PageParametres
from interface.reglages_monde import ReglagesMonde
from interface.ui import (COULEUR_ACCENT, COULEUR_BORDURE, COULEUR_BOUTON, COULEUR_TEXTE,
                COULEUR_TEXTE_GRIS, COULEUR_TITRE, dessiner_bouton, dessiner_panneau)

# =============================================
# ==== Réglages
# =============================================
LARGEUR_BOUTON = 420
HAUTEUR_BOUTON = 70
ESPACE_BOUTONS = 20
LARGEUR_LIGNE = 780
HAUTEUR_LIGNE = 80
ESPACE_LIGNES = 14
TAILLE_MAX_NOM = 24
TAILLE_MAX_PSEUDO = 16
TAILLE_MAX_ADRESSE = 67
NB_ETOILES = 300

COULEUR_FOND = (3, 3, 12)

ACTIONS = ["Jouer", "Nouveau monde", "Multijoueur", "Paramètres", "Quitter"]


def _presse_papiers_lire():
    """Le texte du presse-papiers ("" s'il n'y en a pas, ou si le système ne le laisse pas lire).

    Windows y range aussi la version UTF-16 du texte : on demande le type « text/plain », que SDL
    sait convertir, et on coupe au premier zéro (les deux formats terminent la chaîne par là)."""
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        contenu = pygame.scrap.get(pygame.SCRAP_TEXT)
    except (pygame.error, AttributeError):
        return ""
    if not contenu:
        return ""
    if isinstance(contenu, bytes):
        contenu = contenu.split(b"\0", 1)[0].decode("utf-8", errors="replace")
    return contenu


def _presse_papiers_ecrire(texte):
    """Met le texte dans le presse-papiers. Renvoie False si le système ne le permet pas."""
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.put(pygame.SCRAP_TEXT, (texte + "\0").encode("utf-8"))
        return True
    except (pygame.error, AttributeError):
        return False


def nettoyer_saisie(texte, champ):
    """Garde d'un texte collé ce qui a sa place dans un champ : rien d'invisible, et aucun espace
    du tout dans une adresse (on y colle souvent « 192.168.1.12 » avec un retour à la ligne)."""
    caracteres = [c for c in texte if c.isprintable()]
    if champ == "adresse":
        caracteres = [c for c in caracteres if not c.isspace()]
    return "".join(caracteres)


def decouper_adresse(saisie):
    """« 192.168.1.12 » ou « 192.168.1.12:50001 » -> (ip, port)."""
    texte = saisie.strip()
    if texte.count(":") == 1:
        ip, _, port = texte.partition(":")
        if port.isdigit():
            return ip.strip(), int(port)
    return texte, PORT_DEFAUT


class Accueil:
    """Menu principal : choisir un monde sauvegardé (Jouer), en créer un (Nouveau monde),
    héberger ou rejoindre une partie (Multijoueur), ou quitter.

    `run` renvoie None pour quitter, sinon un dictionnaire :
      {"mode": "solo" | "hote" | "client", "nom", "nouveau", "reglages", "pseudo", "ip", "port"}
    `reglages` = {"graine", "delai"} pour un monde nouveau, None sinon. En mode "client",
    "nom" est vide : le monde arrive par le réseau.
    """

    def __init__(self, screen_width, screen_height):
        self.largeur = screen_width
        self.hauteur = screen_height
        self.police_titre = pygame.font.Font(None, 220)
        self.police_page = pygame.font.Font(None, 100)
        self.police = pygame.font.Font(None, 48)
        self.police_petite = pygame.font.Font(None, 34)

        self.etoiles = [
            [random.uniform(0, screen_width), random.uniform(0, screen_height),
             random.choice((1, 1, 2, 2, 3)), random.uniform(4, 25),
             random.choice(((255, 255, 255), (180, 200, 255), (255, 220, 190)))]
            for _ in range(NB_ETOILES)
        ]

        self.page = "accueil"      # accueil / jouer / nouveau / reglages / parametres / multi / rejoindre
        self.page_parametres = PageParametres(screen_width, screen_height)
        self.page_reglages = ReglagesMonde(screen_width, screen_height)
        self.nom_attente = ""      # nom du monde nouveau, le temps de choisir sa graine et son délai
        self.choix = 0
        self.mondes = []           # [(nom, date)] affichés dans la page « jouer »
        self.defilement = 0        # premier monde visible de la liste
        self.a_supprimer = None    # monde pour lequel on attend la confirmation
        self.saisie = ""           # nom tapé dans la page « nouveau »
        self.resultat = None
        self.fini = False

        # ---- multijoueur ----
        self.mode = "solo"         # solo / hote / client
        self.pseudo = preferences.lire("pseudo", "")        # retenu d'une fois sur l'autre
        self.adresse = preferences.lire("derniere_adresse", "")
        self.champ = None          # champ de saisie actif : "pseudo" ou "adresse"
        self.annonce = ""          # message affiché en haut (« L'hôte ne répond pas »...)

        self.rects_accueil = self._colonne_boutons(len(ACTIONS), int(screen_height * 0.48))
        self.rect_retour = pygame.Rect(0, 0, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        self.rect_retour.midbottom = (screen_width // 2, screen_height - 60)
        self.rect_saisie = pygame.Rect(0, 0, 760, 80)
        self.rect_saisie.center = (screen_width // 2, int(screen_height * 0.32))
        self.rect_creer = pygame.Rect(0, 0, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        self.rect_creer.center = (screen_width // 2, int(screen_height * 0.68))
        self.y_liste = int(screen_height * 0.30)
        self.nb_lignes = max(1, (screen_height - 200 - self.y_liste) // (HAUTEUR_LIGNE + ESPACE_LIGNES))

        # pages multijoueur : deux champs de saisie et deux boutons
        self.rect_pseudo = pygame.Rect(0, 0, 560, 70)
        self.rect_pseudo.center = (screen_width // 2, int(screen_height * 0.34))
        self.rect_adresse = pygame.Rect(0, 0, 560, 70)
        self.rect_adresse.center = (screen_width // 2, int(screen_height * 0.48))
        self.rects_multi = self._colonne_boutons(2, int(screen_height * 0.52))
        self.rect_connecter = pygame.Rect(0, 0, LARGEUR_BOUTON, HAUTEUR_BOUTON)
        self.rect_connecter.center = (screen_width // 2, int(screen_height * 0.64))

    def _colonne_boutons(self, nombre, y0):
        return [pygame.Rect((self.largeur - LARGEUR_BOUTON) // 2,
                            y0 + i * (HAUTEUR_BOUTON + ESPACE_BOUTONS),
                            LARGEUR_BOUTON, HAUTEUR_BOUTON)
                for i in range(nombre)]

    # ---- boucle ----
    def run(self, screen, annonce=""):
        """`annonce` : un message à afficher en arrivant (par exemple pourquoi la partie
        en réseau s'est arrêtée)."""
        self.page, self.choix, self.fini, self.resultat = "accueil", 0, False, None
        self.mode, self.champ, self.annonce = "solo", None, annonce
        clock = pygame.time.Clock()
        while not self.fini:
            dt = clock.tick(FPS) / 1000
            for event in pygame.event.get():
                event = ecran.traduire(event)  # clics ramenés dans la surface de jeu (fenêtre réduite)
                son.handle_event(event)
                if event.type == pygame.QUIT:
                    self.resultat, self.fini = None, True
                else:
                    self._evenement(event)
            self._etoiles(dt)
            self._dessiner(screen)
            ecran.presenter()
        return self.resultat

    def _etoiles(self, dt):
        for etoile in self.etoiles:
            etoile[0] -= etoile[3] * dt
            if etoile[0] < 0:
                etoile[0] = self.largeur
                etoile[1] = random.uniform(0, self.hauteur)

    # ---- pages ----
    def _aller(self, page):
        self.page = page
        self.choix = 0
        self.a_supprimer = None
        self.champ = None
        if page == "jouer":
            self.mondes = sauvegarde.lister()
            self.defilement = 0
        elif page == "nouveau":
            self.saisie = ""
        elif page == "reglages":
            self.page_reglages.ouvrir()
        elif page == "parametres":
            self.page_parametres.ouvrir()
        elif page == "multi":
            self.champ = "pseudo" if not self.pseudo else None
        elif page == "rejoindre":
            # le pseudo est retenu d'une fois sur l'autre : en arrivant ici on a presque toujours
            # l'adresse à taper (ou à coller), autant y être déjà
            self.champ = "pseudo" if not self.pseudo else "adresse"

    def _terminer(self, nom, nouveau, reglages, ip="", port=PORT_DEFAUT):
        """Range le choix du joueur et sort du menu (voir la docstring de la classe)."""
        pseudo = self.pseudo.strip() or "Joueur"
        if self.mode != "solo":
            preferences.ecrire("pseudo", pseudo)
        if self.mode == "client":
            preferences.ecrire("derniere_adresse", self.adresse.strip())
        self.resultat = {"mode": self.mode, "nom": nom, "nouveau": nouveau,
                         "reglages": reglages, "pseudo": pseudo, "ip": ip, "port": port}
        self.fini = True

    def _lignes(self):
        """[(rect_ligne, rect_supprimer, nom, date)] des mondes visibles."""
        x = (self.largeur - (LARGEUR_LIGNE + 10 + HAUTEUR_LIGNE)) // 2
        lignes = []
        visibles = self.mondes[self.defilement:self.defilement + self.nb_lignes]
        for i, (nom, date) in enumerate(visibles):
            y = self.y_liste + i * (HAUTEUR_LIGNE + ESPACE_LIGNES)
            lignes.append((pygame.Rect(x, y, LARGEUR_LIGNE, HAUTEUR_LIGNE),
                           pygame.Rect(x + LARGEUR_LIGNE + 10, y, HAUTEUR_LIGNE, HAUTEUR_LIGNE),
                           nom, date))
        return lignes

    # ---- évènements ----
    def _evenement(self, event):
        if self.page == "accueil":
            self._evenement_accueil(event)
        elif self.page == "jouer":
            self._evenement_jouer(event)
        elif self.page == "reglages":
            self._evenement_reglages(event)
        elif self.page == "parametres":
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE) or self.page_parametres.evenement(event):
                self._aller("accueil")
        elif self.page == "multi":
            self._evenement_multi(event)
        elif self.page == "rejoindre":
            self._evenement_rejoindre(event)
        else:
            self._evenement_nouveau(event)

    def _evenement_reglages(self, event):
        reponse = self.page_reglages.evenement(event)
        if reponse == "retour":
            self.page, self.choix = "nouveau", 0  # (le nom tapé est gardé)
        elif reponse is not None:
            self._terminer(self.nom_attente, True, reponse)

    def _evenement_accueil(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_z):
                self.choix = (self.choix - 1) % len(ACTIONS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.choix = (self.choix + 1) % len(ACTIONS)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._valider_accueil(self.choix)
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.rects_accueil):
                if rect.collidepoint(event.pos):
                    self.choix = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.rects_accueil):
                if rect.collidepoint(event.pos):
                    self._valider_accueil(i)

    def _valider_accueil(self, index):
        action = ACTIONS[index]
        self.annonce = ""
        if action == "Jouer":
            self._aller("jouer")
        elif action == "Nouveau monde":
            self._aller("nouveau")
        elif action == "Multijoueur":
            self._aller("multi")
        elif action == "Paramètres":
            self._aller("parametres")
        else:
            self.resultat, self.fini = None, True

    # ---- multijoueur ----
    def _champ_actif(self):
        """(texte du champ actif, sa longueur maximale)."""
        if self.champ == "pseudo":
            return self.pseudo, TAILLE_MAX_PSEUDO
        return self.adresse, TAILLE_MAX_ADRESSE

    def _ecrire_champ(self, texte):
        _, maxi = self._champ_actif()
        if self.champ == "pseudo":
            self.pseudo = texte[:maxi]
        else:
            self.adresse = texte[:maxi]

    def _raccourci(self, event):
        """Ctrl+C / Ctrl+X / Ctrl+V dans le champ actif (pseudo comme adresse).
        True si la touche a été consommée."""
        if not event.mod & pygame.KMOD_CTRL or event.key not in (pygame.K_c, pygame.K_x, pygame.K_v):
            return False
        texte, maxi = self._champ_actif()
        if event.key in (pygame.K_c, pygame.K_x):
            if not texte:
                self.annonce = "Il n'y a rien à copier."
            elif not _presse_papiers_ecrire(texte):
                self.annonce = "Le presse-papiers n'est pas disponible ici."
            elif event.key == pygame.K_x:
                self._ecrire_champ("")
        else:
            colle = nettoyer_saisie(_presse_papiers_lire(), self.champ)
            if not colle:
                self.annonce = "Le presse-papiers est vide (ou ne contient pas de texte)."
            else:
                # on colle à la suite de ce qui est déjà tapé, comme si on l'avait écrit
                self._ecrire_champ((texte + colle)[:maxi])
        return True

    def _saisir(self, event):
        """Tape dans le champ actif. True si la touche a été consommée."""
        if self.champ is None or event.type != pygame.KEYDOWN:
            return False
        if self._raccourci(event):
            return True
        if event.mod & pygame.KMOD_CTRL:
            return True  # (les autres Ctrl+touche n'écrivent rien dans le champ)
        if event.key == pygame.K_TAB:
            self.champ = "adresse" if (self.champ == "pseudo" and self.page == "rejoindre") else "pseudo"
            return True
        if event.key == pygame.K_BACKSPACE:
            if self.champ == "pseudo":
                self.pseudo = self.pseudo[:-1]
            else:
                self.adresse = self.adresse[:-1]
            return True
        if event.unicode and event.unicode.isprintable():
            if self.champ == "pseudo" and len(self.pseudo) < TAILLE_MAX_PSEUDO:
                self.pseudo += event.unicode
            elif self.champ == "adresse" and len(self.adresse) < TAILLE_MAX_ADRESSE:
                self.adresse += event.unicode
            return True
        return False

    def _clic_champs(self, position, champs):
        """Donne le focus au champ cliqué (et l'enlève si on clique à côté)."""
        for nom, rect in champs:
            if rect.collidepoint(position):
                self.champ = nom
                return True
        self.champ = None
        return False

    def _evenement_multi(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._aller("accueil")
            return
        if self._saisir(event):
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.champ = None
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._clic_champs(event.pos, [("pseudo", self.rect_pseudo)]):
                return
            if self.rects_multi[0].collidepoint(event.pos):
                self.mode = "hote"       # on choisit ensuite le monde à ouvrir
                self._aller("jouer")
            elif self.rects_multi[1].collidepoint(event.pos):
                self.mode = "client"
                self._aller("rejoindre")
            elif self.rect_retour.collidepoint(event.pos):
                self._aller("accueil")

    def _evenement_rejoindre(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.mode = "solo"
            self._aller("multi")
            return
        if (self.champ is None and event.type == pygame.KEYDOWN
                and event.mod & pygame.KMOD_CTRL and event.key in (pygame.K_c, pygame.K_x, pygame.K_v)):
            self.champ = "adresse"  # coller sans avoir cliqué dans le champ : c'est l'adresse qu'on veut
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._se_connecter()
            return
        if self._saisir(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._clic_champs(event.pos, [("pseudo", self.rect_pseudo), ("adresse", self.rect_adresse)]):
                return
            if self.rect_connecter.collidepoint(event.pos):
                self._se_connecter()
            elif self.rect_retour.collidepoint(event.pos):
                self.mode = "solo"
                self._aller("multi")

    def _se_connecter(self):
        ip, port = decouper_adresse(self.adresse)
        if not ip:
            self.annonce = "Entre l'adresse de la machine qui héberge la partie."
            return
        self.mode = "client"
        self._terminer("", False, None, ip=ip, port=port)

    def _evenement_jouer(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._aller("multi" if self.mode == "hote" else "accueil")
        elif event.type == pygame.MOUSEWHEEL:
            maxi = max(0, len(self.mondes) - self.nb_lignes)
            self.defilement = max(0, min(maxi, self.defilement - event.y))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect_retour.collidepoint(event.pos):
                self._aller("multi" if self.mode == "hote" else "accueil")
                return
            for rect, rect_supprimer, nom, _ in self._lignes():
                if rect.collidepoint(event.pos):
                    self._terminer(nom, False, None)
                    return
                if rect_supprimer.collidepoint(event.pos):
                    if self.a_supprimer == nom:  # deuxième clic : on confirme
                        sauvegarde.supprimer(nom)
                        self.mondes = sauvegarde.lister()
                        self.defilement = max(0, min(self.defilement,
                                                     len(self.mondes) - self.nb_lignes))
                        self.a_supprimer = None
                    else:
                        self.a_supprimer = nom
                    return
            self.a_supprimer = None

    def _evenement_nouveau(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._aller("accueil")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._creer()
            elif event.key == pygame.K_BACKSPACE:
                self.saisie = self.saisie[:-1]
            elif event.unicode and event.unicode.isprintable() and len(self.saisie) < TAILLE_MAX_NOM:
                self.saisie += event.unicode
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect_creer.collidepoint(event.pos):
                self._creer()
            elif self.rect_retour.collidepoint(event.pos):
                self._aller("accueil")

    def _creer(self):
        self.nom_attente = sauvegarde.nom_libre(self.saisie)
        self._aller("reglages")  # le monde est créé à la fin de la page des réglages

    # ---- dessin ----
    def _dessiner(self, screen):
        screen.fill(COULEUR_FOND)
        for x, y, rayon, _, couleur in self.etoiles:
            screen.fill(couleur, (int(x), int(y), rayon, rayon))

        centre_x = self.largeur // 2
        souris = ecran.souris()
        if self.page == "accueil":
            titre = self.police_titre.render("SPACE", True, COULEUR_TITRE)
            ombre = self.police_titre.render("SPACE", True, COULEUR_ACCENT)
            position = titre.get_rect(center=(centre_x, int(self.hauteur * 0.25)))
            screen.blit(ombre, position.move(5, 5))
            screen.blit(titre, position)
            for i, (rect, texte) in enumerate(zip(self.rects_accueil, ACTIONS)):
                dessiner_bouton(screen, self.police, rect, texte,
                                i == self.choix or rect.collidepoint(souris))
        elif self.page == "jouer":
            self._dessiner_jouer(screen, souris)
        elif self.page == "parametres":
            self.page_parametres.dessiner(screen, souris)
        elif self.page == "reglages":
            self.page_reglages.dessiner(screen, souris)
        elif self.page == "multi":
            self._dessiner_multi(screen, souris)
        elif self.page == "rejoindre":
            self._dessiner_rejoindre(screen, souris)
        else:
            self._dessiner_nouveau(screen, souris)

        if self.annonce and self.page in ("accueil", "multi", "rejoindre"):
            image = self.police_petite.render(self.annonce, True, COULEUR_ACCENT)
            screen.blit(image, image.get_rect(midtop=(self.largeur // 2, 40)))

    def _titre_page(self, screen, texte):
        titre = self.police_page.render(texte, True, COULEUR_TITRE)
        screen.blit(titre, titre.get_rect(center=(self.largeur // 2, int(self.hauteur * 0.16))))

    def _dessiner_champ(self, screen, rect, nom, texte, invite):
        """Un champ de saisie : son intitulé à gauche, le texte tapé dedans."""
        actif = self.champ == nom
        pygame.draw.rect(screen, COULEUR_BOUTON, rect, border_radius=14)
        pygame.draw.rect(screen, COULEUR_ACCENT if actif else COULEUR_BORDURE, rect, 3, border_radius=14)
        if texte:
            curseur = "|" if actif and (pygame.time.get_ticks() // 500) % 2 == 0 else ""
            image = self.police.render(texte + curseur, True, COULEUR_TEXTE)
        else:
            image = self.police.render(invite, True, COULEUR_TEXTE_GRIS)
        screen.blit(image, image.get_rect(midleft=(rect.x + 24, rect.centery)))

    def _dessiner_multi(self, screen, souris):
        self._titre_page(screen, "Multijoueur")
        self._dessiner_champ(screen, self.rect_pseudo, "pseudo", self.pseudo, "Ton pseudo")
        for rect, texte in zip(self.rects_multi, ("Héberger une partie", "Rejoindre une partie")):
            dessiner_bouton(screen, self.police, rect, texte, rect.collidepoint(souris))
        aide = ("Héberger : tu ouvres un de tes mondes, les autres te rejoignent par ton adresse IP. "
                "Tu joues en même temps.")
        image = self.police_petite.render(aide, True, COULEUR_TEXTE_GRIS)
        screen.blit(image, image.get_rect(midtop=(self.largeur // 2, self.rects_multi[-1].bottom + 30)))
        dessiner_bouton(screen, self.police, self.rect_retour, "Retour",
                        self.rect_retour.collidepoint(souris))

    def _dessiner_rejoindre(self, screen, souris):
        self._titre_page(screen, "Rejoindre une partie")
        self._dessiner_champ(screen, self.rect_pseudo, "pseudo", self.pseudo, "Ton pseudo")
        self._dessiner_champ(screen, self.rect_adresse, "adresse", self.adresse,
                             f"Adresse de l'hôte (ex : 192.168.1.12, ou 192.168.1.12:{PORT_DEFAUT})")
        dessiner_bouton(screen, self.police, self.rect_connecter, "Se connecter",
                        self.rect_connecter.collidepoint(souris))
        raccourcis = self.police_petite.render("Ctrl+V : coller   ·   Ctrl+C : copier   ·   Tab : changer de champ",
                                               True, COULEUR_TEXTE_GRIS)
        screen.blit(raccourcis, raccourcis.get_rect(midtop=(self.largeur // 2, self.rect_adresse.bottom + 12)))
        aide = "L'hôte voit son adresse affichée en haut de son écran quand il héberge."
        image = self.police_petite.render(aide, True, COULEUR_TEXTE_GRIS)
        screen.blit(image, image.get_rect(midtop=(self.largeur // 2, self.rect_connecter.bottom + 26)))
        dessiner_bouton(screen, self.police, self.rect_retour, "Retour",
                        self.rect_retour.collidepoint(souris))

    def _dessiner_jouer(self, screen, souris):
        heberge = self.mode == "hote"
        self._titre_page(screen, "Quel monde ouvrir ?" if heberge else "Choisir un monde")
        if not self.mondes:
            texte = self.police.render("Aucun monde sauvegardé : crée un nouveau monde !",
                                       True, COULEUR_TEXTE_GRIS)
            screen.blit(texte, texte.get_rect(center=(self.largeur // 2, self.y_liste + 60)))
        elif heberge:
            texte = self.police_petite.render(
                "Ce monde sera ouvert aux autres joueurs, et c'est lui qui sera sauvegardé.",
                True, COULEUR_TEXTE_GRIS)
            screen.blit(texte, texte.get_rect(midtop=(self.largeur // 2, self.y_liste - 44)))

        for rect, rect_supprimer, nom, date in self._lignes():
            survol = rect.collidepoint(souris)
            dessiner_bouton(screen, self.police, rect, "", survol)
            image = self.police.render(nom, True, COULEUR_TEXTE)
            screen.blit(image, image.get_rect(midleft=(rect.x + 28, rect.centery)))
            quand = time.strftime("%d/%m/%Y %H:%M", time.localtime(date))
            image = self.police_petite.render(quand, True, COULEUR_TEXTE_GRIS)
            screen.blit(image, image.get_rect(midright=(rect.right - 28, rect.centery)))

            confirmer = self.a_supprimer == nom
            dessiner_bouton(screen, self.police, rect_supprimer, "?" if confirmer else "X",
                            rect_supprimer.collidepoint(souris), danger=confirmer)

        if len(self.mondes) > self.nb_lignes:
            texte = self.police_petite.render(
                f"{self.defilement + 1}-{min(len(self.mondes), self.defilement + self.nb_lignes)}"
                f" / {len(self.mondes)}  (molette pour défiler)", True, COULEUR_TEXTE_GRIS)
            screen.blit(texte, texte.get_rect(midbottom=(self.largeur // 2, self.rect_retour.y - 12)))
        elif self.a_supprimer:
            texte = self.police_petite.render(
                f"Clique encore sur « ? » pour supprimer « {self.a_supprimer} » définitivement",
                True, COULEUR_TEXTE_GRIS)
            screen.blit(texte, texte.get_rect(midbottom=(self.largeur // 2, self.rect_retour.y - 12)))

        dessiner_bouton(screen, self.police, self.rect_retour, "Retour",
                        self.rect_retour.collidepoint(souris))

    def _dessiner_nouveau(self, screen, souris):
        self._titre_page(screen, "Nouveau monde")
        pygame.draw.rect(screen, COULEUR_BOUTON, self.rect_saisie, border_radius=14)
        pygame.draw.rect(screen, COULEUR_ACCENT, self.rect_saisie, 3, border_radius=14)
        if self.saisie:
            curseur = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
            image = self.police.render(self.saisie + curseur, True, COULEUR_TEXTE)
        else:
            image = self.police.render("Nom du monde", True, COULEUR_TEXTE_GRIS)
        screen.blit(image, image.get_rect(midleft=(self.rect_saisie.x + 28, self.rect_saisie.centery)))

        dessiner_bouton(screen, self.police, self.rect_creer, "Suivant",
                        self.rect_creer.collidepoint(souris))
        dessiner_bouton(screen, self.police, self.rect_retour, "Retour",
                        self.rect_retour.collidepoint(souris))


if __name__ == "__main__":
    from lanceur import lancer

    lancer()
