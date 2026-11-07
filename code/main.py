from collections import defaultdict
from types import SimpleNamespace

import pygame

from systeme import ecran
from systeme import sauvegarde
from systeme import son
from interface.accueil import Accueil
from interface.admin import Admin
from interface.info_reseau import InfoReseau
from systeme.ressources import RESSOURCES
from structures.building import (OUTILS, antenne_sous_souris, decodeur_a_cote, deconstruire, detruire_cases, dessiner_zone,
                      dessiner_zone_deconstruction, est_outil, mode_pose, poser_bloc, reapparition,
                      table_craft_sous_souris, table_recherche_sous_souris)
from ennemis.alien import Aliens
from monde.cristaux import Cristaux
from monde.fluides import Fluides
from monde.debris import Debris
from monde.decors import Decors
from monde.fond import FondEtoiles
from structures.coffres import Coffres, PanneauCoffre
from structures.foreuses import Foreuses
from structures.installations import Installations
from construction import base_robot, panneau, plante, table_craft
from joueur.craft import Craft
from joueur.recherche import Recherche
from joueur.energy import Energy
from joueur.joueur import Joueur
from systeme.fermeture import fermer_terminal_apres_delai
from monde.map import Map
from monde.partie import Partie
from reseau import client
from reseau.serveur import Hote
from interface.menu import Menu
from ennemis.meteroite import Meteorites
from monde.grande_carte import GrandeCarte
from monde.minimap import Minimap
from monde.plantes import Plantes
from monde.planetes import Planetes
from monde.orbite import Orbite
from interface.radio_menu import Radio
from structures.robot import Robots
from joueur.respawn import Respawn
from systeme.settings import (COULEUR_FOND_PLANETE, EAU_MAX, FAIM_MAX, FPS, MAP_PATH, OXYGENE_MAX, VIE_MAX,
                      ZOOM_PAS)
from structures.stockage import PanneauStock
from structures.telescopes import PanneauTelescope, Telescopes
from structures.tourelles import Tourelles
from structures.propulsion import Propulsion, structure_sous
from structures.vaisseaux_joueur import VaisseauxJoueur
from construction import vaisseau_joueur
from ennemis.vaisseau import Vaisseaux
from ennemis.trou_noir import TrousNoirs


AUCUNE_TOUCHE = defaultdict(int)  # "aucune touche appuyée" (keys[touche] vaut 0)
PSEUDO_SOLO = "Joueur"  # nom du joueur quand on joue seul (en multijoueur, chacun choisit le sien)
COULEUR_PSEUDO = (200, 225, 255)  # le nom affiché au-dessus des autres joueurs


class _Perdu:
    """Faux inventaire : ce qui y est « rendu » est perdu (structures détruites)."""

    def ajouter_objet(self, *args):
        pass


PERDU = _Perdu()


def quitter():
    pygame.quit()
    raise SystemExit


def main():
    # ==== Initialisation de pygame + fenêtre (plein écran ou fenêtré, au choix
    # ==== dans les paramètres : voir systeme/ecran.py). Le jeu dessine toujours
    # ==== sur une surface de la taille du bureau, étirée dans la fenêtre.
    pygame.init()
    screen = ecran.creer()
    largeur, hauteur = screen.get_size()
    son.lancer_musique()  # musique de fond en continu, pendant les menus et les parties

    # ==== Menu principal -> partie -> (retour au menu principal) ...
    accueil = Accueil(largeur, hauteur)
    annonce = ""
    while True:
        choix = accueil.run(screen, annonce)
        annonce = ""
        if choix is None:
            quitter()
        if choix["mode"] == "client":
            # on rejoint : il faut avoir le monde avant de pouvoir lancer la partie
            ecrire_attente(screen, f"Connexion à {choix['ip']}...")
            try:
                connexion, mon_id, etat = client.rejoindre(choix["ip"], choix["port"], choix["pseudo"])
            except client.ErreurReseau as erreur:
                annonce = str(erreur)
                continue
            annonce = jouer(screen, "", False, None, choix["pseudo"],
                            mode="client", etat=etat, connexion=connexion, mon_id=mon_id) or ""
        else:
            annonce = jouer(screen, choix["nom"], choix["nouveau"], choix["reglages"],
                            choix["pseudo"], mode=choix["mode"]) or ""


def ecrire_attente(screen, texte):
    """Un mot au milieu de l'écran noir pendant qu'on attend (la connexion à l'hôte)."""
    screen.fill((3, 3, 12))
    police = pygame.font.Font(None, 56)
    image = police.render(texte, True, (235, 235, 245))
    screen.blit(image, image.get_rect(center=screen.get_rect().center))
    ecran.presenter()


