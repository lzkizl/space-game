import json
import queue
import socket
import struct
import threading
import zlib

# =============================================
# ==== Transport : des messages (des dictionnaires) qui voyagent sur une connexion TCP.
# ====
# ==== Sur le fil, un message = <taille sur 4 octets><1 octet : compressé ou non><charge JSON>.
# ==== La taille en tête est indispensable : TCP est un flot d'octets, pas une suite de
# ==== messages — sans elle on ne saurait pas où l'un finit et où le suivant commence.
# ====
# ==== Chaque connexion a deux fils d'exécution (lecture et écriture) qui parlent à la boucle
# ==== de jeu par des files. Comme ça, pygame n'attend JAMAIS le réseau : au pire une image
# ==== arrive sans nouvelle du serveur.
# =============================================
ENTETE = struct.Struct("!IB")        # taille de la charge, puis 1 si elle est compressée
TAILLE_MAX = 64 * 1024 * 1024        # au-delà, on considère que la connexion dit n'importe quoi
SEUIL_COMPRESSION = 1024             # en dessous, compresser coûte plus que ça ne rapporte
PORT_DEFAUT = 50000


def encoder(message):
    """Un message (dictionnaire) -> les octets à envoyer."""
    charge = json.dumps(message, separators=(",", ":")).encode("utf-8")
    compresse = len(charge) > SEUIL_COMPRESSION
    if compresse:
        charge = zlib.compress(charge, 1)  # niveau 1 : rapide, largement suffisant ici
    return ENTETE.pack(len(charge), 1 if compresse else 0) + charge


def _lire_exactement(sock, nombre):
    """Lit exactement `nombre` octets (None si la connexion se ferme avant)."""
    morceaux = bytearray()
    while len(morceaux) < nombre:
        bloc = sock.recv(nombre - len(morceaux))
        if not bloc:
            return None
        morceaux += bloc
    return bytes(morceaux)


def decoder(sock):
    """Lit un message complet sur la socket (None si la connexion se ferme)."""
    entete = _lire_exactement(sock, ENTETE.size)
    if entete is None:
        return None
    taille, compresse = ENTETE.unpack(entete)
    if taille > TAILLE_MAX:
        raise ValueError(f"message de {taille} octets : connexion abandonnée")
    charge = _lire_exactement(sock, taille)
    if charge is None:
        return None
    if compresse:
        charge = zlib.decompress(charge)
    return json.loads(charge.decode("utf-8"))


class Connexion:
    """Une connexion ouverte. `envoyer` dépose un message, `messages` récupère ceux reçus.
    Ni l'un ni l'autre ne bloque : tout passe par des files, que deux fils d'exécution vident."""

    def __init__(self, sock, adresse):
        self.sock = sock
        self.adresse = adresse
        self.vivante = True
        self.erreur = ""
        self.octets_envoyes = 0   # pour mesurer le débit
        self.octets_recus = 0
        self._recues = queue.Queue()
        self._a_envoyer = queue.Queue()
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # pas d'attente de Nagle
        except OSError:
            pass
        self._lecteur = threading.Thread(target=self._boucle_lecture, daemon=True)
        self._ecrivain = threading.Thread(target=self._boucle_ecriture, daemon=True)
        self._lecteur.start()
        self._ecrivain.start()

    def _boucle_lecture(self):
        try:
            while self.vivante:
                message = decoder(self.sock)
                if message is None:
                    break  # l'autre bout a fermé proprement
                self._recues.put(message)
        except (OSError, ValueError, zlib.error, UnicodeDecodeError, json.JSONDecodeError) as erreur:
            self.erreur = self.erreur or str(erreur)
        finally:
            self.vivante = False
            self._a_envoyer.put(None)  # réveille l'écrivain pour qu'il s'arrête aussi

    def _boucle_ecriture(self):
        try:
            while True:
                message = self._a_envoyer.get()
                if message is None:
                    break
                octets = encoder(message)
                self.sock.sendall(octets)
                self.octets_envoyes += len(octets)
        except (OSError, ValueError) as erreur:
            self.erreur = self.erreur or str(erreur)
        finally:
            self.vivante = False
            try:
                self.sock.close()
            except OSError:
                pass

    def envoyer(self, message):
        if self.vivante:
            self._a_envoyer.put(message)

    def messages(self, maximum=2000):
        """Les messages arrivés depuis le dernier appel (au plus `maximum`, pour ne jamais
        bloquer une image trop longtemps)."""
        recus = []
        while len(recus) < maximum:
            try:
                recus.append(self._recues.get_nowait())
            except queue.Empty:
                break
        return recus

    def attendre(self, delai):
        """Attend un message au plus `delai` secondes (None s'il n'en vient aucun). Sert aux
        rares moments où l'on a le droit d'attendre : la poignée de main de l'arrivée."""
        try:
            return self._recues.get(timeout=delai)
        except queue.Empty:
            return None

    def fermer(self, immediat=False):
        """Ferme la connexion. Par défaut, on laisse d'abord partir ce qui est déjà en file :
        un refus, un « au revoir », un « l'hôte s'arrête » ne servent à rien s'ils sont perdus.
        C'est l'écrivain qui fermera la socket quand il aura fini (voir _boucle_ecriture).

        `immediat` coupe tout de suite, pour une connexion dont on n'attend plus rien.
        """
        morte = not self.vivante
        self.vivante = False       # plus personne n'ajoute de message après ça
        self._a_envoyer.put(None)  # ... et l'écrivain s'arrête une fois la file vidée
        if immediat or morte:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


class Salon:
    """La porte d'entrée de l'hôte : elle accepte les connexions dans son propre fil."""

    def __init__(self, port=PORT_DEFAUT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", port))
        self.sock.listen(16)
        self.sock.settimeout(0.5)  # pour que le fil puisse s'arrêter
        self.port = self.sock.getsockname()[1]
        self.ouvert = True
        self.erreur = ""
        self._nouvelles = queue.Queue()
        self._fil = threading.Thread(target=self._boucle_accueil, daemon=True)
        self._fil.start()

    def _boucle_accueil(self):
        while self.ouvert:
            try:
                sock, adresse = self.sock.accept()
            except socket.timeout:
                continue
            except OSError as erreur:
                if self.ouvert:
                    self.erreur = str(erreur)
                break
            self._nouvelles.put(Connexion(sock, adresse))

    def nouvelles(self):
        """Les connexions arrivées depuis le dernier appel."""
        arrivees = []
        while True:
            try:
                arrivees.append(self._nouvelles.get_nowait())
            except queue.Empty:
                return arrivees

    def fermer(self):
        self.ouvert = False
        try:
            self.sock.close()
        except OSError:
            pass
        for connexion in self.nouvelles():
            connexion.fermer()


def connecter(ip, port=PORT_DEFAUT, delai=8.0):
    """Ouvre une connexion vers un hôte. Lève OSError si ça ne répond pas."""
    sock = socket.create_connection((ip, port), timeout=delai)
    sock.settimeout(None)  # une fois connecté, les fils lisent en bloquant
    return Connexion(sock, (ip, port))


def adresse_locale():
    """L'adresse de cette machine sur le réseau local, celle à donner aux autres joueurs.

    On ouvre une socket UDP « vers » une adresse extérieure : rien n'est envoyé, mais le
    système choisit par quelle carte réseau il passerait, et donc quelle est notre adresse.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()
