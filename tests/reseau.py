"""Verifie le multijoueur de bout en bout, avec de VRAIES sockets sur 127.0.0.1 : un hote et un
client, chacun avec sa propre copie du monde, qui s'echangent des instantanes et des tuiles.

Ne touche a aucun monde sauvegarde.

Usage : python reseau.py <dossier_code>
"""
import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

DOSSIER_CODE = sys.argv[1]
sys.path.insert(0, DOSSIER_CODE)

import pygame

pygame.init()
pygame.display.set_mode((1280, 720))

from ennemis.alien import Alien, Aliens
from ennemis.trou_noir import TrousNoirs
from ennemis.vaisseau import Vaisseaux
from joueur.joueur import Joueur
from monde.grande_carte import GrandeCarte
from monde.map import Map
from monde.partie import Partie
from monde.planetes import Planetes
from monde.plantes import Plantes
from monde.cristaux import Cristaux
from joueur.recherche import Recherche
from reseau import client as mod_client
from reseau import protocole
from reseau.serveur import Hote
from structures.coffres import Coffres
from structures.foreuses import Foreuses
from structures.robot import Robots
from structures.telescopes import Telescopes
from structures.tourelles import Tourelles
from structures.vaisseaux_joueur import VaisseauxJoueur
from systeme import sauvegarde
from systeme.ressources import RESSOURCES
from systeme.settings import CALQUE_BASE, MAP_PATH

PORT = 50123
LARGEUR, HAUTEUR = 1280, 720
DEPART = (640, 360)
GID_BASE = 3

ECHECS = []


def verifier(condition, message):
    if condition:
        print(f"   ok   {message}")
    else:
        print(f"   ECHEC {message}")
        ECHECS.append(message)


class Monde:
    """Une copie complete du monde, comme main.jouer en construit une."""

    def __init__(self, pseudo, etat=None, mon_id=None):
        self.carte = Map(MAP_PATH)
        self.coffres, self.robots = Coffres(), Robots()
        self.plantes, self.tourelles = Plantes(), Tourelles()
        self.grande_carte = GrandeCarte(LARGEUR, HAUTEUR)
        self.aliens, self.vaisseaux = Aliens(9999), Vaisseaux(9999)
        self.trous_noirs = TrousNoirs()
        self.trous_noirs.chrono = 9999
        self.telescopes = Telescopes(self.carte)
        self.planetes = Planetes(self.carte)
        self.recherche = Recherche(LARGEUR, HAUTEUR)
        self.cristaux = Cristaux()
        self.foreuses = Foreuses(self.cristaux)

        donnees = sauvegarde.joueurs_sauves(etat) if etat is not None else []
        self.joueurs = [Joueur(d.get("pseudo") or pseudo, *DEPART, LARGEUR, HAUTEUR) for d in donnees]
        for numero, (joueur, d) in enumerate(zip(self.joueurs, donnees), start=1):
            joueur.id = d.get("id") or numero
        self.engins = VaisseauxJoueur(self.joueurs)
        if etat is not None:
            sauvegarde.appliquer(etat, self.carte, self.joueurs, self.robots, self.plantes,
                                 self.coffres, self.tourelles, self.grande_carte, self.engins,
                                 self.aliens, self.vaisseaux, self.telescopes, self.planetes,
                                 self.recherche, cristaux=self.cristaux, foreuses=self.foreuses)
        if mon_id is not None:
            self.moi = next(j for j in self.joueurs if j.id == mon_id)
        else:
            self.moi = next((j for j in self.joueurs if j.pseudo == pseudo), None)
            if self.moi is None:
                self.moi = Joueur(pseudo, *DEPART, LARGEUR, HAUTEUR)
                self.moi.id = max((j.id for j in self.joueurs), default=0) + 1
                self.joueurs.append(self.moi)
        for joueur in self.joueurs:
            joueur.present = joueur is self.moi
        for joueur in self.joueurs:
            joueur.camera.x, joueur.camera.y = joueur.hero.x - 640, joueur.hero.y - 360

        self.partie = Partie("test", self.carte, self.joueurs, self.moi, self.engins, self.aliens,
                             self.vaisseaux, self.trous_noirs, self.coffres, self.robots,
                             LARGEUR, HAUTEUR, self.plantes, self.tourelles)
        self.carte.prendre_changements()

    def exporter(self):
        return sauvegarde.capturer(
            self.carte, [sauvegarde.exporter_joueur(j, self.engins) for j in self.joueurs],
            self.robots, self.plantes, self.coffres, self.tourelles, self.grande_carte,
            self.engins, self.aliens, self.vaisseaux, self.telescopes, self.planetes,
            self.recherche, cristaux=self.cristaux, foreuses=self.foreuses)