def jouer(screen, nom, nouveau, reglages=None, pseudo=PSEUDO_SOLO, mode="solo",
          etat=None, connexion=None, mon_id=0):
    """Une partie dans le monde `nom` (créé s'il est nouveau, chargé sinon). `reglages` (monde
    nouveau seulement) : {"graine", "delai"} (délai en minutes avant les premières attaques).
    `pseudo` : sous quel nom le joueur de cette machine est sauvegardé.

    `mode` : "solo", "hote" (on héberge et on joue) ou "client" (on a rejoint quelqu'un).
    En "client", `etat` est le monde reçu de l'hôte, `connexion` la connexion ouverte et
    `mon_id` l'identifiant que l'hôte nous a donné.

    Revient quand on retourne au menu principal ou qu'on n'a plus d'oxygène ; renvoie un
    message à afficher dans le menu (pourquoi la partie s'est arrêtée), ou None."""
    largeur, hauteur = screen.get_size()
    if mode != "client":
        etat = None if nouveau else sauvegarde.charger(nom)
    clock = pygame.time.Clock()
    premiere_attaque = reglages["delai"] * 60 if reglages and reglages["delai"] else None  # secondes

    game_map = Map(MAP_PATH)
    if nouveau:
        game_map.definir_graine(reglages["graine"])
    point_depart = (largeur // 2, hauteur // 2)  # là où le héros réapparaît après sa mort s'il n'y a aucune base
    # Les joueurs de la partie : un par participant déjà connu du monde (voir joueur/joueur.py).
    # Ceux qui ne sont pas là restent dans la liste pour être sauvegardés, mais `present` est faux.
    donnees_joueurs = sauvegarde.joueurs_sauves(etat) if etat is not None else []
    joueurs = [Joueur(d.get("pseudo") or pseudo, *point_depart, largeur, hauteur)
               for d in donnees_joueurs]
    for numero, (joueur, donnees) in enumerate(zip(joueurs, donnees_joueurs), start=1):
        joueur.id = donnees.get("id") or numero  # (les sauvegardes solo d'avant n'en avaient pas)
    if mode == "client":
        moi = next(j for j in joueurs if j.id == mon_id)
    else:
        moi = next((j for j in joueurs if j.pseudo == pseudo), None)
        if moi is None:  # monde neuf, ou première partie de ce joueur dans ce monde
            moi = Joueur(pseudo, *point_depart, largeur, hauteur)
            moi.id = max((j.id for j in joueurs), default=0) + 1
            joueurs.append(moi)
    for joueur in joueurs:
        joueur.present = joueur is moi  # les autres n'arrivent qu'en se connectant
    # (noms courts : la boucle de jeu parle surtout du joueur de cette machine)
    hero, camera, inventaire = moi.hero, moi.camera, moi.inventaire
    oxygene, eau, faim, vie = moi.oxygene, moi.eau, moi.faim, moi.vie
    vue = pygame.Surface((largeur, hauteur))  # le monde y est dessiné avant le zoom
    craft = Craft(largeur, hauteur)
    recherche = Recherche(largeur, hauteur)  # table de recherche : débloque des recettes de la table de craft
    craft.recherches = recherche
    radio = Radio(largeur, hauteur)  # menu d'une antenne : fréquence + message en bits
    energie = Energy()
    meteorites = Meteorites()
    fond = FondEtoiles()
    debris = Debris()  # décor tiré de la graine : des astéroïdes partout dans le vide
    planetes = Planetes(game_map)  # grandes planètes (Mars...) à la place de leur tuile dans la carte
    robots = Robots()
    plantes = Plantes()
    stockage = PanneauStock(largeur, hauteur)  # inventaire du robot / de la plante ouvert
    coffres = Coffres()
    panneau_coffre = PanneauCoffre()  # inventaire (5x5) du coffre ouvert
    menu = Menu(largeur, hauteur)
    respawn = Respawn(largeur, hauteur)  # menu affiché à la mort du héros
    admin = Admin(largeur, hauteur)  # F3 : découvrir toute la carte, ressources infinies
    aliens = Aliens(premiere_attaque)  # ils foncent sur le héros
    minimap = Minimap()  # petite carte en haut à gauche (N l'affiche / la cache)
    grande_carte = GrandeCarte(largeur, hauteur)  # M : le monde déjà parcouru, avec ses coordonnées
    vaisseaux = Vaisseaux(premiere_attaque)  # vaisseaux ennemis : ils tournent autour du héros et lui tirent dessus
    trous_noirs = TrousNoirs()  # le trou noir africain : dérive dans l'espace, avale les météorites et attire le héros
    tourelles = Tourelles()  # elles s'orientent vers les aliens et leur tirent dessus
    telescopes = Telescopes(game_map)  # ils tournent lentement vers des directions au hasard
    panneau_telescope = PanneauTelescope(largeur, hauteur, telescopes)  # clic sur un télescope : sa fréquence
    panneau_coffre.telescopes = telescopes  # un boîtier avec une clé USB satellite pilote un télescope
    grande_carte.telescopes = telescopes  # une icône de satellite par télescope sur la carte (M)
    grande_carte.planetes = planetes  # les planètes sur la carte, là où elles sont (Mars tourne autour du Soleil)
    engins = VaisseauxJoueur(joueurs)  # les vaisseaux posés : on monte dedans pour voler au-dessus du vide
    propulsion = Propulsion()  # les réacteurs poussent leur base (elle glisse d'une tuile à l'autre)
    carte_espace = game_map  # game_map devient la carte d'une planète quand on y descend (voir orbite)
    orbite = Orbite(largeur, hauteur)  # au-dessus d'une planète : bouton pour descendre dedans (et remonter)
    decors = Decors()  # sur une planète : les arbres de ses biomes
    cristaux = Cristaux()  # sur une planète : les cristaux lumineux (E à côté : un shard)
    fluides = Fluides()    # sur une planète : mares d'eau, d'acide, de pétrole ou de lave
    chrono_acide = 0.0
    foreuses = Foreuses(cristaux)  # sur les gisements de la Terre et de Mars : elles extraient le minerai toutes seules

    # objet de départ : seulement l'outil de déconstruction (les constructions se
    # récupèrent en déconstruisant, puis s'empilent dans l'inventaire)
    for outil in OUTILS:
        inventaire.ajouter_objet(outil)
    inventaire.ajouter_objet(table_craft)  # une table de craft pour commencer à fabriquer
    if nouveau:
        inventaire.ajouter_objet(panneau, 4)  # de quoi produire de l'énergie
        inventaire.ajouter_objet(base_robot)  # une base pour un premier robot

    # ce qui est construit dans l'espace, et sur chaque planète (à part : voir structures/installations.py)
    espace = Installations(carte_espace, coffres, plantes, robots, tourelles, energie)
    sur_planetes = {}  # carte d'une planète (ex : "terre.tmx") -> ses Installations, créées à la première visite
    en_attente = {} if nouveau else dict(etat.get("constructions_planetes", {}))  # sauvegardées, pas encore revisitées

    def ici():
        """Les installations de la carte où l'on est : l'espace, ou la planète où l'on est descendu."""
        if orbite.planete is None:
            return espace
        if game_map.nom not in sur_planetes:
            sur_planetes[game_map.nom] = Installations(game_map)
            if game_map.nom in en_attente:
                sauvegarde.appliquer_installations(en_attente.pop(game_map.nom), sur_planetes[game_map.nom])
        return sur_planetes[game_map.nom]

    def sauver():
        if mode == "client":
            return  # le monde n'est pas le nôtre : c'est l'hôte qui le garde
        if orbite.planete is None:
            exportes = [sauvegarde.exporter_joueur(j, engins) for j in joueurs]
        else:
            # sur une planète : on sauvegarde comme si on était remonté en orbite (on y revient au chargement)
            x, y = orbite.position_retour(planetes)
            heros = SimpleNamespace(x=x, y=y, direction=hero.direction)
            cam = SimpleNamespace(x=x - camera.screen_width / 2, y=y - camera.screen_height / 2, zoom=camera.zoom)
            exportes = [sauvegarde.exporter_joueur(j, engins, hero=heros, camera=cam,
                                                   pilote=orbite.retour["vaisseau"]) if j is moi
                        else sauvegarde.exporter_joueur(j, engins) for j in joueurs]
        construit = dict(en_attente)  # (planètes pas revisitées depuis le chargement : telles quelles)
        construit.update({carte: sauvegarde.exporter_installations(installations)
                          for carte, installations in sur_planetes.items()})
        sauvegarde.sauver(nom, sauvegarde.capturer(
            carte_espace, exportes, robots, plantes, coffres, tourelles,
            grande_carte, engins, aliens, vaisseaux, telescopes, planetes, recherche,
            cristaux=cristaux, foreuses=foreuses, constructions_planetes=construit))

    def images_descente():
        """Pour l'animation de la descente sur une planète : (la vue sans ce qui descend, l'image de ce
        qui descend, sa position dans la vue, le héros dans la vue). Ce qui descend : le héros, avec le
        vaisseau qu'il pilote, ou avec la base sur laquelle il se tient (sa partie à l'écran)."""
        tw, th = game_map.tilewidth, game_map.tileheight
        cases = frozenset()
        if moi.pilote is None:
            x, y = hero.hitbox(hero.x, hero.y).center
            base_heros = structure_sous(game_map, (int(x // tw), int(y // th)))
            if base_heros:
                gauche, haut = camera.x // tw - 2, camera.y // th - 2
                droite, bas = (camera.x + camera.screen_width) // tw + 2, (camera.y + camera.screen_height) // th + 2
                cases = frozenset((cx, cy) for cx, cy in base_heros if gauche <= cx <= droite and haut <= cy <= bas)
        # le fond : tout, sauf la base (mise à part et dessinée très loin), le héros et son vaisseau
        game_map.animer([(cases, (10 ** 7, 10 ** 7))])
        taille = (camera.screen_width, camera.screen_height)
        image_fond = pygame.Surface(taille)
        fond.draw(image_fond, camera.zoom)
        planetes.draw(image_fond, camera)
        debris.draw(image_fond, camera, game_map, planetes.disques(camera))
        game_map.draw(image_fond, camera)
        telescopes.draw_monde(image_fond, camera, game_map)
        engins.draw(image_fond, camera.offset, hero, [v for v in engins.liste if v is not moi.pilote])
        aliens.draw(image_fond, camera.offset)
        vaisseaux.draw(image_fond, camera.offset)
        meteorites.draw(image_fond, camera.offset)
        trous_noirs.draw(image_fond, camera.offset)
        # ce qui descend : la base (si on est dessus), puis le vaisseau piloté ou le héros
        objet = pygame.Surface(taille, pygame.SRCALPHA)
        if cases:
            surface, (x0, y0) = game_map.image_masque()
            objet.blit(surface, (x0 * tw - camera.x, y0 * th - camera.y))
        if moi.pilote is not None:
            engins.draw(objet, camera.offset, hero, [moi.pilote])
        else:
            hero.draw(objet, camera.offset)
        game_map.animer([])  # (la propulsion remet ses propres cases à la prochaine image)
        cadre = objet.get_bounding_rect()
        ancre = hero.hitbox(hero.x, hero.y).center
        return (image_fond, objet.subsurface(cadre).copy(), cadre.topleft,
                (ancre[0] - camera.x, ancre[1] - camera.y))

    if not nouveau:
        sauvegarde.appliquer(etat, game_map, joueurs, robots, plantes, coffres, tourelles,
                             grande_carte, engins, aliens, vaisseaux, telescopes, planetes, recherche,
                             cristaux=cristaux, foreuses=foreuses)
    tourelles.scan(game_map)  # les tourelles déjà posées (carte chargée) tirent aussi
    plantes.scan(game_map)  # les plantes déjà dessinées dans la carte produisent aussi
    coffres.scan(game_map)  # ... et les coffres / réacteurs dessinés dans la carte s'ouvrent
    robots.scan(game_map)  # ... et les bases de robot dessinées dans la carte ont leur robot

    # ==== Réseau
    # La partie rassemble le monde et ses joueurs ; c'est elle qui sait le résumer pour
    # l'envoyer et appliquer ce qu'on reçoit (voir monde/partie.py).
    partie = Partie(nom, game_map, joueurs, moi, engins, aliens, vaisseaux, trous_noirs,
                    coffres, robots, largeur, hauteur, plantes, tourelles)
    game_map.prendre_changements()  # le chargement a modifié la carte : rien à envoyer pour autant
    reseau = None
    if mode == "hote":
        def exporter_monde():
            return sauvegarde.capturer(
                carte_espace, [sauvegarde.exporter_joueur(j, engins) for j in joueurs],
                robots, plantes, coffres, tourelles, grande_carte, engins, aliens, vaisseaux,
                telescopes, planetes, recherche, cristaux=cristaux, foreuses=foreuses)
        try:
            reseau = Hote(partie, exporter_monde, sauvegarde.ids_objets, point_depart)
        except OSError as erreur:
            return f"Impossible d'ouvrir la partie aux autres joueurs : {erreur}"
    elif mode == "client":
        reseau = client.Client(connexion, partie, sauvegarde.objets_par_id(),
                               {r.nom: r for r in RESSOURCES})
    hote = reseau is None or reseau.hote  # c'est nous qui simulons le monde partagé
    info_reseau = InfoReseau(largeur, hauteur)
    police_pseudo = pygame.font.Font(None, 28)

    def dessiner_autres(surface, offset):
        """Les autres joueurs présents sur la même carte, avec leur pseudo au-dessus de la tête.
        Celui qui pilote un vaisseau n'est pas dessiné : on voit son vaisseau (engins.draw)."""
        for joueur in joueurs:
            if (joueur is moi or not joueur.present or joueur.carte != moi.carte
                    or joueur.pilote is not None):
                continue
            autre = joueur.hero
            autre.draw(surface, propulsion.offset_hero(offset, joueur))
            image = autre.images["immobile", "bas"][0]
            etiquette = police_pseudo.render(joueur.pseudo, True, COULEUR_PSEUDO)
            fond = etiquette.get_rect().inflate(10, 4)
            fond.midbottom = (autre.x - offset[0] + image.get_width() // 2,
                              autre.y - offset[1] - 2)
            voile = pygame.Surface(fond.size, pygame.SRCALPHA)
            voile.fill((10, 10, 20, 150))
            surface.blit(voile, fond)
            surface.blit(etiquette, etiquette.get_rect(center=fond.center))

    if nouveau:
        sauver()  # le monde existe tout de suite dans la liste des mondes

    def fermer_reseau():
        if reseau is not None:
            reseau.fermer()

    # ==== Boucle de jeu principale
    while True:
        dt = clock.tick(FPS) / 1000  # temps écoulé depuis la frame précédente, en secondes

        # ---- Réseau : on accueille, on écoute, on annonce (jamais bloquant)
        if reseau is not None:
            reseau.tourner(dt)
            info_reseau.annoncer(reseau.messages)
            reseau.messages = []
            # un conteneur démoli par quelqu'un d'autre : on referme le panneau ouvert dessus,
            # sinon on continuerait à ranger des objets dans un coffre qui n'existe plus
            for conteneur in reseau.disparus:
                panneau_coffre.fermer_si(conteneur)
                stockage.fermer_si(conteneur)
            reseau.disparus = []
            if not hote and reseau.fini:
                sauver()
                return reseau.fini  # l'hôte est parti, ou la connexion est tombée

        # ---- Évènements (clavier, fermeture...)
        # (dans un vaisseau téléporteur, F ouvre une petite carte : un clic y emmène, voir plus bas)
        grande_carte.teleporteur = engins.shards_a_bord(moi) if orbite.planete is None else None
        for event in pygame.event.get():
            event = ecran.traduire(event)  # clics ramenés dans la surface de jeu (fenêtre réduite)
            son.handle_event(event)
            if event.type == pygame.QUIT:
                sauver()
                fermer_reseau()
                quitter()
            if orbite.animation is not None:
                continue  # pendant l'animation de la descente, on ne fait rien d'autre
            if respawn.ouvert:
                # menu de mort : il absorbe tous les évènements
                action = respawn.handle_event(event)
                if action == "reapparaitre":
                    if orbite.planete is not None:  # mort sur une planète : on réapparaît dans l'espace
                        orbite.remonter(moi, engins, planetes)
                        game_map = carte_espace
                    moi.ressusciter()
                    hero.x, hero.y = reapparition(game_map, hero, point_depart)  # sur la base la plus proche
                    moi.pilote = None  # (le vaisseau reste où il est)
                    aliens.liste.clear()
                    vaisseaux.vider()
                elif action == "menu_principal":
                    fermer_reseau()
                    return  # la dernière sauvegarde reste intacte
                continue
            if not menu.ouvert and admin.handle_event(event, inventaire, grande_carte):
                continue  # panneau admin (F3)
            if not menu.ouvert:
                if (radio.handle_event(event)
                        or panneau_telescope.handle_event(event)
                        or craft.handle_event(event, inventaire)
                        or recherche.handle_event(event, inventaire)):
                    continue
                # (on retient le conteneur AVANT de traiter l'évènement : il peut refermer le panneau)
                conteneur_stock, conteneur_coffre = stockage.ouvert, panneau_coffre.ouvert
                if stockage.handle_event(event, inventaire):
                    if mode == "client":
                        reseau.signaler_structures(conteneur_stock)
                    continue
                if panneau_coffre.handle_event(event, inventaire):
                    if mode == "client":
                        reseau.signaler_structures(conteneur_coffre)
                    continue
                if grande_carte.handle_event(
                        event, inventaire,
                        libre=not (radio.ouvert or craft.ouvert or recherche.ouvert
                                   or stockage.ouvert is not None
                                   or panneau_coffre.ouvert is not None
                                   or panneau_telescope.ouvert is not None)):
                    continue
            etait_ouvert = menu.ouvert
            action = menu.handle_event(event)
            if action == "sauvegarder":
                sauver()
                menu.afficher_message("Monde sauvegardé")
            elif action == "menu_principal":
                sauver()
                fermer_reseau()
                return
            elif action == "quitter":
                sauver()
                fermer_reseau()
                quitter()
            if etait_ouvert or menu.ouvert:
                continue  # menu pause (ou Echap qui l'ouvre) : il absorbe les évènements
            if inventaire.handle_event(event):
                continue  # le clic était sur l'inventaire
            if minimap.handle_event(event):
                continue
            if orbite.clic(event):
                if orbite.planete is None:
                    orbite.commencer_descente(*images_descente())  # on rétrécit, puis on descend (voir plus bas)
                else:
                    orbite.remonter(moi, engins, planetes)
                    game_map = carte_espace
                continue

            # Vaisseau du joueur : E descend, F ouvre son carburant (quand on est dedans) ; dans un vaisseau
            # téléporteur, F ouvre la petite carte où l'on choisit où se téléporter
            if event.type == pygame.KEYDOWN and moi.pilote is not None and not inventaire.ouvert:
                if event.key == pygame.K_e:
                    engins.descendre(moi, game_map)
                    continue
                if event.key == pygame.K_f:
                    if moi.pilote.shards is not None:
                        grande_carte.ouvrir(inventaire, petite=True)
                    else:
                        panneau_coffre.ouvrir(moi.pilote.coffre, inventaire)
                    continue
            # Sur une planète, E à côté d'un cristal lumineux : on en détache un shard
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_e and orbite.planete is not None
                    and not inventaire.ouvert and cristaux.recolter(game_map, hero, inventaire)):
                continue
            # Foreuse : clic gauche avec elle sélectionnée pour la poser (seulement sur la Terre) ; sur une
            # planète, clic sur une foreuse posée : son inventaire (l'outil de déconstruction la reprend)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not inventaire.ouvert:
                pos = camera.screen_to_view(event.pos)
                monde = (pos[0] + camera.x, pos[1] + camera.y)
                objet = inventaire.objet_selectionne
                if getattr(objet, "FOREUSE", False):
                    sol = game_map if orbite.planete is not None else None
                    if foreuses.poser(sol, *monde, hero):
                        inventaire.consommer_selection()
                    continue
                visee = foreuses.sous_souris(game_map, *monde) if orbite.planete is not None else None
                if visee is not None:
                    if est_outil(objet):
                        if foreuses.enlever(game_map, visee, inventaire):
                            panneau_coffre.fermer_si(visee.coffre)
                    else:
                        panneau_coffre.ouvrir(visee.coffre, inventaire)
                    continue
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3) and not inventaire.ouvert
                    and not est_outil(inventaire.objet_selectionne) and orbite.planete is None):
                pos = camera.screen_to_view(event.pos)
                monde = (pos[0] + camera.x, pos[1] + camera.y)
                objet = inventaire.objet_selectionne
                if event.button == 1 and getattr(objet, "VAISSEAU_JOUEUR", False):
                    if moi.pilote is None and engins.poser(*monde, hero, game_map, objet):
                        inventaire.consommer_selection()  # le vaisseau est posé
                        if mode == "client":
                            reseau.signaler_structures(engins.liste[-1])  # l'hôte ne le connaît pas encore
                    continue
                vise = engins.sous_souris(*monde, hero)
                if vise is not None:
                    if event.button == 3:
                        panneau_coffre.ouvrir(vise.coffre, inventaire)  # clic droit : son inventaire
                    elif moi.pilote is None:
                        engins.monter(vise, moi)  # clic gauche : on monte dedans
                    continue

            # Molette : zoom / dézoom autour de la souris
            if event.type == pygame.MOUSEWHEEL:
                camera.zoom_by(ZOOM_PAS ** event.y, ecran.souris())

            # Clic gauche avec une bouteille d'eau ou une baie sélectionnée : on la boit /
            # la mange (seulement si la jauge n'est pas déjà pleine)
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and not inventaire.ouvert):
                objet = inventaire.objet_selectionne
                if getattr(objet, "EAU", 0) and eau.value < EAU_MAX:
                    eau.boire(objet.EAU)
                    inventaire.consommer_selection()
                    continue
                if getattr(objet, "VIE", 0) and vie.value < VIE_MAX:
                    vie.soigner(objet.VIE)
                    inventaire.consommer_selection()
                    continue
                if getattr(objet, "FAIM", 0) and faim.value < FAIM_MAX:
                    faim.manger(objet.FAIM)
                    inventaire.consommer_selection()
                    continue

            # Clic gauche sur une table de craft, un coffre, un robot ou une plante : ouvre son menu
            # (sauf avec l'outil de déconstruction, qui l'enlève). Aussi sur une planète (ses propres installations).
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and not inventaire.ouvert and not est_outil(inventaire.objet_selectionne)):
                pos = camera.screen_to_view(event.pos)
                local = ici()
                if table_craft_sous_souris(game_map, camera, pos):
                    craft.ouvrir(inventaire)
                    continue
                if table_recherche_sous_souris(game_map, camera, pos):
                    recherche.ouvrir(inventaire)  # l'arbre de recherche
                    continue
                if antenne_sous_souris(game_map, camera, pos):
                    # un clic sur une antenne ouvre la radio (avec un boîtier à côté contenant une clé USB : bits traduits en lettres)
                    radio.ouvrir(inventaire, decodeur_a_cote(game_map, camera, pos, local.coffres))
                    continue
                telescope_vise = telescopes.sous_souris(game_map, camera, pos) if orbite.planete is None else None
                if telescope_vise is not None:
                    panneau_telescope.ouvrir(telescope_vise, inventaire)  # choisir la fréquence de son signal
                    continue
                tourelle_visee = local.tourelles.sous_souris(game_map, camera, pos)
                if tourelle_visee is not None and tourelle_visee.cases and inventaire.objet_selectionne is tourelle_visee.cases[0]:
                    tourelle_visee.charger(inventaire)  # clic avec sa munition (balles performantes : canon) : on la charge
                    if mode == "client":
                        reseau.signaler_structures(tourelle_visee)
                    continue
                if tourelle_visee is not None and tourelle_visee.cases:
                    stockage.ouvrir(tourelle_visee)  # sinon : son inventaire d'1 case (la plasma n'en a pas)
                    continue
                coffre_vise = local.coffres.sous_souris(game_map, camera, pos)
                if coffre_vise is not None:
                    panneau_coffre.ouvrir(coffre_vise, inventaire)
                    continue
                cible = (local.robots.robot_sous_souris(pos, camera)
                         or local.plantes.sous_souris(game_map, camera, pos))
                if cible is not None:
                    stockage.ouvrir(cible)
                    continue

            # Clic gauche : l'outil de déconstruction enlève la structure visée, une
            # construction pose son bloc de tuiles centré sur la souris (dans l'espace ou sur une planète)
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and mode_pose(inventaire) and moi.pilote is None):
                pos = camera.screen_to_view(event.pos)
                objet = inventaire.objet_selectionne
                local = ici()
                if est_outil(objet):
                    vaisseau_vise = (engins.sous_souris(pos[0] + camera.x, pos[1] + camera.y, hero)
                                     if orbite.planete is None else None)  # (les vaisseaux restent dans l'espace)
                    if vaisseau_vise is not None:
                        # un vaisseau posé : il retourne dans l'inventaire (une fois son carburant repris)
                        if engins.enlever(pos[0] + camera.x, pos[1] + camera.y, moi, inventaire):
                            panneau_coffre.fermer_si(vaisseau_vise.coffre)
                        continue
                    enleve = deconstruire(game_map, camera, pos, hero.hitbox(hero.x, hero.y),
                                          inventaire, local.coffres)
                    if enleve and getattr(enleve[0], "COFFRE", False):
                        # coffre ou réacteur (seulement possible quand il est vide)
                        panneau_coffre.fermer_si(local.coffres.retirer(*enleve[1]))
                    elif enleve and getattr(enleve[0], "ROBOT", False):
                        # la base part, le robot aussi
                        stockage.fermer_si(local.robots.retirer(*enleve[1]))
                    elif enleve and getattr(enleve[0], "TOURELLE", False):
                        stockage.fermer_si(local.tourelles.retirer(*enleve[1], inventaire))  # munitions rendues
                    elif enleve and enleve[0] is plante:
                        # la plante part, ses baies vont dans l'inventaire
                        stockage.fermer_si(local.plantes.retirer(*enleve[1], inventaire))
                    elif enleve and getattr(enleve[0], "TELESCOPE", False):
                        # un télescope : il oublie sa fréquence, son panneau se ferme
                        telescopes.etats.pop(enleve[1], None)
                        panneau_telescope.fermer_si(enleve[1])
                else:
                    case = poser_bloc(game_map, camera, pos, objet)
                    if case:
                        inventaire.consommer_selection()  # un exemplaire de moins
                        nouveau = None
                        if getattr(objet, "ROBOT", False):
                            local.robots.ajouter(*case, game_map)  # un robot apparaît sur sa base
                            nouveau = local.robots.robots.get(case)
                        elif getattr(objet, "TOURELLE", False):
                            local.tourelles.ajouter(*case, game_map)  # une tourelle qui tire sur les aliens
                            nouveau = local.tourelles.tourelles.get(case)
                        elif objet is plante:
                            local.plantes.ajouter(*case)  # une plante qui produit des baies
                            nouveau = local.plantes.plantes.get(case)
                        elif getattr(objet, "COFFRE", False):
                            # un coffre (5x5) ou un réacteur (2 cases), vide
                            nouveau = local.coffres.ajouter(*case, objet)
                        if mode == "client" and nouveau is not None:
                            # il n'existe encore que chez nous : on le garde le temps que l'hôte,
                            # prévenu par la tuile, nous le renvoie (sinon son envoi l'effacerait)
                            reseau.signaler_structures(nouveau)

        if grande_carte.destination is not None:
            engins.teleporter(*grande_carte.destination, game_map, moi)  # case choisie sur la petite carte (F)
            grande_carte.destination = None
        if grande_carte.demande_carburant:  # bouton « Carburant » de la petite carte
            grande_carte.demande_carburant = False
            if moi.pilote is not None:
                panneau_coffre.ouvrir(moi.pilote.coffre, inventaire)

        # ---- Mise à jour (oxygène, déplacement, caméra, streaming des chunks)
        # (rien ne bouge tant que le menu pause est ouvert, ni pendant l'animation de la descente)
        if orbite.animation is not None and orbite.avancer_animation(dt):
            game_map = orbite.descendre(moi)  # dans la planète : sa carte remplace l'espace
        local = ici()  # les installations de la carte où l'on est
        moi.carte = None if orbite.planete is None else game_map.nom
        # les joueurs là, et sur la même carte que nous : les seuls que les ennemis d'ici voient
        presents = [j for j in joueurs if j.present and j.carte == moi.carte]
        if not menu.ouvert and not respawn.ouvert and orbite.animation is None:
            dans_espace = orbite.planete is None  # (sur une planète, ce qui est propre à l'espace attend)
            # (le réacteur nucléaire ne produit qu'avec une barre ; chaque planète a sa propre énergie)
            # Le bilan d'énergie se déduit de la carte et des conteneurs : un client peut donc le
            # calculer chez lui, il trouvera le même résultat que l'hôte.
            for installations in (espace, *sur_planetes.values()):
                installations.energie.update(installations.carte, installations.coffres)
            if hote:
                # Les jauges appartiennent à l'hôte : lui les calcule pour tout le monde, le
                # client les reçoit dans l'instantané (sinon elles baisseraient deux fois).
                for joueur in presents:
                    if joueur.pilote is None:  # (le cockpit est étanche : pas de perte d'oxygène)
                        joueur.oxygene.update(dt, game_map, joueur.hero, energie)
                    joueur.eau.update(dt)
                    joueur.faim.update(dt)
            cause = moi.cause_mort()
            if cause:
                respawn.ouvrir(cause)  # le jeu se met en pause : on réapparaît ou on quitte
                continue
            # le héros ne bouge pas quand on tape un message dans la radio
            touches = AUCUNE_TOUCHE if radio.ouvert or grande_carte.ouvert else pygame.key.get_pressed()
            if moi.pilote is None:
                hero.update(dt, touches, game_map)
                if not dans_espace:
                    chrono_acide += dt
                    if chrono_acide >= 0.5:
                        chrono_acide = 0.0
                        if fluides.dans_acide(hero, game_map):
                            vie.subir(5)
            else:
                engins.update(dt, touches, moi)  # le vaisseau vole (et emmène le héros)
            if dans_espace:
                grande_carte.update(game_map, hero)  # les cases autour du héros sont découvertes
            radio.update(dt)
            camera.update(propulsion.cible_camera(moi))  # (le héros glisse avec la base qui est poussée)
            if dans_espace:
                minimap.update(dt, game_map, hero)
            game_map.update(camera)
            orbite.update(dt, planetes, hero, game_map.tilewidth, camera)  # au-dessus d'une planète : bouton pour y descendre
            if dans_espace:
                # les météorites ne sont que du décor : chaque machine fait passer les siennes
                # (seul l'hôte a celles que les robots vont vraiment chercher)
                meteorites.update(dt, presents)
            telescopes.update(dt)
            planetes.update(dt)
            cristaux.update(dt)  # (les lueurs pulsent, les éclats volent)
            fluides.update(dt)   # (les mares pulsent)
            telescopes.reveler(dt, grande_carte)  # chaque télescope découvre la carte là où il regarde

            # ---- Ce qui suit appartient à l'hôte : les ennemis, ce qui produit, ce qui bouge
            # tout seul. Un client ne le simule pas (ça se produirait deux fois, chacun dans son
            # coin) : il le reçoit dans les instantanés et les changements de tuiles.
            if hote:
                avant = {j: (j.hero.x, j.hero.y) for j in presents if j is not moi}
                if dans_espace:
                    trous_noirs.update(dt, presents, meteorites)
                    # les trous noirs du monde (ceux des systèmes, et le supermassif au cœur de chaque
                    # galaxie) aspirent les héros qui s'en approchent
                    planetes.aspirer(dt, presents)
                aliens.update(dt, presents)
                for cases in (vaisseaux.update(dt, presents, game_map) if dans_espace else ()):
                    # fondation détruite : tout ce qui était dessus est cassé (rien n'est rendu)
                    for objet, (ox, oy) in detruire_cases(game_map, cases):
                        if getattr(objet, "COFFRE", False):
                            panneau_coffre.fermer_si(coffres.retirer(ox, oy))
                        elif getattr(objet, "ROBOT", False):
                            stockage.fermer_si(robots.retirer(ox, oy))
                        elif getattr(objet, "TOURELLE", False):
                            stockage.fermer_si(tourelles.retirer(ox, oy, PERDU))
                        elif objet is plante:
                            stockage.fermer_si(plantes.retirer(ox, oy, PERDU))
                # (dans l'espace, elles tirent aussi sur les vaisseaux ennemis)
                local.tourelles.update(dt, (aliens, vaisseaux) if dans_espace else (aliens,), local.energie)
                foreuses.update(dt, None if dans_espace else game_map)  # elles creusent, même quand on est ailleurs
                robots.update(dt, meteorites, energie)  # les robots vont chercher les météorites proches
                # partout, les plantes alimentées produisent des baies, les fours cuisent, les
                # oxygénateurs soufflent (d'abord ceux de là où l'on est). Un oxygénateur
                # alimente tous ceux qui sont là, pas seulement celui qui l'a posé.
                besoin = max((OXYGENE_MAX - j.oxygene.value for j in presents), default=0)
                for installations in (local, *(i for i in (espace, *sur_planetes.values()) if i is not local)):
                    installations.plantes.update(dt, installations.energie)
                    souffle = installations.coffres.update(dt, besoin)
                    for joueur in presents:
                        joueur.oxygene.recevoir(souffle)
                if dans_espace:
                    # les réacteurs poussent leur base (et emmènent les joueurs posés dessus)
                    propulsion.update(dt, game_map, coffres, robots, plantes, tourelles, presents)
                # Un joueur fait autorité sur sa position : l'hôte ne peut pas la lui imposer.
                # Ce qu'il vient de lui faire subir (base poussée, trou noir) part donc en
                # « poussée », que le joueur appliquera chez lui (voir reseau/protocole.py).
                for joueur, (x, y) in avant.items():
                    joueur.poussee[0] += joueur.hero.x - x
                    joueur.poussee[1] += joueur.hero.y - y
            else:
                # ---- Côté client : on ne simule rien, mais ce que l'hôte nous raconte arrive
                # par paquets (20 fois par seconde pour les positions, 2 fois pour les
                # conteneurs) alors qu'on dessine 60 images par seconde. On comble entre deux
                # nouvelles, sinon les robots sautent d'un point à l'autre et la flèche des
                # fours avance par à-coups.
                robots.suivre(dt)
                coffres.avancer_cuisson(dt)

        # ---- Dessin de la frame
        # Le monde est dessiné sur une vue de la taille visible (plus petite
        # quand on zoome), puis agrandie à la taille de la fenêtre.
        taille_vue = (camera.screen_width, camera.screen_height)
        if vue.get_size() != taille_vue:
            vue = pygame.Surface(taille_vue)
        souris = ecran.souris()
        if orbite.animation is not None:
            orbite.dessiner_animation(vue)  # le héros (et son vaisseau ou sa base) rétrécit
        elif orbite.planete is not None:
            # sur une planète : sa carte, sans fond étoilé ni astéroïdes (ni ce qui est resté dans l'espace)
            vue.fill(COULEUR_FOND_PLANETE)
            game_map.draw(vue, camera)
            fluides.draw(vue, camera, game_map)           # mares sur le sol (avec lueurs de lave/acide)
            cristaux.draw_lueurs(vue, camera, game_map)  # le sol éclairé par les cristaux
            local.robots.draw_monde(vue, camera.offset)  # (les tuiles des constructions : dessinées par la carte)
            local.tourelles.draw_monde(vue, camera.offset)
            pied = hero.hitbox(hero.x, hero.y).bottom
            # arbres, cristaux et foreuses derrière le héros...
            decors.draw(vue, camera, game_map, pied, devant=False, autres=(cristaux, foreuses))
            orbite.dessiner_vaisseau_casse(vue, camera)  # descendu avec son vaisseau : le voilà, écrasé
            dessiner_autres(vue, camera.offset)
            hero.draw(vue, camera.offset)
            decors.draw(vue, camera, game_map, pied, devant=True, autres=(cristaux, foreuses))  # ... et ceux devant lui
            cristaux.draw_eclats(vue, camera)
            foreuses.draw_barres(vue, camera, game_map)
            if not inventaire.ouvert and not inventaire.contient(souris):
                pos = camera.screen_to_view(souris)
                objet = inventaire.objet_selectionne
                if getattr(objet, "FOREUSE", False):  # la foreuse à poser, sous la souris
                    foreuses.apercu(vue, camera, game_map, pos[0] + camera.x, pos[1] + camera.y, hero)
                elif est_outil(objet):  # la foreuse que l'outil de déconstruction reprendrait
                    foreuses.apercu_enlever(vue, camera, game_map, pos[0] + camera.x, pos[1] + camera.y)
            aliens.draw(vue, camera.offset)
        else:
            fond.draw(vue, camera.zoom)  # étoiles fixes derrière la carte
            planetes.draw(vue, camera)  # les planètes : tout au fond, derrière les débris et les bases (elles sont loin)
            # débris de décor : derrière la carte (cachés par les bases), mais pas sur les planètes
            debris.draw(vue, camera, game_map, planetes.disques(camera))
            game_map.draw(vue, camera)
            robots.draw_monde(vue, camera.offset, propulsion)
            tourelles.draw_monde(vue, camera.offset, propulsion)
            telescopes.draw_monde(vue, camera, game_map, propulsion)
            engins.draw(vue, camera.offset, hero)
            dessiner_autres(vue, camera.offset)
            if moi.pilote is None:
                hero.draw(vue, propulsion.offset_hero(camera.offset, moi))
            aliens.draw(vue, camera.offset)
            vaisseaux.draw(vue, camera.offset)
            meteorites.draw(vue, camera.offset)
            trous_noirs.draw(vue, camera.offset)
        if (getattr(inventaire.objet_selectionne, "VAISSEAU_JOUEUR", False) and moi.pilote is None
                and not inventaire.ouvert and not craft.ouvert and not recherche.ouvert
                and not inventaire.contient(souris) and not stockage.contient(souris)
                and orbite.planete is None and orbite.animation is None):
            engins.orienter(pygame.key.get_pressed())
            pos = camera.screen_to_view(souris)
            engins.apercu(vue, camera.offset, pos[0] + camera.x, pos[1] + camera.y, hero, game_map,
                          inventaire.objet_selectionne)
        if (mode_pose(inventaire) and not craft.ouvert and not recherche.ouvert and not inventaire.contient(souris)
                and not stockage.contient(souris) and orbite.animation is None):
            pos = camera.screen_to_view(souris)
            objet = inventaire.objet_selectionne
            if est_outil(objet):
                # un vaisseau sous la souris est entouré (orange : on peut l'enlever), sinon la structure visée
                # (sur une planète, pas de vaisseau : ils restent dans l'espace)
                if orbite.planete is not None or not engins.apercu_enlever(
                        vue, camera.offset, pos[0] + camera.x, pos[1] + camera.y, moi):
                    dessiner_zone_deconstruction(vue, game_map, camera, pos,
                                                 hero.hitbox(hero.x, hero.y), local.coffres)
            else:
                dessiner_zone(vue, game_map, camera, pos, objet)
        pygame.transform.scale(vue, (largeur, hauteur), screen)

        # Interface : pas affectée par le zoom
        if orbite.planete is None:
            minimap.draw(screen, game_map, hero, aliens, vaisseaux, meteorites, trous_noirs)
        elif orbite.animation is None:
            cristaux.draw_interface(screen, camera, game_map, hero,
                                    libre=not (inventaire.ouvert or menu.ouvert or respawn.ouvert))
        local.energie.draw(screen)  # (sur une planète : l'énergie de ce qui est posé sur elle)
        oxygene.draw(screen)
        eau.draw(screen)
        faim.draw(screen)
        vie.draw(screen)
        engins.draw_hud(screen, moi)
        foreuses.draw_hud(screen)  # (« Pose-la sur un gisement de minerai »...)
        stockage.draw(screen, inventaire)
        inventaire.draw(screen)
        panneau_coffre.draw(screen, inventaire)
        craft.draw(screen, inventaire)
        recherche.draw(screen, inventaire)
        radio.draw(screen)
        panneau_telescope.draw(screen)
        orbite.draw(screen, libre=not (inventaire.ouvert or craft.ouvert or recherche.ouvert or radio.ouvert
                                       or grande_carte.ouvert or admin.ouvert
                                       or stockage.ouvert is not None or panneau_telescope.ouvert is not None))
        grande_carte.draw(screen, carte_espace)
        admin.draw(screen, inventaire, grande_carte)
        info_reseau.draw(screen, reseau, joueurs)  # adresse à donner, arrivées et départs
        menu.draw(screen)
        respawn.draw(screen)

        ecran.presenter()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:  # fermeture normale du jeu (pas une erreur : on garde les traces d'erreur)
        fermer_terminal_apres_delai()
        raise