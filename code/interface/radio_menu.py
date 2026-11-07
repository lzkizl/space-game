import math
import random
import re
import sys
import threading
from pathlib import Path

import pygame

# permet de lancer ce fichier directement : on ajoute le dossier code/ au chemin des imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interface.ui import (COULEUR_ACCENT, COULEUR_BORDURE, COULEUR_BOUTON, COULEUR_TEXTE, COULEUR_TEXTE_GRIS,
                COULEUR_TITRE, dessiner_bouton, dessiner_panneau)
from systeme import ecran

# =============================================
# ==== Radio de l'antenne : un clic sur une antenne posée ouvre ce menu.
# ==== Un vrai émetteur-récepteur : on règle la fréquence (200 à 800 MHz), on écrit un message,
# ==== il part en octets (8 bits par caractère, UTF-8) et ces bits modulent l'amplitude d'une
# ==== porteuse à la fréquence réglée (modulation ASK). Rien n'est traduit : on voit le signal,
# ==== sa fréquence, sa période et sa longueur d'onde (λ = c / f), et le spectre autour de nous.
# ==== Un vaisseau accordé sur la bonne fréquence répond avec l'IA de code/ia/, de la même façon ;
# ==== plus on est mal accordé, plus le bruit abîme les bits reçus.
# =============================================
F_MIN, F_MAX = 200.0, 800.0        # bande de la radio, en MHz
F_DEPART = 433.5
VITESSE_LUMIERE = 299_792_458      # m/s

# Ce qu'on trouve sur la bande : (fréquence en MHz, nom, type). Il faut s'accorder dessus pour l'entendre.
#   vaisseau : écoute et répond avec l'IA
#   balise   : émet en boucle un motif de bits (voir MOTIFS), ne répond pas
#   naturel  : source du ciel (pulsar, quasar...), émet des impulsions, ne répond pas
STATIONS = [
    (211.0, "SOS", "balise"),
    (243.0, "Aurore", "vaisseau"),
    (275.0, "Pulsar", "naturel"),
    (318.2, "Nomade", "vaisseau"),
    (355.5, "Épave", "balise"),
    (433.5, "Relais", "vaisseau"),
    (527.8, "Horizon", "vaisseau"),
    (580.0, "Quasar", "naturel"),
    (612.5, "Orion", "vaisseau"),
    (719.4, "Sentinelle", "vaisseau"),
    (775.0, "Mine", "balise"),
]
TYPES = {nom: type_ for _, nom, type_ in STATIONS}
LIBELLES = {"balise": "Balise", "naturel": "Source naturelle"}   # (les vaisseaux : « Signal »)
# motif répété en boucle par chaque balise (le SOS en morse : ... --- ...)
MOTIFS = {"SOS": "10101000111011101110001010100000", "Épave": "11001100110011000000", "Mine": "1111000011110000"}
# Zones de bruit : (fréquence, nom, largeur en MHz, force). Le bruit y noie les signaux.
ZONES_BRUIT = [(480.0, "Brouilleur", 6.0, 0.45), (680.0, "Orage solaire", 18.0, 0.35)]
PORTEE_NETTE = 0.5                 # écart (MHz) jusqu'auquel la réception est parfaite
PORTEE_MAX = 3.0                   # au-delà, on n'entend plus rien ; entre les deux, il y a des parasites

VITESSE_EMISSION = 60              # bits par seconde (animation de l'envoi)
VITESSE_RECEPTION = 240            # bits par seconde (animation de la réponse)
MAX_BITS = 64                      # taille maximale d'un message, en bits
MAX_CARACTERES = 100               # avec une clé USB : taille maximale d'un message, en lettres
MAX_REPONSE = 160                  # taille maximale d'une réponse
FENETRE_BITS = 12                  # nombre de bits visibles sur l'oscilloscope
NIVEAU_ZERO = 0.25                 # amplitude de la porteuse pour un bit 0 (1 pour un bit 1)
FENETRE_NS = 10.0                  # durée montrée par le zoom sur la porteuse
PORTEE_ESPACE = 3.0                # longueur d'air montrée par le dessin de l'onde, en mètres

COULEUR_EMISSION = (130, 170, 255)
COULEUR_RECEPTION = (140, 230, 160)
COULEUR_PARASITES = (255, 190, 90)
COULEUR_SPECTRE = (110, 200, 230)
COULEUR_BROUILLAGE = (255, 110, 110)
COULEURS_TYPE = {"vaisseau": (170, 170, 190), "balise": (255, 190, 90), "naturel": (190, 150, 255)}  # noms du spectre
COULEUR_FOND_ECRAN = (10, 10, 18)