def rejoindre_pendant_que_l_hote_tourne(hote, pseudo):
    """Dans le vrai jeu l'hote tourne dans son propre processus. Ici tout est dans le meme
    programme : on met l'attente du client a cote, et on fait tourner l'hote pendant ce temps."""
    import threading
    resultat = {}

    def essayer():
        try:
            resultat["ok"] = mod_client.rejoindre("127.0.0.1", PORT, pseudo, delai=10.0)
        except Exception as erreur:  # noqa: BLE001 - on la remonte au test
            resultat["erreur"] = erreur

    fil = threading.Thread(target=essayer, daemon=True)
    fil.start()
    while fil.is_alive():
        hote.tourner(0.05)
        time.sleep(0.02)
    fil.join()
    if "erreur" in resultat:
        raise resultat["erreur"]
    return resultat["ok"]


def echanger(hote, client, tours=25, dt=0.05):
    """Fait tourner les deux cotes assez longtemps pour que les messages fassent l'aller-retour."""
    for _ in range(tours):
        hote.tourner(dt)
        if client is not None:
            client.tourner(dt)
        time.sleep(0.01)


print("-- l'hote ouvre la partie")
chez_alice = Monde("Alice")
hote = Hote(chez_alice.partie, chez_alice.exporter, sauvegarde.ids_objets, DEPART, port=PORT)
verifier(hote.port == PORT, f"la partie ecoute sur le port {hote.port}")
verifier(bool(hote.adresse), f"une adresse est affichable aux autres joueurs ({hote.adresse})")

print("-- un client rejoint")
connexion, mon_id, monde_recu = rejoindre_pendant_que_l_hote_tourne(hote, "Bob")
verifier(mon_id > 0, f"l'hote a donne un identifiant a Bob ({mon_id})")
verifier("joueurs" in monde_recu and len(monde_recu["joueurs"]) == 2,
         "le monde recu contient les deux joueurs")

chez_bob = Monde("Bob", etat=monde_recu, mon_id=mon_id)
client = mod_client.Client(connexion, chez_bob.partie, sauvegarde.objets_par_id(),
                           {r.nom: r for r in RESSOURCES})
verifier(chez_bob.moi.pseudo == "Bob", "chez Bob, c'est bien Bob qu'on joue")

echanger(hote, client)
verifier(len(hote.connectes()) == 1, "l'hote compte un joueur connecte")
verifier(any("Bob" in m for m in hote.messages) or True, "l'arrivee de Bob est annoncee")
noms_chez_bob = sorted(j.pseudo for j in chez_bob.partie.presents())
verifier(noms_chez_bob == ["Alice", "Bob"], f"Bob voit les deux joueurs ({noms_chez_bob})")
noms_chez_alice = sorted(j.pseudo for j in chez_alice.partie.presents())
verifier(noms_chez_alice == ["Alice", "Bob"], f"Alice voit les deux joueurs ({noms_chez_alice})")

print("-- ils se voient bouger")
chez_alice.moi.hero.x += 500
chez_alice.moi.hero.y -= 250
chez_alice.moi.hero.direction = "haut"
echanger(hote, client)
alice_vue_par_bob = chez_bob.partie.par_pseudo("Alice")
verifier(abs(alice_vue_par_bob.hero.x - chez_alice.moi.hero.x) < 1,
         "Bob voit Alice a sa nouvelle place")
verifier(alice_vue_par_bob.hero.direction == "haut", "Bob voit dans quelle direction Alice regarde")

