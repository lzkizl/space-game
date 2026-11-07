import pygame

# =============================================
# ==== Style commun des menus (pause, menu principal)
# =============================================
COULEUR_PANNEAU = (15, 15, 25, 235)
COULEUR_BORDURE = (120, 120, 140)
COULEUR_TITRE = (255, 255, 255)
COULEUR_ACCENT = (130, 170, 255)
COULEUR_BOUTON = (30, 30, 50)
COULEUR_BOUTON_SURVOL = (55, 70, 130)
COULEUR_DANGER = (130, 40, 40)
COULEUR_DANGER_BORDURE = (255, 110, 110)
COULEUR_TEXTE = (235, 235, 245)
COULEUR_TEXTE_GRIS = (170, 170, 190)
COULEUR_ALERTE_TEXTE = (255, 110, 110)


def dessiner_panneau(screen, rect):
    fond = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(fond, COULEUR_PANNEAU, fond.get_rect(), border_radius=24)
    screen.blit(fond, rect)
    pygame.draw.rect(screen, COULEUR_BORDURE, rect, 3, border_radius=24)


JAUGE_LARGEUR = 220
JAUGE_HAUTEUR = 24
JAUGE_DECALAGE = 150  # le nom de la jauge est écrit à gauche, la barre commence ici


def dessiner_jauge(screen, police, pos, nom, valeur, maximum, couleur, alerte=0.2):
    """Jauge du HUD : le nom, puis une barre `couleur` remplie à valeur/maximum (le nom
    passe en rouge sous le seuil `alerte`)."""
    x, y = pos
    proportion = max(0.0, min(1.0, valeur / maximum))
    couleur_nom = COULEUR_ALERTE_TEXTE if proportion < alerte else (255, 255, 255)
    texte = police.render(nom, True, couleur_nom)
    screen.blit(texte, (x, y + (JAUGE_HAUTEUR - texte.get_height()) // 2))

    cadre = pygame.Rect(x + JAUGE_DECALAGE, y, JAUGE_LARGEUR, JAUGE_HAUTEUR)
    pygame.draw.rect(screen, (20, 20, 30), cadre, border_radius=6)
    if proportion > 0:
        rempli = pygame.Rect(cadre.x, cadre.y, max(6, round(cadre.w * proportion)), cadre.h)
        pygame.draw.rect(screen, couleur, rempli, border_radius=6)
    pygame.draw.rect(screen, (230, 230, 240), cadre, 2, border_radius=6)


def dessiner_infobulle(screen, police, texte, pos):
    """Petite bulle de texte près de la souris (reste dans l'écran)."""
    image = police.render(texte, True, COULEUR_TEXTE)
    bulle = image.get_rect().inflate(20, 12)
    bulle.topleft = (pos[0] + 16, pos[1] + 20)
    bulle.clamp_ip(screen.get_rect())
    fond = pygame.Surface(bulle.size, pygame.SRCALPHA)
    pygame.draw.rect(fond, (10, 10, 20, 240), fond.get_rect(), border_radius=8)
    screen.blit(fond, bulle)
    pygame.draw.rect(screen, COULEUR_ACCENT, bulle, 2, border_radius=8)
    screen.blit(image, image.get_rect(center=bulle.center))


def dessiner_bouton(screen, police, rect, texte, survol, danger=False):
    if danger:
        fond, bordure = COULEUR_DANGER, COULEUR_DANGER_BORDURE
    elif survol:
        fond, bordure = COULEUR_BOUTON_SURVOL, COULEUR_ACCENT
    else:
        fond, bordure = COULEUR_BOUTON, COULEUR_BORDURE
    pygame.draw.rect(screen, fond, rect, border_radius=14)
    pygame.draw.rect(screen, bordure, rect, 3, border_radius=14)
    image = police.render(texte, True, COULEUR_TEXTE)
    screen.blit(image, image.get_rect(center=rect.center))