DOSSIER_IA = Path(__file__).resolve().parent.parent / "ia"
PAS_FREQUENCE = [(-10, "-10"), (-1, "-1"), (-0.1, "-0,1"), (0.1, "+0,1"), (1, "+1"), (10, "+10")]
MOT = re.compile(r"[a-zàâäéèêëîïôöùûüÿçœæ]+(?:[-'][a-zàâäéèêëîïôöùûüÿçœæ]+)*")


def station_proche(frequence):
    """(nom, écart en MHz) du vaisseau le plus proche de la fréquence, ou None s'il est trop loin."""
    ecart, nom = min((abs(f - frequence), nom) for f, nom, _ in STATIONS)
    return (nom, ecart) if ecart <= PORTEE_MAX else None


def zone_bruit(frequence):
    """(nom, intensité de 0 à 1) de la zone de bruit la plus forte à cette fréquence, ou None."""
    meilleure = None
    for centre, nom, largeur, force in ZONES_BRUIT:
        intensite = max(0.0, 1 - abs(frequence - centre) / largeur)
        if intensite > 0 and (meilleure is None or intensite * force > meilleure[1] * meilleure[2]):
            meilleure = (nom, intensite, force)
    return (meilleure[0], meilleure[1]) if meilleure else None


def bruit_ajoute(frequence):
    """Bruit supplémentaire (amplitude) dû aux zones de bruit à cette fréquence."""
    return max((max(0.0, 1 - abs(frequence - centre) / largeur) * force
                for centre, _, largeur, force in ZONES_BRUIT), default=0.0)


def force_signal(ecart):
    """Amplitude (0 à 1) d'une station selon l'écart d'accord."""
    if ecart <= PORTEE_NETTE:
        return 1.0
    if ecart >= PORTEE_MAX:
        return 0.0
    return 1.0 - (ecart - PORTEE_NETTE) / (PORTEE_MAX - PORTEE_NETTE) * 0.7


def bruit_reception(ecart):
    """Amplitude du bruit sur le signal reçu : faible si bien accordé, forte sinon."""
    return 0.05 + min(0.45, max(0.0, ecart - PORTEE_NETTE) * 0.18)


def vers_bits(texte):
    """Texte -> bits : 8 bits par octet (UTF-8)."""
    return "".join(format(octet, "08b") for octet in texte.encode("utf-8"))


def depuis_bits(bits):
    """Bits -> texte. Un octet abîmé par le bruit donne un autre caractère, ou '?'."""
    donnees = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits) - 7, 8))
    texte = donnees.decode("utf-8", errors="replace")
    return "".join(c if c.isprintable() and c != "�" else "?" for c in texte)


def par_octets(bits):
    """Bits groupés par 8 pour la lecture : '0100100001101001' -> '01001000 01101001'."""
    return " ".join(bits[i:i + 8] for i in range(0, len(bits), 8))


def parasiter(bits, ecart):
    """Des bits sont inversés quand la fréquence n'est pas bien réglée (plus on est loin, plus il y en a)."""
    if ecart <= PORTEE_NETTE:
        return bits
    proba = min(0.04, (ecart - PORTEE_NETTE) * 0.016)
    return "".join(("1" if b == "0" else "0") if random.random() < proba else b for b in bits)


def nombre(valeur, decimales=1):
    return f"{valeur:.{decimales}f}".replace(".", ",")


def longueur_onde(frequence):
    """λ = c / f, écrite en cm (ou en m au-delà d'un mètre)."""
    metres = VITESSE_LUMIERE / (frequence * 1e6)
    return f"{nombre(metres, 2)} m" if metres >= 1 else f"{nombre(metres * 100, 1)} cm"