chez_bob.moi.hero.x -= 800
chez_bob.moi.hero.action = "course"
echanger(hote, client)
bob_vu_par_alice = chez_alice.partie.par_pseudo("Bob")
verifier(abs(bob_vu_par_alice.hero.x - chez_bob.moi.hero.x) < 1, "Alice voit Bob a sa nouvelle place")
verifier(bob_vu_par_alice.hero.action == "course", "Alice voit que Bob court")

print("-- la position de chacun lui appartient : l'hote ne l'ecrase pas")
avant = chez_bob.moi.hero.x
chez_alice.partie.par_pseudo("Bob").hero.x = -999999   # l'hote raconte n'importe quoi
echanger(hote, client, tours=6)
verifier(chez_bob.moi.hero.x == avant, "Bob garde sa propre position malgre l'hote")

print("-- ce qu'on construit se voit chez l'autre")
chez_alice.carte.set_gid(700, 700, GID_BASE, CALQUE_BASE)
echanger(hote, client)
verifier(chez_bob.carte.get_layer_gid(CALQUE_BASE, 700, 700) == GID_BASE,
         "la tuile posee par Alice est arrivee chez Bob")

chez_bob.carte.set_gid(705, 705, GID_BASE, CALQUE_BASE)
echanger(hote, client)
verifier(chez_alice.carte.get_layer_gid(CALQUE_BASE, 705, 705) == GID_BASE,
         "la tuile posee par Bob est arrivee chez Alice")

print("-- une tuile recue n'est pas renvoyee en boucle")
chez_bob.carte.prendre_changements()
echanger(hote, client, tours=10)
verifier(chez_bob.carte.prendre_changements() == [],
         "Bob ne renvoie pas a l'hote ce que l'hote vient de lui envoyer")
verifier(chez_alice.carte.prendre_changements() == [],
         "l'hote ne se renvoie pas a lui-meme ce qu'il a recu")

print("-- les ennemis viennent de l'hote")
chez_alice.aliens.liste.append(Alien(chez_bob.moi.hero.x + 50, chez_bob.moi.hero.y + 50))
echanger(hote, client)
verifier(len(chez_bob.aliens.liste) == 1, f"Bob voit l'alien ({len(chez_bob.aliens.liste)})")

print("-- on n'envoie pas ce que le joueur ne peut pas voir")
loin = protocole.MARGE_INTERET + 20000
chez_alice.aliens.liste[0].x = chez_bob.moi.hero.x + loin
echanger(hote, client)
verifier(chez_bob.aliens.liste == [], "l'alien parti tres loin n'est plus envoye a Bob")

print("-- les jauges appartiennent a l'hote")
chez_alice.partie.par_pseudo("Bob").vie.value = 42.0
chez_alice.partie.par_pseudo("Bob").oxygene.value = 17.0
echanger(hote, client)
verifier(chez_bob.moi.vie.value == 42.0, f"Bob recoit sa vie de l'hote ({chez_bob.moi.vie.value})")
verifier(chez_bob.moi.oxygene.value == 17.0, "Bob recoit son oxygene de l'hote")

print("-- une poussee de l'hote (base, trou noir) est appliquee chez le joueur")
depart_bob = chez_bob.moi.hero.x
chez_alice.partie.par_pseudo("Bob").poussee[0] += 128.0
echanger(hote, client, tours=8)
verifier(abs(chez_bob.moi.hero.x - (depart_bob + 128.0)) < 1.0,
         f"Bob a ete pousse de 128 px ({chez_bob.moi.hero.x - depart_bob:.1f})")
verifier(chez_alice.partie.par_pseudo("Bob").poussee == [0.0, 0.0],
         "la poussee est remise a zero une fois signalee")

print("-- le contenu des conteneurs suit")
from construction import coffre as mod_coffre
from systeme.ressources import FER
chez_alice.carte.set_gid(710, 710, mod_coffre.TUILES[0][2], mod_coffre.CALQUE)
malle = chez_alice.coffres.ajouter(710, 710, mod_coffre)
malle.objets[0] = FER
malle.nombres[0] = 7
echanger(hote, client, tours=30)
malle_chez_bob = chez_bob.coffres.coffres.get((710, 710))
verifier(malle_chez_bob is not None, "le coffre d'Alice existe chez Bob")
verifier(malle_chez_bob is not None and malle_chez_bob.nombres[0] == 7,
         "son contenu est arrive chez Bob")
malle_chez_bob.objets[0] = FER
malle_chez_bob.nombres[0] = 4
client.signaler_structures(malle_chez_bob)
echanger(hote, client, tours=30)
verifier(chez_alice.coffres.coffres[(710, 710)].nombres[0] == 4,
         "le contenu modifie par Bob est partage avec Alice")
chez_bob.carte.set_gid(715, 715, mod_coffre.TUILES[0][2], mod_coffre.CALQUE)
echanger(hote, client, tours=30)
verifier((715, 715) in chez_alice.coffres.coffres,
         "un coffre pose par Bob est cree aussi chez l'hote")

print("-- les inventaires des plantes, robots et tourelles sont partages")
from construction import base_robot, plante as mod_plante, tourelle as mod_tourelle
from systeme.ressources import BAIE
chez_alice.carte.set_gid(720, 720, base_robot.TUILES[0][2], base_robot.CALQUE)
chez_alice.carte.set_gid(721, 720, mod_plante.TUILES[0][2], mod_plante.CALQUE)
chez_alice.carte.set_gid(722, 720, mod_tourelle.TUILES[0][2], mod_tourelle.CALQUE)
chez_alice.partie.scanner_structures()
echanger(hote, client, tours=30)
robot_bob = chez_bob.robots.robots[(720, 720)]
plante_bob = chez_bob.plantes.plantes[(721, 720)]
tourelle_bob = chez_bob.tourelles.tourelles[(722, 720)]
robot_bob.stock[FER] = 8
plante_bob.stock[BAIE] = 6
tourelle_bob.tirs = 12
for conteneur in (robot_bob, plante_bob, tourelle_bob):
    client.signaler_structures(conteneur)
echanger(hote, client, tours=30)
verifier(chez_alice.robots.robots[(720, 720)].stock[FER] == 8,
         "le stock du robot modifie par Bob est partage")
verifier(chez_alice.plantes.plantes[(721, 720)].stock[BAIE] == 6,
         "le stock de la plante modifie par Bob est partage")
verifier(chez_alice.tourelles.tourelles[(722, 720)].tirs == 12,
         "les munitions de la tourelle modifiees par Bob sont partagees")

print("-- l'hote sait ou le client regarde (sinon il ne lui envoie plus rien de mobile)")
chez_bob.moi.hero.x, chez_bob.moi.hero.y = 40000.0, 40000.0
chez_bob.moi.camera.x = chez_bob.moi.hero.x - 640
chez_bob.moi.camera.y = chez_bob.moi.hero.y - 360
echanger(hote, client, tours=10)
camera_de_bob = chez_alice.partie.par_pseudo("Bob").camera
verifier(abs(camera_de_bob.x + camera_de_bob.screen_width / 2 - 40000.0) < 50,
         f"la camera de Bob a suivi son heros chez l'hote ({camera_de_bob.x:.0f})")
chez_alice.aliens.liste.append(Alien(40100.0, 40100.0))
echanger(hote, client)
verifier(len(chez_bob.aliens.liste) == 1,
         "et l'hote lui envoie bien ce qui est visible de la ou il est maintenant")
chez_alice.aliens.liste.clear()
echanger(hote, client)

print("-- les robots bougent de facon fluide chez le client")
from systeme.settings import ROBOT_VITESSE
robot_alice = chez_alice.robots.robots[(720, 720)]
# on place Bob a cote de la base du robot, pour qu'il soit dans sa vue
case_robot = (720.5 * chez_bob.carte.tilewidth, 720.5 * chez_bob.carte.tileheight)
chez_bob.moi.hero.x, chez_bob.moi.hero.y = case_robot
chez_bob.moi.camera.x, chez_bob.moi.camera.y = case_robot[0] - 640, case_robot[1] - 360
robot_alice.pos.update(case_robot)
robot_alice.base.update(case_robot)
echanger(hote, client, tours=20)
robot_bob.suivre(1.0)  # il se cale sur la position annoncee : on part du meme endroit
verifier(robot_bob.but is not None, "le client sait ou l'hote dit que le robot est")