# ---- l'IA qui répond (chargée en arrière-plan : torch met quelques secondes à démarrer) ----
class Cerveau:
    """Fait répondre l'IA de code/ia/ sans bloquer le jeu. `reponse` vaut None tant qu'elle réfléchit."""

    def __init__(self):
        self.reponse = None
        self._modele = None
        self._langue = None            # langue du modèle chargé (voir systeme/langue.py)

    def demander(self, message, station=None):
        self.reponse = None
        threading.Thread(target=self._penser, args=(message, station), daemon=True).start()

    def _penser(self, message, station=None):
        try:
            if str(DOSSIER_IA) not in sys.path:
                sys.path.append(str(DOSSIER_IA))
            import ia
            from systeme import langue
            choisie = langue.actuelle()           # la langue des Paramètres (peut changer en cours de partie)
            if choisie != self._langue:
                ia.definir_langue(choisie)
                self._modele, self._langue = None, choisie
            if self._modele is None or self._modele[0] is None:
                # sans modèle entraîné, elle répond quand même aux questions connues (mémoire)
                self._modele = ia.charger() if Path(ia.MODEL_PATH).exists() else (None, None)
            modele, vocab = self._modele
            self.reponse = ia.repondre(message, modele, vocab, station=station)
        except Exception as erreur:  # pas de torch, modèle illisible... le jeu ne doit pas planter
            self.reponse = f"Message reçu. (IA indisponible : {type(erreur).__name__})"