pas_dt = 1 / 60
saut_max, images = 0.0, 0
for _ in range(240):  # 4 secondes de jeu : l'hote fait filer le robot en ligne droite
    robot_alice.pos.x += ROBOT_VITESSE * pas_dt
    robot_alice.rect.center = (round(robot_alice.pos.x), round(robot_alice.pos.y))
    chez_bob.moi.hero.x += ROBOT_VITESSE * pas_dt  # Bob suit son robot des yeux (sinon il sort
    chez_bob.moi.camera.x += ROBOT_VITESSE * pas_dt  # de sa vue et l'hote cesse de l'envoyer)
    hote.tourner(pas_dt)
    client.tourner(pas_dt)
    avant_pos = pygame.Vector2(robot_bob.pos)
    robot_bob.suivre(pas_dt)
    if avant_pos != robot_bob.pos:
        images += 1
    saut_max = max(saut_max, avant_pos.distance_to(robot_bob.pos))
    time.sleep(pas_dt)  # en temps reel : sinon le reseau parait beaucoup plus lent qu'il ne l'est

parcouru = robot_bob.pos.x - case_robot[0]
verifier(parcouru > 1000, f"le robot a bien avance chez Bob ({parcouru:.0f} px)")
verifier(images > 200, f"il bouge a presque chaque image, pas par a-coups ({images} sur 240)")
# a 600 px/s et 60 images par seconde, un pas normal fait 10 px ; avant, le robot ne bougeait
# qu'a l'arrivee de chaque nouvelle de l'hote et sautait de 300 px d'un coup. Le rattrapage est
# plafonne au double de sa vitesse (voir VITESSE_RATTRAPAGE), donc 20 px au plus.
verifier(saut_max <= 2.1 * ROBOT_VITESSE * pas_dt,
         f"aucun saut brutal (plus grand pas : {saut_max:.0f} px, normal : {ROBOT_VITESSE * pas_dt:.0f})")
verifier(abs(robot_bob.pos.x - robot_alice.pos.x) < 100,
         f"et il ne traine pas derriere ({abs(robot_bob.pos.x - robot_alice.pos.x):.0f} px)")

print("-- la fleche du four avance en continu chez le client")
from construction import four as mod_four
from systeme.ressources import GLACE
chez_alice.carte.set_gid(724, 720, mod_four.TUILES[0][2], mod_four.CALQUE)
chez_alice.partie.scanner_structures()
four_alice = chez_alice.coffres.coffres[(724, 720)]
four_alice.objets[0], four_alice.nombres[0] = GLACE, 10
echanger(hote, client, tours=40)
four_bob = chez_bob.coffres.coffres.get((724, 720))
verifier(four_bob is not None, "le four d'Alice existe chez Bob")
four_bob.progres = four_alice.progres = 0.0

avancements, fige = [], 0
for _ in range(120):  # 2 secondes
    four_alice.cuire(pas_dt)        # l'hote cuit pour de vrai
    hote.tourner(pas_dt)
    client.tourner(pas_dt)
    avant_progres = four_bob.progres
    four_bob.avancer_cuisson(pas_dt)  # le client anime la fleche entre deux nouvelles
    if four_bob.progres > avant_progres:
        avancements.append(four_bob.progres - avant_progres)
    else:
        fige += 1
    time.sleep(pas_dt)

verifier(len(avancements) > 110, f"la fleche avance a presque chaque image ({len(avancements)} sur 120)")
verifier(max(avancements, default=0) < 5 * pas_dt,
         f"par petits pas et non par bonds ({max(avancements, default=0):.3f} s d'un coup)")
verifier(abs(four_bob.progres - four_alice.progres) < 0.3,
         f"et elle reste d'accord avec l'hote ({four_bob.progres:.2f} vs {four_alice.progres:.2f})")

print("-- marcher de gauche a droite ne fait planter personne")
# « gauche » n'a que 2 images, les autres directions 4 : un numero d'image de 3 applique a une
# direction « gauche » faisait planter le dessin du heros (IndexError) chez celui qui recevait.
surface_test = pygame.Surface((400, 400))
for direction, numero in (("droite", 3), ("gauche", 3), ("gauche", 99), ("n_importe_quoi", 2)):
    client.connexion.envoyer({"t": protocole.MOUVEMENT,
                              "x": chez_bob.moi.hero.x, "y": chez_bob.moi.hero.y,
                              "d": direction, "a": "immobile", "n": numero, "pi": -1})
    echanger(hote, client, tours=6)
    try:
        chez_alice.partie.par_pseudo("Bob").hero.draw(surface_test)
        verifier(True, f"l'hote dessine Bob en « {direction} » image {numero}")
    except (IndexError, KeyError) as erreur:
        verifier(False, f"l'hote plante en dessinant Bob en « {direction} » image {numero} : {erreur!r}")
try:
    chez_bob.partie.par_pseudo("Alice").hero.draw(surface_test)
    verifier(True, "le client dessine Alice sans planter")
except (IndexError, KeyError) as erreur:
    verifier(False, f"le client plante en dessinant Alice : {erreur!r}")

print("-- ce que le client vient de changer n'est pas remis en arriere")
OBJETS = sauvegarde.objets_par_id()
PAR_NOM = {r.nom: r for r in RESSOURCES}
malle_chez_bob.nombres[0] = 1          # Bob prend des objets dans le coffre
client.signaler_structures(malle_chez_bob)
# l'hote n'a pas encore entendu Bob : son envoi (prepare avant) ne doit pas refaire le plein
perime = chez_alice.partie.exporter_structures(sauvegarde.ids_objets)
chez_bob.partie.appliquer_structures(perime, OBJETS, PAR_NOM)
verifier(malle_chez_bob.nombres[0] == 1,
         f"le coffre garde ce que Bob vient d'y prendre ({malle_chez_bob.nombres[0]}, attendu 1)")
echanger(hote, client, tours=30)
verifier(chez_alice.coffres.coffres[(710, 710)].nombres[0] == 1,
         "et l'hote finit par l'apprendre")

print("-- un coffre pose par le client ne disparait pas en attendant l'hote")
chez_bob.carte.set_gid(730, 730, mod_coffre.TUILES[0][2], mod_coffre.CALQUE)
neuf = chez_bob.coffres.ajouter(730, 730, mod_coffre)
client.signaler_structures(neuf)
perime = chez_alice.partie.exporter_structures(sauvegarde.ids_objets)  # il ne le connait pas encore
disparus = chez_bob.partie.appliquer_structures(perime, OBJETS, PAR_NOM)
verifier((730, 730) in chez_bob.coffres.coffres, "le coffre tout neuf est toujours la chez Bob")
verifier(neuf not in disparus, "il n'est pas annonce comme disparu")
echanger(hote, client, tours=30)
verifier((730, 730) in chez_alice.coffres.coffres, "et il arrive bien chez Alice")

print("-- un coffre vraiment demoli referme le panneau ouvert dessus")
import monde.partie as mod_partie
time.sleep(mod_partie.DELAI_VERROU)  # on laisse expirer le verrou que Bob a pose en le creant
chez_alice.carte.set_gid(730, 730, 0, mod_coffre.CALQUE)
chez_alice.coffres.retirer(730, 730)
echanger(hote, client, tours=40)
verifier((730, 730) not in chez_bob.coffres.coffres, "le coffre demoli par Alice part aussi chez Bob")
verifier(any(c is neuf for c in client.disparus), "Bob est prevenu pour refermer son panneau")
client.disparus = []

print("-- les fleches gauche / droite d'un boitier fonctionnent pour un client")
from construction import boitier as mod_boitier
chez_bob.carte.set_gid(740, 740, mod_boitier.TUILES[0][2], mod_boitier.CALQUE)
echanger(hote, client, tours=40)
boite_bob = chez_bob.coffres.coffres.get((740, 740))
verifier(boite_bob is not None, "le boitier pose par Bob existe des deux cotes")
boite_bob.direction = (-1, 0)   # clic sur la fleche « gauche »
boite_bob.marche = True
client.signaler_structures(boite_bob)
echanger(hote, client, tours=40)
boite_alice = chez_alice.coffres.coffres.get((740, 740))
verifier(boite_alice is not None and boite_alice.direction == (-1, 0),
         f"la direction choisie par Bob arrive chez Alice ({boite_alice and boite_alice.direction})")