class Radio:
    """Menu de la radio. États : libre -> emission -> attente -> reception -> libre."""

    def __init__(self, screen_width, screen_height):
        self.ouvert = False
        self.decodeur = False          # True si un boîtier avec une clé USB est collé à l'antenne ouverte
        self.frequence = F_DEPART
        self.texte = ""
        self.journal = []              # [(qui, texte, couleur)]
        self.etat = "libre"
        self.bits = ""                 # bits en cours d'émission ou de réception
        self.temps = 0.0               # temps passé dans l'état courant
        self.station = None            # (nom, écart) du vaisseau qui écoute à l'envoi
        self.glisse = False            # True pendant qu'on fait glisser le curseur de fréquence
        self.cerveau = Cerveau()
        self.reponse_recue = ""        # texte lu dans les bits reçus (après le bruit)

        self.police_titre = pygame.font.Font(None, 80)
        self.police_grande = pygame.font.Font(None, 110)
        self.police = pygame.font.Font(None, 40)
        self.police_petite = pygame.font.Font(None, 30)
        self.police_bits = pygame.font.Font(None, 27)

        hauteur = min(820, screen_height - 40)
        self.panneau = pygame.Rect(0, 0, 1500, hauteur)
        self.panneau.center = (screen_width // 2, screen_height // 2)
        x, y = self.panneau.x + 40, self.panneau.y
        self.boutons_frequence = []
        for i, (pas, nom) in enumerate(PAS_FREQUENCE):
            self.boutons_frequence.append((pygame.Rect(x + i * 132, y + 190, 120, 50), pas, nom))
        self.barre = pygame.Rect(x, y + 270, 780, 26)
        self.champ = pygame.Rect(x, y + 405, 780, 56)
        self.zone_infos = pygame.Rect(x, y + 475, 780, 100)
        self.oscillo = pygame.Rect(x, y + 585, 780, 150)
        self.bouton_envoyer = pygame.Rect(x, y + 750, 340, 66)
        self.zone_spectre = pygame.Rect(self.panneau.x + 880, y + 110, 580, 200)
        self.zone_journal = pygame.Rect(self.panneau.x + 880, y + 370, 580, hauteur - 410)

    # ---- évènements ----
    def ouvrir(self, inventaire, decodeur=False):
        """Ouvre la radio (appelé quand on clique sur une antenne posée). `decodeur` vaut True quand une
        boîtier avec une clé USB est posé contre l'antenne : elle traduit alors les bits en lettres."""
        self.ouvert = True
        self.decodeur = decodeur
        inventaire.ouvert = False

    def regler(self, frequence):
        self.frequence = round(min(F_MAX, max(F_MIN, frequence)), 1)

    def _regler_depuis_souris(self, x):
        proportion = (x - self.barre.x) / self.barre.width
        self.regler(F_MIN + proportion * (F_MAX - F_MIN))

    def envoi_possible(self):
        return self.etat == "libre" and bool(self.texte)

    def envoyer(self):
        if not self.envoi_possible():
            return
        # les bits tapés partent tels quels ; avec une clé USB, ce sont des lettres qu'elle traduit en bits
        self.bits = vers_bits(self.texte) if self.decodeur else self.texte
        self.texte = ""
        self.temps = 0.0
        self.etat = "emission"
        self.station = station_proche(self.frequence)
        self.journal.append((f"Moi ({nombre(self.frequence)} MHz)", par_octets(self.bits), COULEUR_EMISSION))
        if self.station and TYPES[self.station[0]] == "vaisseau":
            # le vaisseau lit les octets reçus (8 bits = 1 caractère) et y répond avec l'IA
            message = depuis_bits(self.bits)
            self.cerveau.demander(" ".join(MOT.findall(message.lower())) or message or "?", self.station[0])

    def handle_event(self, event):
        """Quand la radio est ouverte, elle absorbe les évènements. Renvoie True s'il est consommé."""
        if not self.ouvert:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.ouvert = False  # (Echap ne doit pas ouvrir la pause)
                return True
            if event.key == pygame.K_TAB:
                self.ouvert = False  # Tab ouvre l'inventaire à la place
                return False
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.envoyer()
            elif event.key == pygame.K_BACKSPACE:
                self.texte = self.texte[:-1]
            elif self.decodeur:
                # clé USB : on tape des lettres, elle les traduit en bits à l'envoi
                if event.unicode and event.unicode.isprintable() and len(self.texte) < MAX_CARACTERES:
                    self.texte += event.unicode
            elif event.unicode in ("0", "1") and len(self.texte) < MAX_BITS:
                self.texte += event.unicode
            return True

        if event.type == pygame.MOUSEWHEEL:
            self.regler(self.frequence + event.y)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panneau.collidepoint(event.pos):
                self.ouvert = False
                return True
            for rect, pas, _ in self.boutons_frequence:
                if rect.collidepoint(event.pos):
                    self.regler(self.frequence + pas)
            if self.barre.inflate(0, 30).collidepoint(event.pos):
                self.glisse = True
                self._regler_depuis_souris(event.pos[0])
            if self.bouton_envoyer.collidepoint(event.pos):
                self.envoyer()
            return True

        if event.type == pygame.MOUSEMOTION and self.glisse:
            self._regler_depuis_souris(event.pos[0])
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.glisse:
            self.glisse = False
            return True
        return False

    # ---- mise à jour (continue même si le menu est fermé : la réponse arrive quand même) ----
    def update(self, dt):
        if self.etat == "libre":
            return
        self.temps += dt
        if self.etat == "emission":
            if self.temps * VITESSE_EMISSION >= len(self.bits):
                if self.station is None:
                    self.journal.append(("Radio", "Aucune réponse... seulement du bruit.", COULEUR_TEXTE_GRIS))
                    self.etat = "libre"
                elif TYPES[self.station[0]] != "vaisseau":
                    self.journal.append((self.station[0], "Ne répond pas : c'est un signal automatique.",
                                         COULEUR_TEXTE_GRIS))
                    self.etat = "libre"
                else:
                    self.etat, self.temps = "attente", 0.0
        elif self.etat == "attente":
            if self.cerveau.reponse is not None:
                nom, ecart = self.station
                reponse = self.cerveau.reponse.strip()[:MAX_REPONSE]
                if not reponse:
                    self.journal.append((nom, "...", COULEUR_TEXTE_GRIS))
                    self.etat = "libre"
                    return
                # la réponse part en bits, le bruit en abîme, et ce qu'on lit vient des bits reçus
                self.bits = parasiter(vers_bits(reponse), ecart)
                self.reponse_recue = par_octets(self.bits)
                self.etat, self.temps = "reception", 0.0
        elif self.etat == "reception":
            if self.temps * VITESSE_RECEPTION >= len(self.bits):
                nom, ecart = self.station
                couleur = COULEUR_RECEPTION if ecart <= PORTEE_NETTE else COULEUR_PARASITES
                self.journal.append((nom, self.reponse_recue, couleur))
                self.etat = "libre"

    # ---- dessin ----
    def _position_bits(self):
        """Position (en bits) du signal sous l'oscilloscope : avance avec l'émission ou la réception ;
        sinon la porteuse défile quand même, pour qu'on voie l'onde « vivre »."""
        if self.etat == "emission":
            return self.temps * VITESSE_EMISSION
        if self.etat == "reception":
            return self.temps * VITESSE_RECEPTION
        return pygame.time.get_ticks() / 1000 * VITESSE_EMISSION

    def _regime(self):
        """(amplitude de la porteuse au repos, bruit) quand rien n'est transmis."""
        station = station_proche(self.frequence)
        if station is None:
            return 0.0, 0.18
        return 0.7 * force_signal(station[1]), 0.05 + 0.2 * (1 - force_signal(station[1]))

    def _niveau_bruit(self):
        if self.etat == "reception":
            base = bruit_reception(self.station[1])
        elif self.etat == "emission":
            base = 0.03
        else:
            base = self._regime()[1]
        return base + bruit_ajoute(self.frequence)

    def _amplitude_repos(self, position):
        """Porteuse de la station sur laquelle on est accordé quand rien n'est transmis :
        constante pour un vaisseau, motif de bits pour une balise, impulsions pour une source naturelle."""
        station = station_proche(self.frequence)
        if station is None:
            return 0.0
        nom, ecart = station
        niveau = 0.7 * force_signal(ecart)
        genre = TYPES[nom]
        if genre == "balise":
            motif = MOTIFS[nom]
            return niveau * (1.0 if motif[int(position) % len(motif)] == "1" else NIVEAU_ZERO)
        if genre == "naturel":
            return niveau * (1.0 if position % VITESSE_EMISSION < 8 else 0.08)   # une impulsion par seconde
        return niveau

    def _amplitude(self, position):
        """Amplitude de la porteuse à cette position en bits (ASK : 1 -> haute, 0 -> basse)."""
        if self.etat in ("emission", "reception"):
            i = math.floor(position)
            if 0 <= i < len(self.bits):
                return 1.0 if self.bits[i] == "1" else NIVEAU_ZERO
            return 0.0
        return self._amplitude_repos(position)

    def draw(self, screen, inventaire=None):
        if not self.ouvert:
            return
        dessiner_panneau(screen, self.panneau)
        x, y = self.panneau.x + 40, self.panneau.y
        titre = self.police_titre.render("Radio", True, COULEUR_TITRE)
        screen.blit(titre, (x, y + 25))
        aide = self.police_petite.render("Echap pour fermer", True, COULEUR_TEXTE_GRIS)
        screen.blit(aide, aide.get_rect(topright=(self.panneau.right - 40, y + 40)))
        if self.decodeur:
            badge = self.police.render("Clé USB : bits traduits en lettres", True, COULEUR_RECEPTION)
            screen.blit(badge, (x + 230, y + 38))

        # fréquence
        freq = self.police_grande.render(f"{nombre(self.frequence)} MHz", True, COULEUR_TITRE)
        screen.blit(freq, freq.get_rect(midtop=(x + 390, y + 80)))
        souris = ecran.souris()
        for rect, _, nom in self.boutons_frequence:
            dessiner_bouton(screen, self.police, rect, nom, rect.collidepoint(souris))

        # curseur de fréquence (clic ou glisser, molette pour ajuster)
        pygame.draw.rect(screen, COULEUR_BOUTON, self.barre, border_radius=8)
        pygame.draw.rect(screen, COULEUR_BORDURE, self.barre, 2, border_radius=8)
        for f in (200, 400, 600, 800):
            tx = self.barre.x + (f - F_MIN) / (F_MAX - F_MIN) * self.barre.width
            texte = self.police_petite.render(str(f), True, COULEUR_TEXTE_GRIS)
            screen.blit(texte, texte.get_rect(midtop=(tx, self.barre.bottom + 4)))
        curseur_x = self.barre.x + (self.frequence - F_MIN) / (F_MAX - F_MIN) * self.barre.width
        pygame.draw.rect(screen, COULEUR_ACCENT, pygame.Rect(curseur_x - 7, self.barre.y - 6, 14, self.barre.height + 12),
                         border_radius=6)

        # ce qu'on entend sur cette fréquence
        station = station_proche(self.frequence)
        if station is None:
            etat, couleur = "Aucun signal... bruit radio", COULEUR_TEXTE_GRIS
        else:
            libelle = LIBELLES.get(TYPES[station[0]], "Signal")
            if station[1] <= PORTEE_NETTE:
                etat, couleur = f"{libelle} fort : {station[0]}", COULEUR_RECEPTION
            else:
                etat, couleur = f"{libelle} faible : {station[0]} (parasites)", COULEUR_PARASITES
        zone = zone_bruit(self.frequence)
        if zone and zone[1] > 0.3:
            etat, couleur = f"Brouillage : {zone[0]}" + (f"  ·  {etat}" if station else ""), COULEUR_BROUILLAGE
        screen.blit(self.police.render(etat, True, couleur), (x, y + 340))

        # message
        consigne = ("Message : tape des lettres, traduites en bits (Entrée pour envoyer, 100 max)" if self.decodeur
                    else "Bits à envoyer : tape des 0 et des 1 (Entrée pour envoyer)")
        screen.blit(self.police_petite.render(consigne, True, COULEUR_TEXTE_GRIS), (x, y + 378))
        pygame.draw.rect(screen, COULEUR_BOUTON, self.champ, border_radius=12)
        pygame.draw.rect(screen, COULEUR_ACCENT, self.champ, 2, border_radius=12)
        curseur = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        affiche = (self.texte if self.decodeur else par_octets(self.texte)) + curseur
        while len(affiche) > 1 and self.police.size(affiche)[0] > self.champ.width - 32:
            affiche = affiche[1:]      # le texte défile : on garde la fin
        saisie = self.police.render(affiche, True, COULEUR_TEXTE)
        screen.blit(saisie, saisie.get_rect(midleft=(self.champ.x + 16, self.champ.centery)))

        self._dessiner_infos(screen)
        self._dessiner_oscillo(screen)
        self._dessiner_spectre(screen)

        possible = self.envoi_possible()
        dessiner_bouton(screen, self.police, self.bouton_envoyer, "Envoyer le signal",
                        possible and self.bouton_envoyer.collidepoint(souris))
        if not possible:
            voile = pygame.Surface(self.bouton_envoyer.size, pygame.SRCALPHA)
            pygame.draw.rect(voile, (0, 0, 0, 140), voile.get_rect(), border_radius=14)
            screen.blit(voile, self.bouton_envoyer)

        self._dessiner_journal(screen)

    def _cote(self, screen, x1, x2, y, symbole, couleur):
        """Une cote horizontale entre x1 et x2, avec son symbole (λ, T) au milieu."""
        pygame.draw.line(screen, couleur, (x1, y), (x2, y), 2)
        pygame.draw.line(screen, couleur, (x1, y - 5), (x1, y + 5), 2)
        pygame.draw.line(screen, couleur, (x2, y - 5), (x2, y + 5), 2)
        image = self.police_bits.render(symbole, True, couleur)
        place = image.get_rect(center=((x1 + x2) // 2, y))
        pygame.draw.rect(screen, COULEUR_FOND_ECRAN, place.inflate(6, 0))
        screen.blit(image, place)

    def _dessiner_infos(self, screen):
        """Les grandeurs de l'onde : fréquence, longueur d'onde, période, et l'onde dans l'air."""
        zone = self.zone_infos
        f = self.frequence
        pygame.draw.rect(screen, COULEUR_FOND_ECRAN, zone, border_radius=10)
        pygame.draw.rect(screen, COULEUR_BORDURE, zone, 2, border_radius=10)
        lignes = [
            ("Onde radio : vitesse c = 299 792 458 m/s", COULEUR_TEXTE_GRIS),
            (f"Fréquence    f = {nombre(f)} MHz", COULEUR_TEXTE),
            (f"Longueur d'onde    λ = c / f = {longueur_onde(f)}", COULEUR_ACCENT),
            (f"Période    T = 1 / f = {nombre(1000 / f, 2)} ns", COULEUR_TEXTE),
        ]
        for i, (texte, couleur) in enumerate(lignes):
            screen.blit(self.police_bits.render(texte, True, couleur), (zone.x + 14, zone.y + 8 + i * 23))

        # l'onde dans l'air sur 3 m (ralentie) : une longueur d'onde = la distance entre deux crêtes
        boite = pygame.Rect(zone.x + 440, zone.y + 6, 330, zone.height - 12)
        screen.blit(self.police_bits.render(f"dans l'air, sur {int(PORTEE_ESPACE)} m (ralenti)", True, COULEUR_TEXTE_GRIS),
                    (boite.x, boite.y))
        lam = VITESSE_LUMIERE / (f * 1e6)
        decalage = pygame.time.get_ticks() / 1500 * 2 * math.pi
        milieu, demi = boite.y + 44, 16
        points = [(boite.x + px, milieu - demi * math.sin(2 * math.pi * (PORTEE_ESPACE * px / boite.width) / lam - decalage))
                  for px in range(0, boite.width + 1, 2)]
        pygame.draw.lines(screen, COULEUR_ACCENT, False, points, 2)
        crete = lam * ((0.25 + decalage / (2 * math.pi)) % 1.0)   # première crête (sin = 1)
        echelle = boite.width / PORTEE_ESPACE
        self._cote(screen, boite.x + crete * echelle, boite.x + (crete + lam) * echelle, boite.bottom - 14, "λ",
                   COULEUR_ACCENT)

    def _dessiner_oscillo(self, screen):
        """L'oscilloscope : en haut le signal modulé (les bits sur la porteuse), en bas un zoom sur
        quelques nanosecondes de la porteuse, où l'on voit la vraie période."""
        zone = self.oscillo
        pygame.draw.rect(screen, COULEUR_FOND_ECRAN, zone, border_radius=10)
        pygame.draw.rect(screen, COULEUR_BORDURE, zone, 2, border_radius=10)
        etats = {"libre": ("En veille", COULEUR_TEXTE_GRIS), "emission": ("Émission", COULEUR_EMISSION),
                 "attente": ("Attente de réponse...", COULEUR_TEXTE_GRIS),
                 "reception": ("Réception", COULEUR_RECEPTION)}
        nom, couleur = etats[self.etat]
        if self.etat == "libre" and station_proche(self.frequence) is not None:
            nom = "Écoute"
        screen.blit(self.police_petite.render(nom, True, couleur), (zone.x + 12, zone.y + 4))

        f = self.frequence
        position = self._position_bits()
        if self.decodeur and self.etat in ("emission", "reception"):   # lettres traduites au fil des bits
            lettres = self.police_petite.render("= " + depuis_bits(self.bits[:int(position)]), True, couleur)
            screen.blit(lettres, (zone.x + 190, zone.y + 4))
        largeur = zone.width - 20
        x0 = zone.x + 10
        bruit = self._niveau_bruit()

        # octet en cours : on lit les bits, sans traduction par un dictionnaire
        if self.etat in ("emission", "reception") and self.bits:
            octet = min(len(self.bits) // 8 - 1, int(position) // 8)
            if octet >= 0:
                bits_octet = self.bits[octet * 8:octet * 8 + 8]
                valeur = int(bits_octet, 2)
                car = chr(valeur) if 32 <= valeur < 127 else "·"
                info = f"octet {octet + 1} : {bits_octet} = {car}"
                image = self.police_petite.render(info, True, couleur)
                screen.blit(image, image.get_rect(topright=(zone.right - 12, zone.y + 4)))

        # accordé sur une balise sans rien émettre : son motif de bits, qui tourne en boucle
        if self.etat == "libre":
            proche = station_proche(self.frequence)
            if proche and TYPES[proche[0]] == "balise" and proche[1] <= PORTEE_NETTE:
                image = self.police_petite.render(f"motif : {MOTIFS[proche[0]]}", True, couleur)
                screen.blit(image, image.get_rect(topright=(zone.right - 12, zone.y + 4)))

        # signal modulé, temps dilaté : f / 100 cycles par bit (une vraie porteuse en aurait des millions)
        cycles_par_bit = f / 100
        milieu, demi = zone.y + 54, 22
        points = []
        for px in range(0, largeur + 1, 2):
            pos = position - FENETRE_BITS + FENETRE_BITS * px / largeur
            amplitude = self._amplitude(pos)
            v = amplitude * math.sin(2 * math.pi * cycles_par_bit * pos) + random.uniform(-1, 1) * bruit
            points.append((x0 + px, milieu - demi * max(-1.2, min(1.2, v))))
        pygame.draw.lines(screen, couleur, False, points, 2)

        # zoom sur la porteuse : FENETRE_NS nanosecondes, donc f * 10 ns / 1000 cycles
        cycles = f * FENETRE_NS / 1000
        phase = pygame.time.get_ticks() / 700
        amplitude = self._amplitude(position)
        milieu2, demi2 = zone.y + 118, 14
        titre = f"Porteuse, zoom sur {int(FENETRE_NS)} ns : T = {nombre(1000 / f, 2)} ns"
        screen.blit(self.police_bits.render(titre, True, COULEUR_TEXTE_GRIS), (zone.x + 12, zone.y + 80))
        points = [(x0 + px, milieu2 - demi2 * max(-1.2, min(1.2, amplitude * math.sin(2 * math.pi * cycles * px / largeur - phase)
                                                              + random.uniform(-1, 1) * bruit)))
                  for px in range(0, largeur + 1, 2)]
        pygame.draw.lines(screen, couleur, False, points, 2)
        periode_px = largeur / cycles
        crete = ((math.pi / 2 + phase) / (2 * math.pi) % 1.0) * periode_px
        self._cote(screen, x0 + crete, x0 + crete + periode_px, zone.bottom - 8, "T", COULEUR_ACCENT)

    def _dessiner_spectre(self, screen):
        """Analyseur de spectre : le bruit de fond, les vaisseaux qui émettent, notre émission."""
        zone = self.zone_spectre
        screen.blit(self.police.render("Spectre", True, COULEUR_TITRE), (zone.x, zone.y - 46))
        pygame.draw.rect(screen, COULEUR_FOND_ECRAN, zone, border_radius=12)
        pygame.draw.rect(screen, COULEUR_BORDURE, zone, 2, border_radius=12)
        gauche, droite = zone.x + 12, zone.right - 12
        largeur = droite - gauche
        base, haut = zone.bottom - 28, zone.y + 56

        def pic(f, centre, hauteur, largeur_pic=2.5):
            return hauteur * math.exp(-((f - centre) / largeur_pic) ** 2)

        # hauteur et largeur du pic de chaque type : les balises clignotent, les sources naturelles pulsent
        maintenant = pygame.time.get_ticks() / 1000
        forme = {"vaisseau": (0.4, 2.5), "balise": (0.3 + 0.3 * (int(maintenant * 8) % 2), 1.8),
                 "naturel": (0.3 + 0.3 * abs(math.sin(maintenant * 3)), 4.0)}
        points = []
        for px in range(largeur + 1):
            f = F_MIN + (F_MAX - F_MIN) * px / largeur
            v = 0.04 + random.random() * 0.05
            for centre, nom, genre in STATIONS:
                hauteur, large = forme[genre]
                if genre == "vaisseau" and self.etat == "reception" and self.station and self.station[0] == nom:
                    hauteur = 0.95
                v += pic(f, centre, hauteur, large)
            for centre, _, large, force in ZONES_BRUIT:   # le bruit des zones : une bosse irrégulière
                v += force * max(0.0, 1 - abs(f - centre) / large) * (0.3 + random.random() * 0.5)
            if self.etat == "emission":
                v += pic(f, self.frequence, 1.0)
            points.append((gauche + px, base - (base - haut) * min(1.0, v)))
        pygame.draw.lines(screen, COULEUR_SPECTRE, False, points, 2)

        # noms sur trois rangées (les sources sont serrées), colorés selon leur type
        for i, (centre, nom, genre) in enumerate(sorted(STATIONS)):
            tx = gauche + (centre - F_MIN) / (F_MAX - F_MIN) * largeur
            image = self.police_bits.render(nom, True, COULEURS_TYPE[genre])
            screen.blit(image, image.get_rect(midtop=(tx, zone.y + 5 + (i % 3) * 16)))
        for centre, nom, _, _ in ZONES_BRUIT:
            tx = gauche + (centre - F_MIN) / (F_MAX - F_MIN) * largeur
            image = self.police_bits.render(nom, True, COULEUR_BROUILLAGE)
            screen.blit(image, image.get_rect(midbottom=(tx, base - 2)))
        for f in (200, 400, 600, 800):
            tx = gauche + (f - F_MIN) / (F_MAX - F_MIN) * largeur
            image = self.police_bits.render(f"{f}", True, COULEUR_TEXTE_GRIS)
            screen.blit(image, image.get_rect(midtop=(min(max(tx, gauche + 12), droite - 12), base + 6)))
        marque = gauche + (self.frequence - F_MIN) / (F_MAX - F_MIN) * largeur
        pygame.draw.line(screen, COULEUR_ACCENT, (marque, haut - 4), (marque, base), 2)

    def _dessiner_journal(self, screen):
        zone = self.zone_journal
        pygame.draw.rect(screen, COULEUR_FOND_ECRAN, zone, border_radius=12)
        pygame.draw.rect(screen, COULEUR_BORDURE, zone, 2, border_radius=12)
        titre = self.police.render("Journal", True, COULEUR_TITRE)
        screen.blit(titre, (zone.x, zone.y - 46))

        lignes = []  # (texte, couleur), du plus ancien au plus récent

        def envelopper(texte, couleur):
            mot_en_cours = ""
            for mot in texte.split(" "):
                essai = (mot_en_cours + " " + mot).strip()
                if self.police_petite.size(essai)[0] > zone.width - 40:
                    lignes.append(("   " + mot_en_cours, couleur))
                    mot_en_cours = mot
                else:
                    mot_en_cours = essai
            lignes.append(("   " + mot_en_cours, couleur))

        for qui, texte, couleur in self.journal:
            lignes.append((qui, couleur))
            envelopper(texte, COULEUR_TEXTE)
            if self.decodeur and texte and set(texte) <= {"0", "1", " "}:   # des bits : la clé USB les traduit
                envelopper("= " + depuis_bits(texte.replace(" ", "")), COULEUR_RECEPTION)
        place = (zone.height - 20) // 30
        for i, (texte, couleur) in enumerate(lignes[-place:]):
            screen.blit(self.police_petite.render(texte, True, couleur), (zone.x + 16, zone.y + 12 + i * 30))