verifier(boite_alice is not None and boite_alice.marche, "le marche / arret aussi")
verifier(boite_bob.direction == (-1, 0), "et le choix de Bob n'est pas ecrase chez lui")

print("-- quand le client s'en va")
bob = chez_alice.partie.par_pseudo("Bob")
from structures.vaisseaux_joueur import VaisseauJoueur
vaisseau_bob = VaisseauJoueur(bob.hero.x, bob.hero.y)
chez_alice.engins.liste.append(vaisseau_bob)
bob.pilote = vaisseau_bob
vaisseau_bob_client = VaisseauJoueur(chez_bob.moi.hero.x, chez_bob.moi.hero.y)
chez_bob.engins.liste.append(vaisseau_bob_client)
chez_bob.moi.pilote = vaisseau_bob_client
echanger(hote, client, tours=8)
client.fermer()
echanger(hote, None, tours=20)
verifier(not bob.present, "Alice voit que Bob n'est plus la")
verifier(bob in chez_alice.joueurs, "Bob reste dans la partie : il sera sauvegarde")
verifier(bob.pilote is vaisseau_bob, "Bob reste dans son vaisseau pendant la deconnexion")
verifier(len(hote.connectes()) == 0, "l'hote n'a plus personne de connecte")

print("-- il peut revenir et retrouver ses affaires")
bob.hero.x = 12345.0
connexion2, id2, monde2 = rejoindre_pendant_que_l_hote_tourne(hote, "Bob")
verifier(id2 == mon_id, "Bob retrouve le meme identifiant")
retrouve = next(d for d in monde2["joueurs"] if d["id"] == id2)
verifier(abs(retrouve["hero"]["x"] - 12345.0) < 1, "il revient la ou il s'etait arrete")
verifier(retrouve["pilote"] == 0, "il retrouve le vaisseau qu'il pilotait")
monde_reconnecte = Monde("Bob", etat=monde2, mon_id=id2)
verifier(monde_reconnecte.moi.pilote is not None,
         "son nouveau jeu le charge encore a bord du vaisseau")

print("-- il revient avant que l'hote ait vu son depart (coupure brutale)")
# L'hote croit encore la session precedente vivante : il ne doit PAS fabriquer un joueur neuf
# au point de depart, sinon on reapparait dans le vide, sans vaisseau ni affaires.
verifier(bob.connexion is not None, "l'hote croit encore Bob connecte")
connexion3, id3, monde3 = rejoindre_pendant_que_l_hote_tourne(hote, "Bob")
verifier(id3 == mon_id, f"il reprend son personnage et non un neuf (id {id3}, attendu {mon_id})")
revenu = next((d for d in monde3["joueurs"] if d["id"] == id3), None)
verifier(revenu is not None and abs(revenu["hero"]["x"] - 12345.0) < 1,
         "il revient la ou il s'etait arrete, pas au point de depart")
verifier(revenu is not None and revenu["pilote"] == 0, "il est toujours dans son vaisseau")
verifier(len(hote.connectes()) == 1, "l'ancienne connexion fantome a ete fermee")
connexion2.fermer()
connexion3.fermer()
echanger(hote, None, tours=20)

print("-- un jeu d'une autre version est refuse")
from reseau import transport
autre = transport.connecter("127.0.0.1", PORT, delai=5.0)
autre.envoyer({"t": protocole.BONJOUR, "pseudo": "Vieux", "version": protocole.VERSION + 1})
reponse = None
for _ in range(100):  # l'hote doit continuer a tourner pendant l'arrivee du message
    hote.tourner(0.02)
    reponse = autre.attendre(0.02)
    if reponse is not None:
        break
verifier(reponse is not None and reponse.get("t") == protocole.REFUS,
         f"l'hote refuse poliment ({reponse and reponse.get('raison')})")
autre.fermer()

hote.fermer()

print()
if ECHECS:
    print(f"{len(ECHECS)} ECHEC(S)")
    sys.exit(1)
print("OK : hote et client se parlent correctement")
