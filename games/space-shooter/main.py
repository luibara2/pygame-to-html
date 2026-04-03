

# ====== inlined: audio.py ======

import math
import random
from array import array
import pygame

def vytvor_ton(frekvence, delka_ms, hlasitost=0.4):
    vzorkovani = 44100
    pocet_vzorku = int(vzorkovani * delka_ms / 1000)
    amplituda = int(32767 * hlasitost)
    vzorky = array('h', (int(amplituda * math.sin(2 * math.pi * frekvence * i / vzorkovani)) for i in range(pocet_vzorku)))
    return pygame.mixer.Sound(buffer=vzorky.tobytes())

def vytvor_strela_zvuk():
    vzorkovani = 44100
    delka_ms = 120
    pocet_vzorku = int(vzorkovani * delka_ms / 1000)
    f_start = 1400
    f_end = 650
    vzorky = array('h')
    for i in range(pocet_vzorku):
        t = i / pocet_vzorku
        f = f_start + (f_end - f_start) * t
        obalka = (1.0 - t) ** 1.2
        hodnota = int(32767 * 0.45 * obalka * math.sin(2 * math.pi * f * (i / vzorkovani)))
        vzorky.append(hodnota)
    return pygame.mixer.Sound(buffer=vzorky.tobytes())

def vytvor_exploze_zvuk():
    vzorkovani = 44100
    delka_ms = 260
    pocet_vzorku = int(vzorkovani * delka_ms / 1000)
    vzorky = array('h')
    faze_a = 0.0
    faze_b = 0.0
    for i in range(pocet_vzorku):
        t = i / pocet_vzorku
        obalka_hlavni = (1.0 - t) ** 2.2
        obalka_click = max(0.0, 1.0 - t * 10.0)
        f_a = 260 - 190 * t
        f_b = 130 - 85 * t
        faze_a += 2 * math.pi * f_a / vzorkovani
        faze_b += 2 * math.pi * f_b / vzorkovani
        ton = math.sin(faze_a) * 0.36 + math.sin(faze_b) * 0.22
        sum_val = i / vzorkovani
        click = math.sin(2 * math.pi * 920 * sum_val) * obalka_click * 0.45
        sum_val = random.uniform(-1.0, 1.0) * obalka_hlavni * 0.75 + ton + click
        sum_val = max(-1.0, min(1.0, sum_val * 0.62))
        vzorky.append(int(sum_val * 32767))
    return pygame.mixer.Sound(buffer=vzorky.tobytes())

def init_sounds():
    """Create all game sounds. Returns dict name→Sound."""
    return {'strela': vytvor_strela_zvuk(), 'exploze': vytvor_exploze_zvuk(), 'hit': vytvor_ton(250, 130, 0.6), 'start': vytvor_ton(520, 160, 0.45), 'game_over': vytvor_ton(180, 520, 0.55)}

def safe_play(zvuk):
    if zvuk:
        zvuk.play()

# ====== inlined: config.py ======

import os
import pygame
ROZLISENI_X = 800
ROZLISENI_Y = 800
ROZLISENI = (ROZLISENI_X, ROZLISENI_Y)
FPS = 60
TARGET_DT = 1000.0 / 60.0
BARVA_OKOLI_HORNI = (4, 6, 18)
BARVA_OKOLI_DOLNI = (14, 18, 38)
BARVA_OKRAJ_PLAYFIELDU = (190, 220, 255)
BARVA_POZADI_HORNI = (5, 8, 25)
BARVA_POZADI_DOLNI = (35, 15, 55)
DEFAULTNI_BARVA_TEXTU = (255, 255, 255)
DEFAULTNI_BARVA_TLACITKA = (100, 100, 100)
BARVA_HVEZDA = (255, 255, 200)
BARVA_RAKETKA_TRUP = (200, 220, 255)
BARVA_RAKETKA_STIN = (70, 90, 140)
BARVA_RAKETKA_PLAMEN = (255, 180, 80)
BARVA_RAKETKA_PLAMEN_OUT = (255, 90, 40)
BARVA_STRELY = (0, 255, 255)
BARVA_STRELA_JADRO = (0, 255, 255)
BARVA_STRELA_GLOW = (0, 120, 255)
BARVA_TRAIL = (0, 200, 255)
METEOR_BARVA = (200, 100, 50)
BARVA_METEORIT_STIN = (40, 20, 10)
VELKY_METEORIT_BARVA = (255, 120, 120)
BARVA_EXPLOZE = (255, 200, 120)
BARVA_EXPLOZE_JADRO = (255, 80, 40)
ASTRONAUT_BARVA = (80, 200, 255)
POWERUP_BARVY = {'shield': (90, 220, 255), 'slow_time': (170, 120, 255), 'boost': (255, 190, 80)}
POWERUP_POPISKY = {'shield': 'S', 'slow_time': 'T', 'boost': 'B'}
BARVA_NABOJ = (255, 200, 60)
TMAVY_OVERLAY = (0, 0, 0, 25)
RAKETKA_SIRKA = 100
RAKETKA_VYSKA = 100
RAKETKA_RYCHLOST = 5
RAKETKA_RYCHLOST_BOOST = 8
SPAWN_SIDE_MARGIN = RAKETKA_SIRKA // 2
STRELA_SIRKA = 6
STRELA_VYSKA = 20
STRELA_RYCHLOST = 8
STRELA_INTERVAL_MS = 1000
STRELA_INTERVAL_BOOST_MS = 650
NABOJ_POTREBA = 5
NABOJ_SALVA_STRELY = 3
NABOJ_SALVA_ROZESTUP = 18
METEOR_INTERVAL_BASE_MIN_MS = 2000
METEOR_INTERVAL_BASE_MAX_MS = 3000
METEOR_RYCHLOST_ZAKLAD = 3
METEOR_DIFFICULTY_STEP_MS = 60000
METEOR_INTERVAL_ZRYCHLENI_ZA_KROK = 0.12
METEOR_INTERVAL_MIN_LIMIT_MS = 450
METEOR_MIN_VELIKOST = 48
METEOR_MAX_VELIKOST = 92
METEOR_MAX_POCET = 3
VELKY_METEORIT_SANCE = 0.1
VELKY_METEORIT_HP = 3
VELKY_METEORIT_MIN_VELIKOST = 124
VELKY_METEORIT_MAX_VELIKOST = 168
SCORE_SMALL_METEOR = 1
SCORE_BIG_METEOR = 5
ZTEZOVANI_ZACATEK_MS = 30000
ZTEZOVANI_PRIRUSTEK_ZA_SEC = 0.0001
ASTRONAUT_SIRKA = 50
ASTRONAUT_VYSKA = 62
ASTRONAUT_RYCHLOST = 2
POWERUP_INTERVAL_MIN_MS = 20000
POWERUP_INTERVAL_MAX_MS = 30000
POWERUP_VELIKOST = 38
POWERUP_RYCHLOST = 2
SHIELD_DURATION_MS = 10000
SLOW_TIME_DURATION_MS = 10000
BOOST_DURATION_MS = 10000
DEATH_ANIM_DURATION_MS = 1500
LEADERBOARD_PATH = 'leaderboard.jsonl'
LEADERBOARD_SHOW_LIMIT = 8
MAX_JMENO_DELKA = 12
ARCADE_ZNAKY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
ARCADE_JMENO_DELKA = 3
EXPLOSION_SPRITE_PATH = os.path.join('assets', 'explosion.png')
ASTRONAUT_ASSETS_DIR = os.path.join('assets', 'astronauts')
METEOR_ASSETS_DIR = os.path.join('assets', 'meteors')
BIG_METEOR_ASSETS_DIR = os.path.join('assets', 'big_meteors')
PLAY_BUTTON_RECT = pygame.Rect(ROZLISENI_X / 2 - 100, ROZLISENI_Y / 2 - 100, 200, 50)
LEADERBOARD_BUTTON_RECT = pygame.Rect(ROZLISENI_X / 2 - 100, ROZLISENI_Y / 2 - 25, 200, 50)
HOW_TO_PLAY_BUTTON_RECT = pygame.Rect(ROZLISENI_X / 2 - 100, ROZLISENI_Y / 2 + 50, 200, 50)
QUIT_BUTTON_RECT = pygame.Rect(ROZLISENI_X / 2 - 100, ROZLISENI_Y / 2 + 125, 200, 50)

# ====== inlined: rendering.py ======

import os
import math
import random
import pygame

class FontCache:
    """Caches pygame Font objects by (name, size, bold) to avoid re-creating
    them every frame."""

    def __init__(self):
        self._cache = {}

    def get(self, name='arial', size=20, bold=False):
        key = (name, size, bold)
        if key not in self._cache:
            self._cache[key] = pygame.font.SysFont(name, size, bold=bold)
        return self._cache[key]

def draw_text(surface, fonts, text, barva, x, y, velikost=20):
    font = fonts.get(size=velikost)
    image = font.render(text, True, barva)
    rect = image.get_rect(center=(x, y))
    surface.blit(image, rect)

def draw_text_topright(surface, fonts, text, barva, x, y, velikost=20):
    font = fonts.get(size=velikost)
    image = font.render(text, True, barva)
    rect = image.get_rect(topright=(x, y))
    surface.blit(image, rect)

def draw_text_glow(surface, fonts, text, color, x, y, velikost=20, offset=None):
    offset = offset or pygame.Vector2()
    font = fonts.get(size=velikost)
    image = font.render(text, True, color)
    shadow = font.render(text, True, (10, 10, 10))
    surface.blit(shadow, shadow.get_rect(center=(x + 1 - offset.x, y + 1 - offset.y)))
    surface.blit(image, image.get_rect(center=(x - offset.x, y - offset.y)))

def draw_text_topright_glow(surface, fonts, text, color, x, y, velikost=20, offset=None):
    offset = offset or pygame.Vector2()
    font = fonts.get(size=velikost)
    image = font.render(text, True, color)
    shadow = font.render(text, True, (10, 10, 10))
    surface.blit(shadow, shadow.get_rect(topright=(x + 1 - offset.x, y + 1 - offset.y)))
    surface.blit(image, image.get_rect(topright=(x - offset.x, y - offset.y)))

def draw_button(surface, fonts, x, y, width, height, barva_tlacitka, text_tlacitka, barva_textu_tlacitka, selected=False):
    rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, barva_tlacitka, rect)
    if selected:
        pygame.draw.rect(surface, (0, 255, 255), rect, width=3)
    draw_text(surface, fonts, text_tlacitka, barva_textu_tlacitka, x + width / 2, y + height / 2, velikost=20)

def uprav_barvu(barva, faktor):
    return tuple((max(0, min(255, int(kanal * faktor))) for kanal in barva))

def _vertical_gradient_surface(width, height, color_top, color_bottom):
    """Vertical RGB gradient without numpy/surfarray (blit_array is unreliable on wasm)."""
    strip = pygame.Surface((1, height))
    denom = max(height - 1, 1)
    for y in range(height):
        t = y / denom
        r = int(color_top[0] * (1 - t) + color_bottom[0] * t)
        g = int(color_top[1] * (1 - t) + color_bottom[1] * t)
        b = int(color_top[2] * (1 - t) + color_bottom[2] * t)
        strip.set_at((0, y), (r, g, b))
    if width == 1:
        return strip
    return pygame.transform.scale(strip, (width, height))


def vytvor_gradient_pozadi():
    return _vertical_gradient_surface(
        ROZLISENI_X, ROZLISENI_Y, BARVA_POZADI_HORNI, BARVA_POZADI_DOLNI
    )


def vytvor_okoli_surface(sirka, vyska):
    return _vertical_gradient_surface(sirka, vyska, BARVA_OKOLI_HORNI, BARVA_OKOLI_DOLNI)

def vykresli_nebulovy_layer():
    surf = pygame.Surface((ROZLISENI_X, ROZLISENI_Y), pygame.SRCALPHA)
    for _ in range(8):
        radius = random.randint(120, 260)
        center = (random.randint(-100, ROZLISENI_X + 100), random.randint(-100, ROZLISENI_Y + 100))
        color = random.choice([(40, 80, 200, 35), (80, 10, 160, 40), (20, 120, 200, 30)])
        pygame.draw.circle(surf, color, center, radius)
    return surf

def vytvor_overlay():
    surface = pygame.Surface((ROZLISENI_X, ROZLISENI_Y), pygame.SRCALPHA)
    surface.fill(TMAVY_OVERLAY)
    return surface

def vytvor_glow_surface(rozmer=64):
    surf = pygame.Surface((rozmer, rozmer), pygame.SRCALPHA)
    stred = rozmer // 2
    for r in range(stred, 0, -1):
        alpha = int(180 * (r / stred) ** 2)
        color = (0, 120, 255, alpha)
        pygame.draw.circle(surf, color, (stred, stred), r)
    return surf

def inicializuj_hvezdy(hvezdy, pocet=90):
    hvezdy.clear()
    for _ in range(pocet):
        hvezdy.append({'x': random.randint(0, ROZLISENI_X), 'y': random.randint(0, ROZLISENI_Y), 'velikost': random.choice([1, 2, 2, 3]), 'rychlost': random.uniform(0.5, 2.5)})

def vykresli_pozadi_animovane(surface, pozadi_surface, nebula_surface, hvezdy, camera_offset, dt_factor):
    ox, oy = (int(camera_offset.x), int(camera_offset.y))
    surface.blit(pozadi_surface, (-ox, -oy))
    if nebula_surface:
        surface.blit(nebula_surface, (-ox // 2, -oy // 2))
    for hvezda in hvezdy:
        hvezda['y'] += hvezda['rychlost'] * dt_factor
        if hvezda['y'] > ROZLISENI_Y:
            hvezda['y'] = -5
            hvezda['x'] = random.randint(0, ROZLISENI_X)
            hvezda['rychlost'] = random.uniform(0.5, 2.5)
        x = int(hvezda['x'] - ox * 0.3)
        y = int(hvezda['y'] - oy * 0.3)
        pygame.draw.circle(surface, BARVA_HVEZDA, (x, y), hvezda['velikost'])
        if hvezda['velikost'] >= 2:
            pygame.draw.circle(surface, (80, 140, 255), (x, y), hvezda['velikost'] + 1, width=1)

def vykresli_raketku(surface, raketka, offset):
    ox, oy = (int(offset.x), int(offset.y))
    trup = [(raketka.centerx - ox, raketka.y - 10 - oy), (raketka.left + 10 - ox, raketka.bottom - 10 - oy), (raketka.right - 10 - ox, raketka.bottom - 10 - oy)]
    pygame.draw.polygon(surface, BARVA_RAKETKA_STIN, trup, width=6)
    pygame.draw.polygon(surface, BARVA_RAKETKA_TRUP, trup)
    pygame.draw.circle(surface, (90, 150, 255), (raketka.centerx - ox, raketka.y + 25 - oy), 10)
    plamen_sirka = 24
    plamen_vyska = random.randint(24, 34)
    plamen = [(raketka.centerx - ox, raketka.bottom + plamen_vyska - oy), (raketka.centerx - plamen_sirka / 2 - ox, raketka.bottom - 8 - oy), (raketka.centerx + plamen_sirka / 2 - ox, raketka.bottom - 8 - oy)]
    pygame.draw.polygon(surface, BARVA_RAKETKA_PLAMEN_OUT, plamen)
    pygame.draw.polygon(surface, BARVA_RAKETKA_PLAMEN, plamen, width=2)

def vykresli_strelu(surface, strela_rect, offset):
    ox, oy = (int(offset.x), int(offset.y))
    rect = strela_rect.move(-ox, -oy)
    pygame.draw.rect(surface, BARVA_STRELA_GLOW, rect.inflate(4, 6), border_radius=3)
    pygame.draw.rect(surface, BARVA_STRELA_JADRO, rect, border_radius=2)

def vytvor_default_square_surface(sirka, vyska, barva):
    povrch = pygame.Surface((sirka, vyska), pygame.SRCALPHA)
    pygame.draw.rect(povrch, barva, (0, 0, sirka, vyska), border_radius=4)
    pygame.draw.rect(povrch, uprav_barvu(barva, 0.65), (0, 0, sirka, vyska), width=2, border_radius=4)
    return povrch

def vygeneruj_meteorit_surface(velikost, barva, design_id, je_velky):
    povrch = pygame.Surface((velikost, velikost), pygame.SRCALPHA)
    stred_x = velikost // 2
    stred_y = velikost // 2
    polomer = max(8, velikost // 2 - 2)
    seed = velikost * 73856093 + design_id * 19349663 + barva[0] * 83492791 + barva[1] * 297657976 + barva[2] * 15485863 + (1 if je_velky else 0) * 49979687
    rnd = random.Random(seed)
    tmava = uprav_barvu(barva, 0.52)
    stredni = uprav_barvu(barva, 0.82)
    svetla = uprav_barvu(barva, 1.18)
    if design_id == 0:
        body = []
        pocet_bodu = 18 if je_velky else 14
        for i in range(pocet_bodu):
            uhel = math.tau * i / pocet_bodu
            r = polomer * rnd.uniform(0.72, 1.0)
            body.append((stred_x + math.cos(uhel) * r, stred_y + math.sin(uhel) * r))
        pygame.draw.polygon(povrch, tmava, body)
        vnitrni = [(stred_x + (x - stred_x) * 0.9, stred_y + (y - stred_y) * 0.9) for x, y in body]
        pygame.draw.polygon(povrch, stredni, vnitrni)
    elif design_id == 1:
        pygame.draw.circle(povrch, tmava, (stred_x, stred_y), polomer)
        pygame.draw.circle(povrch, stredni, (stred_x, stred_y), int(polomer * 0.88))
        praskliny = 5 if je_velky else 3
        for _ in range(praskliny):
            uhel = rnd.uniform(0, math.tau)
            start_r = rnd.uniform(polomer * 0.18, polomer * 0.4)
            end_r = rnd.uniform(polomer * 0.65, polomer * 0.95)
            x1 = stred_x + math.cos(uhel) * start_r
            y1 = stred_y + math.sin(uhel) * start_r
            x2 = stred_x + math.cos(uhel + rnd.uniform(-0.35, 0.35)) * end_r
            y2 = stred_y + math.sin(uhel + rnd.uniform(-0.35, 0.35)) * end_r
            pygame.draw.line(povrch, tmava, (x1, y1), (x2, y2), width=max(1, velikost // 32))
    else:
        body = []
        pocet_bodu = 12 if je_velky else 9
        for i in range(pocet_bodu):
            uhel = math.tau * i / pocet_bodu
            nerovnost = 0.68 + 0.32 * abs(math.sin(i * 1.7))
            r = polomer * nerovnost * rnd.uniform(0.85, 1.05)
            body.append((stred_x + math.cos(uhel) * r, stred_y + math.sin(uhel) * r))
        pygame.draw.polygon(povrch, tmava, body)
        vnitrni = [(stred_x + (x - stred_x) * 0.84, stred_y + (y - stred_y) * 0.84) for x, y in body]
        pygame.draw.polygon(povrch, stredni, vnitrni)
        pruhy = 4 if je_velky else 3
        for _ in range(pruhy):
            y = int(stred_y + rnd.uniform(-polomer * 0.5, polomer * 0.5))
            pygame.draw.line(povrch, uprav_barvu(barva, rnd.uniform(0.9, 1.12)), (int(stred_x - polomer * 0.6), y), (int(stred_x + polomer * 0.6), y + rnd.randint(-2, 2)), width=max(1, velikost // 30))
    pocet_krateru = 10 if je_velky else 6
    min_krater = max(2, velikost // 18)
    max_krater = max(min_krater + 1, velikost // 9)
    for _ in range(pocet_krateru):
        uhel = rnd.uniform(0, math.tau)
        dist = rnd.uniform(0, polomer * 0.6)
        cx = stred_x + math.cos(uhel) * dist
        cy = stred_y + math.sin(uhel) * dist
        r = rnd.randint(min_krater, max_krater)
        pygame.draw.circle(povrch, uprav_barvu(barva, 0.45), (int(cx), int(cy)), r)
        pygame.draw.circle(povrch, uprav_barvu(barva, 0.7), (int(cx - r * 0.25), int(cy - r * 0.25)), max(1, int(r * 0.5)), width=1)
    for i in range(4):
        r = int(polomer * (0.68 - i * 0.12))
        if r <= 0:
            continue
        alpha = max(25, 120 - i * 24)
        pygame.draw.circle(povrch, (*svetla, alpha), (int(stred_x - polomer * 0.25), int(stred_y - polomer * 0.25)), r)
    return povrch

def ziskej_meteorit_surface(meteorit, meteor_surface_cache, meteor_sprite_pool, big_meteor_sprite_pool):
    velikost = meteorit['rect'].width
    sprite_idx = meteorit.get('sprite_idx')
    pool_typ = 'big' if meteorit['je_velky'] else 'normal'
    klic = ('meteor', pool_typ, velikost, meteorit['barva'], meteorit['je_velky'], sprite_idx)
    if klic not in meteor_surface_cache:
        pool = big_meteor_sprite_pool if meteorit['je_velky'] else meteor_sprite_pool
        sprite = None
        if sprite_idx is not None and 0 <= sprite_idx < len(pool):
            sprite = pygame.transform.smoothscale(pool[sprite_idx], (velikost, velikost))
        if sprite is None:
            sprite = vytvor_default_square_surface(velikost, velikost, meteorit['barva'])
        meteor_surface_cache[klic] = sprite
    return meteor_surface_cache[klic]

def ziskej_meteorit_mask(meteorit, meteor_mask_cache, meteor_surface_cache, meteor_sprite_pool, big_meteor_sprite_pool):
    velikost = meteorit['rect'].width
    sprite_idx = meteorit.get('sprite_idx')
    pool_typ = 'big' if meteorit['je_velky'] else 'normal'
    klic = ('meteor', pool_typ, velikost, meteorit['barva'], meteorit['je_velky'], sprite_idx)
    if klic not in meteor_mask_cache:
        surf = ziskej_meteorit_surface(meteorit, meteor_surface_cache, meteor_sprite_pool, big_meteor_sprite_pool)
        meteor_mask_cache[klic] = pygame.mask.from_surface(surf)
    return meteor_mask_cache[klic]

def ziskej_masku_rectu(sirka, vyska, rect_mask_cache):
    klic = (sirka, vyska)
    if klic not in rect_mask_cache:
        povrch = pygame.Surface((sirka, vyska), pygame.SRCALPHA)
        povrch.fill((255, 255, 255, 255))
        rect_mask_cache[klic] = pygame.mask.from_surface(povrch)
    return rect_mask_cache[klic]

def ma_meteorit_texturu(meteorit, meteor_sprite_pool, big_meteor_sprite_pool):
    pool = big_meteor_sprite_pool if meteorit['je_velky'] else meteor_sprite_pool
    sprite_idx = meteorit.get('sprite_idx')
    return sprite_idx is not None and 0 <= sprite_idx < len(pool)

def kolize_maska(rect_a, maska_a, rect_b, maska_b):
    if not rect_a.colliderect(rect_b):
        return False
    offset = (rect_b.x - rect_a.x, rect_b.y - rect_a.y)
    return maska_a.overlap(maska_b, offset) is not None

def ziskej_astronaut_surface(astronaut, astronaut_surface_cache, astronaut_sprite_pool):
    sirka = astronaut['rect'].width
    vyska = astronaut['rect'].height
    sprite_idx = astronaut.get('sprite_idx')
    klic = ('astronaut', sirka, vyska, sprite_idx)
    if klic not in astronaut_surface_cache:
        sprite = None
        if sprite_idx is not None and 0 <= sprite_idx < len(astronaut_sprite_pool):
            sprite = pygame.transform.smoothscale(astronaut_sprite_pool[sprite_idx], (sirka, vyska))
        if sprite is None:
            sprite = vytvor_default_square_surface(sirka, vyska, ASTRONAUT_BARVA)
        astronaut_surface_cache[klic] = sprite
    return astronaut_surface_cache[klic]

def vykresli_meteorit(surface, meteorit, offset, meteor_surface_cache, meteor_sprite_pool, big_meteor_sprite_pool):
    rect = meteorit['rect'].move(-int(offset.x), -int(offset.y))
    if not ma_meteorit_texturu(meteorit, meteor_sprite_pool, big_meteor_sprite_pool):
        polomer = rect.width // 2
        offset_px = 4 if meteorit['je_velky'] else 2
        pygame.draw.circle(surface, BARVA_METEORIT_STIN, (rect.centerx + offset_px, rect.centery + offset_px), polomer)
    surface.blit(ziskej_meteorit_surface(meteorit, meteor_surface_cache, meteor_sprite_pool, big_meteor_sprite_pool), rect)

def vykresli_powerup(surface, fonts, powerup, offset):
    rect = powerup['rect'].move(-int(offset.x), -int(offset.y))
    typ = powerup['typ']
    barva = POWERUP_BARVY.get(typ, (255, 255, 255))
    pygame.draw.circle(surface, uprav_barvu(barva, 0.45), rect.center, rect.width // 2 + 2)
    pygame.draw.circle(surface, barva, rect.center, rect.width // 2)
    pygame.draw.circle(surface, (255, 255, 255), rect.center, rect.width // 2, width=2)
    draw_text_glow(surface, fonts, POWERUP_POPISKY.get(typ, '?'), (15, 15, 20), rect.centerx, rect.centery + 1, velikost=22)

def vykresli_varovani(surface, fonts, meteority, astronauti, offset):
    ox = int(offset.x)
    varovani_y = 6
    trojuhelnik_vyska = 22
    trojuhelnik_sirka = 18
    font = fonts.get(size=14, bold=True)
    for meteorit in meteority:
        if meteorit['rect'].top < 0:
            cx = max(trojuhelnik_sirka, min(ROZLISENI_X - trojuhelnik_sirka, meteorit['rect'].centerx - ox))
            body = [(cx, varovani_y), (cx - trojuhelnik_sirka // 2, varovani_y + trojuhelnik_vyska), (cx + trojuhelnik_sirka // 2, varovani_y + trojuhelnik_vyska)]
            pygame.draw.polygon(surface, (255, 160, 30), body)
            pygame.draw.polygon(surface, (255, 200, 80), body, width=2)
            vykricnik = font.render('!', True, (30, 15, 0))
            surface.blit(vykricnik, vykricnik.get_rect(center=(cx, varovani_y + trojuhelnik_vyska // 2 + 2)))
    for astronaut in astronauti:
        if astronaut['rect'].top < 0:
            cx = max(trojuhelnik_sirka, min(ROZLISENI_X - trojuhelnik_sirka, astronaut['rect'].centerx - ox))
            body = [(cx, varovani_y), (cx - trojuhelnik_sirka // 2, varovani_y + trojuhelnik_vyska), (cx + trojuhelnik_sirka // 2, varovani_y + trojuhelnik_vyska)]
            pygame.draw.polygon(surface, (60, 160, 255), body)
            pygame.draw.polygon(surface, (120, 200, 255), body, width=2)
            vykricnik = font.render('!', True, (0, 10, 40))
            surface.blit(vykricnik, vykricnik.get_rect(center=(cx, varovani_y + trojuhelnik_vyska // 2 + 2)))

def emit_particles(particles, position, count, speed_min, speed_max, size_min, size_max, color, life_ms=420):
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(speed_min, speed_max)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        particles.append({'pos': pygame.Vector2(position), 'vel': pygame.Vector2(vx, vy), 'life': life_ms, 'max_life': life_ms, 'size': random.uniform(size_min, size_max), 'color': color})

def emit_explosion(particles, position, velky=False):
    count = 36 if velky else 22
    emit_particles(particles, position, count, 0.6, 2.6 if velky else 2.0, 2.5, 6 if velky else 4.5, BARVA_EXPLOZE, life_ms=520)
    emit_particles(particles, position, count // 2, 0.4, 1.8, 2, 3, BARVA_EXPLOZE_JADRO, life_ms=360)

def emit_trail(particles, strela_rect):
    center = (strela_rect.centerx, strela_rect.bottom)
    emit_particles(particles, center, 2, 0.1, 0.3, 1.5, 2.5, BARVA_TRAIL, life_ms=240)

def emit_muzzle_flash(particles, raketka):
    pos = (raketka.centerx, raketka.top - 6)
    emit_particles(particles, pos, 8, 0.3, 1.2, 2, 3.5, (255, 240, 180), life_ms=220)

def emit_burn_plume(particles, raketka):
    pos = (raketka.centerx, raketka.bottom)
    emit_particles(particles, pos, 4, 0.1, 0.35, 2, 3, (255, 140, 80), life_ms=240)

def update_and_draw_particles(surface, particles, delta_ms, offset, dt_factor):
    ox, oy = (offset.x, offset.y)
    alive = []
    for p in particles:
        p['life'] -= delta_ms
        if p['life'] <= 0:
            continue
        p['pos'] += p['vel'] * dt_factor
        fade = max(0.1, p['life'] / p['max_life'])
        size = max(1.0, p['size'] * fade)
        alpha = int(220 * fade)
        col = (*p['color'], alpha)
        pygame.draw.circle(surface, col, (int(p['pos'].x - ox), int(p['pos'].y - oy)), int(size))
        alive.append(p)
    particles[:] = alive

def limit_particles(particles, max_count=900):
    if len(particles) > max_count:
        del particles[:len(particles) - max_count]

def trigger_shake(state, intenzita=6, duration_ms=260):
    state.shake_time_ms = max(state.shake_time_ms, duration_ms)
    state.shake_intenzita = max(state.shake_intenzita, intenzita)

def update_shake(state, delta_ms):
    if state.shake_time_ms <= 0:
        state.camera_offset.update(0, 0)
        return
    state.shake_time_ms -= delta_ms
    decay = max(0.1, state.shake_time_ms / 260)
    intensity = state.shake_intenzita * decay
    state.camera_offset.x = random.uniform(-intensity, intensity)
    state.camera_offset.y = random.uniform(-intensity, intensity)
    if state.shake_time_ms <= 0:
        state.camera_offset.update(0, 0)

def nacti_obrazek_cesta(path):
    if not os.path.exists(path):
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except pygame.error:
        return None

def nacti_obrazky_ze_slozky(folder_path):
    if not os.path.isdir(folder_path):
        return []
    validni_pripony = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
    obrazky = []
    try:
        for nazev in sorted(os.listdir(folder_path)):
            _, pripona = os.path.splitext(nazev.lower())
            if pripona not in validni_pripony:
                continue
            obrazek = nacti_obrazek_cesta(os.path.join(folder_path, nazev))
            if obrazek:
                obrazky.append(obrazek)
    except OSError:
        return []
    return obrazky

def init_sprite_assets():
    return {'astronaut': nacti_obrazky_ze_slozky(ASTRONAUT_ASSETS_DIR), 'meteor': nacti_obrazky_ze_slozky(METEOR_ASSETS_DIR), 'big_meteor': nacti_obrazky_ze_slozky(BIG_METEOR_ASSETS_DIR)}

def ziskej_nahodny_sprite_index(pool):
    if not pool:
        return None
    return random.randrange(len(pool))

def init_explosion_frames():
    frames = []
    sprite = nacti_obrazek_cesta(EXPLOSION_SPRITE_PATH)
    if sprite:
        frame_size = sprite.get_height()
        cols = sprite.get_width() // frame_size
        for i in range(cols):
            rect = pygame.Rect(i * frame_size, 0, frame_size, frame_size)
            frame = sprite.subsurface(rect)
            frames.append(frame)
    if not frames:
        for radius in range(12, 46, 6):
            surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*BARVA_EXPLOZE_JADRO, 220), (radius, radius), max(2, radius // 3))
            pygame.draw.circle(surf, (*BARVA_EXPLOZE, 160), (radius, radius), radius)
            pygame.draw.circle(surf, (255, 255, 255, 90), (radius, radius), max(1, radius // 4))
            frames.append(surf)
    return frames

# ====== inlined: state.py ======

import pygame
import random

class GameState:
    """All mutable per-game state, replacing the ~50 former globals."""

    def __init__(self):
        self.screen = 'main_menu'
        self.main_menu_selected = 0
        self.pause_menu_selected = 0
        self.game_over_selected = 0
        self.raketka = pygame.Rect(ROZLISENI_X / 2 - RAKETKA_SIRKA / 2, ROZLISENI_Y - RAKETKA_VYSKA, RAKETKA_SIRKA, RAKETKA_VYSKA)
        self.zivoty = 3
        self.score = 0
        self.dying_timer_ms = 0
        self.dying_type = None
        self.dying_position = (0, 0)
        self.strely = []
        self.meteority = []
        self.astronauti = []
        self.powerupy = []
        self.particles = []
        self.hvezdy = []
        self.cas_posledni_strely = 0
        self.cas_posledni_meteoritu = 0
        self.cas_posledni_astronauta = 0
        self.cas_posledni_powerupu = 0
        self.meteor_interval_ms = random.randint(METEOR_INTERVAL_BASE_MIN_MS, METEOR_INTERVAL_BASE_MAX_MS)
        self.astronaut_interval_ms = random.randint(7000, 11000)
        self.powerup_interval_ms = random.randint(POWERUP_INTERVAL_MIN_MS, POWERUP_INTERVAL_MAX_MS)
        self.naboj_pocitadlo = 0
        self.naboj_pripraveny = False
        self.hra_zacatek_cas = 0
        self.pozastaveno_celkove_ms = 0
        self.pause_start_time = None
        self.cekani_na_prvni_pohyb = False
        self.shield_end_ms = 0
        self.slow_time_end_ms = 0
        self.boost_end_ms = 0
        self.zadani_jmena = False
        self.arcade_jmeno_index = 0
        self.arcade_jmeno_znaky = [ARCADE_ZNAKY[0]] * ARCADE_JMENO_DELKA
        self.zadane_jmeno = ''.join(self.arcade_jmeno_znaky)
        self.zaznam_ulozen = False
        self.konecny_cas_s = 0.0
        self.camera_offset = pygame.Vector2(0, 0)
        self.shake_time_ms = 0
        self.shake_intenzita = 0.0
        self.leaderboard_cache = []
        self.autoplay_enabled = False
        self.cheat_progress = 0
        self.cheat_last_key_ms = 0
        self.leaderboard_back_rect = None
        self.how_to_play_back_rect = None
        self.name_confirm_rect = None
        self.name_skip_rect = None

    def reset_game(self, sounds, safe_play_fn):
        """Reset state for a new game round."""
        self.screen = 'game'
        self.main_menu_selected = 0
        self.pause_menu_selected = 0
        self.game_over_selected = 0
        self.cekani_na_prvni_pohyb = True
        self.strely.clear()
        self.meteority.clear()
        self.astronauti.clear()
        self.powerupy.clear()
        self.particles.clear()
        now = pygame.time.get_ticks()
        self.cas_posledni_strely = now
        self.cas_posledni_meteoritu = now
        self.cas_posledni_astronauta = now
        self.cas_posledni_powerupu = now
        self.meteor_interval_ms = random.randint(METEOR_INTERVAL_BASE_MIN_MS, METEOR_INTERVAL_BASE_MAX_MS)
        self.astronaut_interval_ms = random.randint(7000, 11000)
        self.powerup_interval_ms = random.randint(POWERUP_INTERVAL_MIN_MS, POWERUP_INTERVAL_MAX_MS)
        self.shield_end_ms = 0
        self.slow_time_end_ms = 0
        self.boost_end_ms = 0
        self.naboj_pocitadlo = 0
        self.naboj_pripraveny = False
        self.score = 0
        self.hra_zacatek_cas = now
        self.pozastaveno_celkove_ms = 0
        self.pause_start_time = None
        self.zivoty = 3
        self.zadani_jmena = False
        self.arcade_jmeno_index = 0
        self.arcade_jmeno_znaky = [ARCADE_ZNAKY[0]] * ARCADE_JMENO_DELKA
        self.zadane_jmeno = ''.join(self.arcade_jmeno_znaky)
        self.zaznam_ulozen = False
        self.konecny_cas_s = 0.0
        self.dying_timer_ms = 0
        self.dying_type = None
        self.dying_position = (0, 0)
        self.camera_offset.update(0, 0)
        self.shake_time_ms = 0
        self.shake_intenzita = 0.0
        self.autoplay_enabled = False
        self.cheat_progress = 0
        self.cheat_last_key_ms = 0
        self.raketka = pygame.Rect(ROZLISENI_X / 2 - RAKETKA_SIRKA / 2, ROZLISENI_Y - RAKETKA_VYSKA, RAKETKA_SIRKA, RAKETKA_VYSKA)
        safe_play_fn(sounds.get('start'))

    def aktualni_herni_cas_s(self):
        return max(0.0, (pygame.time.get_ticks() - self.hra_zacatek_cas - self.pozastaveno_celkove_ms) / 1000)

    def posun_powerup_timingy(self, o_kolik_ms):
        if o_kolik_ms <= 0:
            return
        if self.shield_end_ms > 0:
            self.shield_end_ms += o_kolik_ms
        if self.slow_time_end_ms > 0:
            self.slow_time_end_ms += o_kolik_ms
        if self.boost_end_ms > 0:
            self.boost_end_ms += o_kolik_ms

# ====== inlined: game.py ======

import os
import sys
import json
import math
import random
import ctypes
import pygame

class Game:
    """Main game class: owns loop, events, update, and render."""
    CHEAT_SEQUENCE = (pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_f, pygame.K_g, pygame.K_h, pygame.K_j, pygame.K_k, pygame.K_l)
    CHEAT_MAX_DELAY_MS = 1000

    def __init__(self):
        self.okno = pygame.Surface(ROZLISENI)
        self.display_surface = None
        self.viewport_rect = pygame.Rect(0, 0, ROZLISENI_X, ROZLISENI_Y)
        self.je_fullscreen = False
        self.okoli_surface = None
        self.set_display_mode(False)
        self.clock = pygame.time.Clock()
        self.fonts = FontCache()
        self.sounds = init_sounds()
        sprite_assets = init_sprite_assets()
        self.astronaut_sprite_pool = sprite_assets['astronaut']
        self.meteor_sprite_pool = sprite_assets['meteor']
        self.big_meteor_sprite_pool = sprite_assets['big_meteor']
        self.explosion_frames = init_explosion_frames()
        self.glow_surface = vytvor_glow_surface()
        self.pozadi_surface = vytvor_gradient_pozadi()
        self.nebula_surface = vykresli_nebulovy_layer()
        self.overlay_surface = vytvor_overlay()
        self.meteor_surface_cache = {}
        self.astronaut_surface_cache = {}
        self.meteor_mask_cache = {}
        self.rect_mask_cache = {}
        self.state = GameState()
        self.running = True
        inicializuj_hvezdy(self.state.hvezdy)
        self.refresh_leaderboard()

    def _nastav_pozici_okna_top_center(self, pos_x):
        if sys.platform != 'win32':
            return
        try:
            info = pygame.display.get_wm_info()
            hwnd = info.get('window')
            if not hwnd:
                return
            SWP_NOSIZE = 1
            SWP_NOZORDER = 4
            ctypes.windll.user32.SetWindowPos(hwnd, 0, int(pos_x), 0, 0, 0, SWP_NOSIZE | SWP_NOZORDER)
        except Exception:
            return

    def set_display_mode(self, fullscreen):
        self.je_fullscreen = fullscreen
        is_wasm = sys.platform == 'emscripten'
        if fullscreen:
            if is_wasm:
                self.display_surface = pygame.display.set_mode(ROZLISENI)
            else:
                self.display_surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        elif is_wasm:
            self.display_surface = pygame.display.set_mode(ROZLISENI)
        else:
            desktop_sizes = pygame.display.get_desktop_sizes()
            if desktop_sizes:
                desktop_w, _ = desktop_sizes[0]
                pos_x = max(0, (desktop_w - ROZLISENI_X) // 2)
            else:
                pos_x = 0
            os.environ['SDL_VIDEO_CENTERED'] = '0'
            os.environ['SDL_VIDEO_WINDOW_POS'] = f'{pos_x},0'
            self.display_surface = pygame.display.set_mode(ROZLISENI, pygame.NOFRAME)
            self._nastav_pozici_okna_top_center(pos_x)
        pygame.display.set_caption('Vesmírná střílečka')
        sirka, vyska = self.display_surface.get_size()
        scale = min(sirka / ROZLISENI_X, vyska / ROZLISENI_Y)
        viewport_w = max(1, int(ROZLISENI_X * scale))
        viewport_h = max(1, int(ROZLISENI_Y * scale))
        self.viewport_rect = pygame.Rect((sirka - viewport_w) // 2, (vyska - viewport_h) // 2, viewport_w, viewport_h)
        self.okoli_surface = vytvor_okoli_surface(sirka, vyska)

    def preved_pozici_mysi(self, pozice):
        if not self.viewport_rect.collidepoint(pozice):
            return None
        rel_x = (pozice[0] - self.viewport_rect.x) / self.viewport_rect.width
        rel_y = (pozice[1] - self.viewport_rect.y) / self.viewport_rect.height
        return (int(rel_x * ROZLISENI_X), int(rel_y * ROZLISENI_Y))

    def present_frame(self):
        if self.je_fullscreen and self.okoli_surface is not None:
            self.display_surface.blit(self.okoli_surface, (0, 0))
        else:
            self.display_surface.fill((0, 0, 0))
        if self.viewport_rect.size == (ROZLISENI_X, ROZLISENI_Y):
            self.display_surface.blit(self.okno, self.viewport_rect.topleft)
        else:
            scaled = pygame.transform.scale(self.okno, self.viewport_rect.size)
            self.display_surface.blit(scaled, self.viewport_rect.topleft)
        pygame.draw.rect(self.display_surface, BARVA_OKRAJ_PLAYFIELDU, self.viewport_rect, width=3)
        pygame.display.update()

    def load_leaderboard(self):
        if not os.path.exists(LEADERBOARD_PATH):
            return []
        zaznamy = []
        try:
            with open(LEADERBOARD_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(data, dict):
                        continue
                    zaznamy.append(data)
        except OSError:
            return []
        return zaznamy

    def refresh_leaderboard(self):
        zaznamy = self.load_leaderboard()
        self.state.leaderboard_cache = sorted(zaznamy, key=lambda z: (-z.get('score', z.get('meteors', 0)), -z.get('time_s', 0.0)))

    def append_score_record(self, name, score, time_s):
        os.makedirs(os.path.dirname(LEADERBOARD_PATH) or '.', exist_ok=True)
        zaznam = {'name': name, 'score': score, 'time_s': round(time_s, 1), 'timestamp': int(pygame.time.get_ticks())}
        try:
            with open(LEADERBOARD_PATH, 'a', encoding='utf-8') as f:
                f.write(json.dumps(zaznam, ensure_ascii=True) + '\n')
        except OSError:
            return

    def posun_arcade_pozici(self, krok):
        s = self.state
        s.arcade_jmeno_index = (s.arcade_jmeno_index + krok) % ARCADE_JMENO_DELKA

    def zmen_arcade_znak(self, krok):
        s = self.state
        aktualni_znak = s.arcade_jmeno_znaky[s.arcade_jmeno_index]
        znak_index = ARCADE_ZNAKY.find(aktualni_znak)
        if znak_index < 0:
            znak_index = 0
        novy_index = (znak_index + krok) % len(ARCADE_ZNAKY)
        s.arcade_jmeno_znaky[s.arcade_jmeno_index] = ARCADE_ZNAKY[novy_index]
        s.zadane_jmeno = ''.join(s.arcade_jmeno_znaky)

    def uloz_skore_pokud_validni(self):
        s = self.state
        jmeno = s.zadane_jmeno.strip()
        if not jmeno or s.zaznam_ulozen:
            return False
        self.append_score_record(jmeno, s.score, s.konecny_cas_s)
        self.refresh_leaderboard()
        s.zaznam_ulozen = True
        s.zadani_jmena = False
        return True

    def preskoc_ulozeni(self):
        self.state.zadani_jmena = False

    @staticmethod
    def ziskej_koeficient_ztezovani(odehrane_ms):
        if odehrane_ms <= ZTEZOVANI_ZACATEK_MS:
            return 1.0
        dodatecne_sekundy = (odehrane_ms - ZTEZOVANI_ZACATEK_MS) / 1000
        return 1.0 + dodatecne_sekundy * ZTEZOVANI_PRIRUSTEK_ZA_SEC

    @staticmethod
    def ziskej_meteor_spawn_parametry(odehrane_ms):
        stupne_obtiznosti = max(0, int(odehrane_ms // METEOR_DIFFICULTY_STEP_MS))
        interval_koeficient = max(0.25, 1.0 - stupne_obtiznosti * METEOR_INTERVAL_ZRYCHLENI_ZA_KROK)
        min_interval = max(METEOR_INTERVAL_MIN_LIMIT_MS, int(METEOR_INTERVAL_BASE_MIN_MS * interval_koeficient))
        max_interval = max(min_interval + 100, int(METEOR_INTERVAL_BASE_MAX_MS * interval_koeficient))
        max_pocet = METEOR_MAX_POCET + stupne_obtiznosti
        return (min_interval, max_interval, max_pocet)

    def nahodna_spawn_x(self, velikost_objektu):
        min_x = SPAWN_SIDE_MARGIN
        max_x = ROZLISENI_X - velikost_objektu - SPAWN_SIDE_MARGIN
        if max_x < min_x:
            return max(0, (ROZLISENI_X - velikost_objektu) // 2)
        return random.randint(min_x, max_x)

    def najdi_bezpecnou_pozici_x_astronauta(self):
        s = self.state
        min_x = SPAWN_SIDE_MARGIN
        max_x = ROZLISENI_X - ASTRONAUT_SIRKA - SPAWN_SIDE_MARGIN
        if max_x < min_x:
            return None
        blokovane = [False] * (max_x + 1)
        for strela in s.strely:
            x_min = max(0, int(math.floor(strela.centerx - ASTRONAUT_SIRKA)))
            x_max = min(max_x, int(math.ceil(strela.centerx)))
            for x in range(x_min, x_max + 1):
                blokovane[x] = True
        bezpecne = [x for x in range(min_x, max_x + 1) if not blokovane[x]]
        if not bezpecne:
            return None
        return random.choice(bezpecne)

    def najdi_bezpecnou_pozici_x_meteoritu(self, velikost_objektu):
        s = self.state
        min_x = SPAWN_SIDE_MARGIN
        max_x = ROZLISENI_X - velikost_objektu - SPAWN_SIDE_MARGIN
        if max_x < min_x:
            return None
        blokovane = [False] * (max_x + 1)
        for astronaut in s.astronauti:
            a_left = astronaut['rect'].left
            a_right = astronaut['rect'].right
            x_min = max(min_x, int(math.floor(a_left - velikost_objektu + 1)))
            x_max = min(max_x, int(math.ceil(a_right - 1)))
            if x_min > x_max:
                continue
            for x in range(x_min, x_max + 1):
                blokovane[x] = True
        bezpecne = [x for x in range(min_x, max_x + 1) if not blokovane[x]]
        if not bezpecne:
            return None
        return random.choice(bezpecne)

    def spawn_powerup(self, aktualni_cas):
        s = self.state
        typ = random.choice(['shield', 'slow_time', 'boost'])
        x = self.nahodna_spawn_x(POWERUP_VELIKOST)
        s.powerupy.append({'rect': pygame.Rect(x, -POWERUP_VELIKOST, POWERUP_VELIKOST, POWERUP_VELIKOST), 'y': float(-POWERUP_VELIKOST), 'typ': typ})
        s.cas_posledni_powerupu = aktualni_cas
        s.powerup_interval_ms = random.randint(POWERUP_INTERVAL_MIN_MS, POWERUP_INTERVAL_MAX_MS)

    @staticmethod
    def aktivuj_powerup(state, typ, aktualni_cas):
        if typ == 'shield':
            state.shield_end_ms = aktualni_cas + SHIELD_DURATION_MS
        elif typ == 'slow_time':
            state.slow_time_end_ms = aktualni_cas + SLOW_TIME_DURATION_MS
        elif typ == 'boost':
            state.boost_end_ms = aktualni_cas + BOOST_DURATION_MS

    @staticmethod
    def zbyvajici_sekundy(aktualni_cas, konec_ms):
        return max(0.0, (konec_ms - aktualni_cas) / 1000)

    def trigger_dying(self, dying_type):
        """Begin death animation. World continues, ship disappears."""
        s = self.state
        if s.screen == 'dying':
            return
        s.screen = 'dying'
        s.dying_type = dying_type
        s.dying_timer_ms = DEATH_ANIM_DURATION_MS
        s.dying_position = (s.raketka.centerx, s.raketka.centery)
        s.konecny_cas_s = s.aktualni_herni_cas_s()
        safe_play(self.sounds.get('game_over'))
        if dying_type == 'meteor':
            emit_explosion(s.particles, s.dying_position, velky=True)
            emit_particles(s.particles, s.dying_position, 50, 0.8, 3.0, 3.0, 7.0, (255, 200, 120), life_ms=800)
            emit_particles(s.particles, s.dying_position, 20, 0.5, 2.0, 4.0, 8.0, (200, 200, 200), life_ms=800)
            trigger_shake(s, intenzita=12, duration_ms=500)
        else:
            emit_particles(s.particles, s.dying_position, 30, 0.6, 2.4, 2.5, 6.0, (255, 60, 60), life_ms=700)
            emit_particles(s.particles, s.dying_position, 15, 0.4, 1.8, 2.0, 4.0, (255, 120, 80), life_ms=500)
            trigger_shake(s, intenzita=8, duration_ms=400)

    def trigger_game_over_state(self):
        """Finalize into game-over screen (called after dying animation)."""
        s = self.state
        s.screen = 'game_over'
        s.zadani_jmena = True
        s.arcade_jmeno_index = 0
        s.arcade_jmeno_znaky = [ARCADE_ZNAKY[0]] * ARCADE_JMENO_DELKA
        s.zadane_jmeno = ''.join(s.arcade_jmeno_znaky)
        s.zaznam_ulozen = False

    def go_to_main_menu(self):
        s = self.state
        s.screen = 'main_menu'
        s.strely.clear()
        s.meteority.clear()
        s.powerupy.clear()
        s.autoplay_enabled = False
        self.reset_cheat_progress()
        now = pygame.time.get_ticks()
        s.cas_posledni_strely = now
        s.cas_posledni_meteoritu = now

    async def run(self):
        # CPython wasm / pygbag: must yield every frame or the browser never paints SDL.
        while self.running:
            self.handle_events()
            delta_ms = self.clock.tick(FPS)
            dt_factor = delta_ms / TARGET_DT
            self.update(delta_ms, dt_factor)
            self.render(delta_ms, dt_factor)
            self.present_frame()
            await asyncio.sleep(0)
        pygame.quit()

    def handle_events(self):
        s = self.state
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.set_display_mode(not self.je_fullscreen)
                    continue
                if s.screen in ('game', 'paused'):
                    self.process_cheat_key(event.key, pygame.time.get_ticks())
                else:
                    self.reset_cheat_progress()
                if s.screen == 'game_over' and s.zadani_jmena:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.uloz_skore_pokud_validni()
                    elif event.key == pygame.K_ESCAPE:
                        self.preskoc_ulozeni()
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        self.posun_arcade_pozici(-1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.posun_arcade_pozici(1)
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.zmen_arcade_znak(-1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.zmen_arcade_znak(1)
                elif s.screen == 'main_menu':
                    if event.key in (pygame.K_UP, pygame.K_w):
                        s.main_menu_selected = (s.main_menu_selected - 1) % 4
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        s.main_menu_selected = (s.main_menu_selected + 1) % 4
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if s.main_menu_selected == 0:
                            s.reset_game(self.sounds, safe_play)
                            inicializuj_hvezdy(s.hvezdy)
                        elif s.main_menu_selected == 1:
                            s.screen = 'leaderboard'
                        elif s.main_menu_selected == 2:
                            s.screen = 'how_to_play'
                        elif s.main_menu_selected == 3:
                            self.running = False
                elif s.screen == 'paused':
                    if event.key in (pygame.K_UP, pygame.K_w):
                        s.pause_menu_selected = (s.pause_menu_selected - 1) % 2
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        s.pause_menu_selected = (s.pause_menu_selected + 1) % 2
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if s.pause_menu_selected == 0:
                            self._resume_game()
                        else:
                            self.go_to_main_menu()
                elif s.screen == 'game_over' and (not s.zadani_jmena):
                    if event.key in (pygame.K_UP, pygame.K_w):
                        s.game_over_selected = (s.game_over_selected - 1) % 2
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        s.game_over_selected = (s.game_over_selected + 1) % 2
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if s.game_over_selected == 0:
                            s.reset_game(self.sounds, safe_play)
                            inicializuj_hvezdy(s.hvezdy)
                        else:
                            self.go_to_main_menu()
                elif s.screen == 'leaderboard':
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        s.screen = 'main_menu'
                elif s.screen == 'how_to_play':
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        s.screen = 'main_menu'
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                herni_pozice = self.preved_pozici_mysi(event.pos)
                if herni_pozice is None:
                    continue
                if s.screen == 'game_over' and s.zadani_jmena:
                    if s.name_confirm_rect and s.name_confirm_rect.collidepoint(herni_pozice):
                        self.uloz_skore_pokud_validni()
                    elif s.name_skip_rect and s.name_skip_rect.collidepoint(herni_pozice):
                        self.preskoc_ulozeni()
                    continue
                if s.screen == 'main_menu':
                    if PLAY_BUTTON_RECT.collidepoint(herni_pozice):
                        s.main_menu_selected = 0
                        s.reset_game(self.sounds, safe_play)
                        inicializuj_hvezdy(s.hvezdy)
                    if LEADERBOARD_BUTTON_RECT.collidepoint(herni_pozice):
                        s.main_menu_selected = 1
                        s.screen = 'leaderboard'
                    if HOW_TO_PLAY_BUTTON_RECT.collidepoint(herni_pozice):
                        s.main_menu_selected = 2
                        s.screen = 'how_to_play'
                    if QUIT_BUTTON_RECT.collidepoint(herni_pozice):
                        s.main_menu_selected = 3
                        self.running = False
                if s.screen == 'leaderboard':
                    if s.leaderboard_back_rect and s.leaderboard_back_rect.collidepoint(herni_pozice):
                        s.screen = 'main_menu'
                if s.screen == 'how_to_play':
                    if s.how_to_play_back_rect and s.how_to_play_back_rect.collidepoint(herni_pozice):
                        s.screen = 'main_menu'
                if s.screen == 'paused':
                    if PLAY_BUTTON_RECT.collidepoint(herni_pozice):
                        s.pause_menu_selected = 0
                        self._resume_game()
                    if QUIT_BUTTON_RECT.collidepoint(herni_pozice):
                        s.pause_menu_selected = 1
                        self.go_to_main_menu()
                if s.screen == 'game_over':
                    if s.zadani_jmena and (not s.zaznam_ulozen):
                        continue
                    if PLAY_BUTTON_RECT.collidepoint(herni_pozice):
                        s.game_over_selected = 0
                        s.reset_game(self.sounds, safe_play)
                        inicializuj_hvezdy(s.hvezdy)
                    if QUIT_BUTTON_RECT.collidepoint(herni_pozice):
                        s.game_over_selected = 1
                        self.go_to_main_menu()

    def _resume_game(self):
        s = self.state
        if s.pause_start_time is not None:
            pause_delta = pygame.time.get_ticks() - s.pause_start_time
            s.pozastaveno_celkove_ms += pause_delta
            s.posun_powerup_timingy(pause_delta)
            s.pause_start_time = None
        s.screen = 'game'

    def reset_cheat_progress(self):
        s = self.state
        s.cheat_progress = 0
        s.cheat_last_key_ms = 0

    def process_cheat_key(self, key, aktualni_cas):
        s = self.state
        if s.cheat_progress > 0 and aktualni_cas - s.cheat_last_key_ms > self.CHEAT_MAX_DELAY_MS:
            self.reset_cheat_progress()
        expected_key = self.CHEAT_SEQUENCE[s.cheat_progress]
        if key == expected_key:
            s.cheat_progress += 1
            s.cheat_last_key_ms = aktualni_cas
            if s.cheat_progress == len(self.CHEAT_SEQUENCE):
                s.autoplay_enabled = not s.autoplay_enabled
                self.reset_cheat_progress()
                safe_play(self.sounds.get('start'))
        elif key == self.CHEAT_SEQUENCE[0]:
            s.cheat_progress = 1
            s.cheat_last_key_ms = aktualni_cas
        else:
            self.reset_cheat_progress()

    @staticmethod
    def je_cil_blokovan_astronautem(state, cil_rect, lane_half_width):
        """True when an astronaut is in the bullet path between ship and target."""
        for astronaut in state.astronauti:
            a_rect = astronaut['rect']
            if a_rect.bottom >= state.raketka.top:
                continue
            if a_rect.centery <= cil_rect.centery:
                continue
            if abs(a_rect.centerx - cil_rect.centerx) <= lane_half_width + ASTRONAUT_SIRKA // 2:
                return True
        return False

    def autoplay_controls(self):
        s = self.state
        lane_half_width = max(22, RAKETKA_SIRKA // 4)
        meteory = [m['rect'] for m in s.meteority]
        powerupy = [p['rect'] for p in s.powerupy if not self.je_cil_blokovan_astronautem(s, p['rect'], lane_half_width)]
        cile = meteory + powerupy
        if not cile:
            return (0, False, False)
        cil = min(cile, key=lambda r: (ROZLISENI_Y - r.centery) * 1.15 + abs(r.centerx - s.raketka.centerx))
        dx = cil.centerx - s.raketka.centerx
        if abs(dx) <= 6:
            smer = 0
        elif dx > 0:
            smer = 1
        else:
            smer = -1
        meteory_v_linii = [r for r in meteory if abs(r.centerx - s.raketka.centerx) <= lane_half_width and r.bottom < s.raketka.top and (not self.je_cil_blokovan_astronautem(s, r, lane_half_width))]
        powerupy_v_linii = [r for r in powerupy if abs(r.centerx - s.raketka.centerx) <= lane_half_width and r.bottom < s.raketka.top]
        should_fire = bool(meteory_v_linii or powerupy_v_linii)
        big_meteor_v_linii = any((meteorit.get('je_velky') and abs(meteorit['rect'].centerx - s.raketka.centerx) <= lane_half_width and (meteorit['rect'].bottom < s.raketka.top) and (not self.je_cil_blokovan_astronautem(s, meteorit['rect'], lane_half_width)) for meteorit in s.meteority))
        should_use_charge = s.naboj_pripraveny and big_meteor_v_linii
        return (smer, should_fire, should_use_charge)

    def update(self, delta_ms, dt_factor):
        s = self.state
        if s.screen == 'game':
            self.update_game(delta_ms, dt_factor)
        elif s.screen == 'dying':
            self.update_dying(delta_ms, dt_factor)

    def update_game(self, delta_ms, dt_factor):
        s = self.state
        aktualni_cas = pygame.time.get_ticks()
        shield_aktivni = aktualni_cas < s.shield_end_ms
        slow_time_aktivni = aktualni_cas < s.slow_time_end_ms
        boost_aktivni = aktualni_cas < s.boost_end_ms
        casovy_koeficient = 0.5 if slow_time_aktivni else 1.0
        inverzni_casovy_koeficient = 1.0 / casovy_koeficient
        aktualni_raketka_rychlost = RAKETKA_RYCHLOST_BOOST if boost_aktivni else RAKETKA_RYCHLOST
        aktualni_strela_interval = STRELA_INTERVAL_BOOST_MS if boost_aktivni else STRELA_INTERVAL_MS
        keys = pygame.key.get_pressed()
        auto_smer = 0
        auto_fire = False
        auto_charge = False
        if s.autoplay_enabled:
            auto_smer, auto_fire, auto_charge = self.autoplay_controls()
        posunuto = False
        chce_vpravo = keys[pygame.K_RIGHT] or auto_smer > 0
        chce_vlevo = keys[pygame.K_LEFT] or auto_smer < 0
        if chce_vpravo and (not chce_vlevo):
            s.raketka.x += aktualni_raketka_rychlost * dt_factor
            emit_burn_plume(s.particles, s.raketka)
            posunuto = True
        if chce_vlevo and (not chce_vpravo):
            s.raketka.x -= aktualni_raketka_rychlost * dt_factor
            emit_burn_plume(s.particles, s.raketka)
            posunuto = True
        if s.cekani_na_prvni_pohyb and posunuto:
            s.cekani_na_prvni_pohyb = False
            now = pygame.time.get_ticks()
            s.hra_zacatek_cas = now
            s.cas_posledni_strely = now
            s.cas_posledni_meteoritu = now
            s.cas_posledni_astronauta = now
        if (keys[pygame.K_UP] or auto_charge) and s.naboj_pripraveny and (not s.cekani_na_prvni_pohyb):
            s.naboj_pripraveny = False
            s.naboj_pocitadlo = 0
            for i in range(NABOJ_SALVA_STRELY):
                nova_strela = pygame.Rect(int(s.raketka.centerx - STRELA_SIRKA / 2), int(s.raketka.y - STRELA_VYSKA - i * NABOJ_SALVA_ROZESTUP), STRELA_SIRKA, STRELA_VYSKA)
                s.strely.append(nova_strela)
            s.cas_posledni_strely = aktualni_cas
            safe_play(self.sounds.get('exploze'))
            emit_muzzle_flash(s.particles, s.raketka)
            emit_particles(s.particles, (s.raketka.centerx, s.raketka.top - 10), 16, 0.8, 2.4, 2.5, 5, BARVA_NABOJ, life_ms=360)
            trigger_shake(s, 4, 180)
        if keys[pygame.K_ESCAPE] and s.screen == 'game':
            s.screen = 'paused'
            s.pause_start_time = pygame.time.get_ticks()
        update_shake(s, delta_ms)
        s.raketka.x = max(0, min(ROZLISENI_X - RAKETKA_SIRKA, s.raketka.x))
        if s.cekani_na_prvni_pohyb:
            return
        odehrane_ms = aktualni_cas - s.hra_zacatek_cas - s.pozastaveno_celkove_ms
        koeficient_ztezovani = self.ziskej_koeficient_ztezovani(odehrane_ms)
        min_dyn, max_dyn, max_pocet_dyn = self.ziskej_meteor_spawn_parametry(odehrane_ms)
        s.meteor_interval_ms = max(min_dyn, min(s.meteor_interval_ms, max_dyn))
        aktualni_meteor_rychlost = METEOR_RYCHLOST_ZAKLAD * koeficient_ztezovani * casovy_koeficient
        aktualni_astronaut_rychlost = ASTRONAUT_RYCHLOST * casovy_koeficient
        aktualni_powerup_rychlost = POWERUP_RYCHLOST * casovy_koeficient
        raketka_mask = ziskej_masku_rectu(s.raketka.width, s.raketka.height, self.rect_mask_cache)
        if (keys[pygame.K_SPACE] or auto_fire) and aktualni_cas - s.cas_posledni_strely >= aktualni_strela_interval:
            nova_strela = pygame.Rect(int(s.raketka.centerx - STRELA_SIRKA / 2), int(s.raketka.y - STRELA_VYSKA), STRELA_SIRKA, STRELA_VYSKA)
            s.strely.append(nova_strela)
            s.cas_posledni_strely = aktualni_cas
            safe_play(self.sounds.get('strela'))
            emit_muzzle_flash(s.particles, s.raketka)
        herni_elapsed_meteor_ms = (aktualni_cas - s.cas_posledni_meteoritu) * casovy_koeficient
        if herni_elapsed_meteor_ms >= s.meteor_interval_ms and len(s.meteority) < max_pocet_dyn:
            je_velky = odehrane_ms >= 30000 and random.random() < VELKY_METEORIT_SANCE
            if je_velky:
                velikost = random.randint(VELKY_METEORIT_MIN_VELIKOST, VELKY_METEORIT_MAX_VELIKOST)
                hp = VELKY_METEORIT_HP
                barva = VELKY_METEORIT_BARVA
            else:
                velikost = random.randint(METEOR_MIN_VELIKOST, METEOR_MAX_VELIKOST)
                hp = 1
                barva = METEOR_BARVA
            nova_pozice_x = self.najdi_bezpecnou_pozici_x_meteoritu(velikost)
            if nova_pozice_x is not None:
                pool = self.big_meteor_sprite_pool if je_velky else self.meteor_sprite_pool
                novy = {'rect': pygame.Rect(nova_pozice_x, -velikost, velikost, velikost), 'hp': hp, 'barva': barva, 'je_velky': je_velky, 'design_id': random.randint(0, 2), 'sprite_idx': ziskej_nahodny_sprite_index(pool)}
                s.meteority.append(novy)
                s.cas_posledni_meteoritu = aktualni_cas
                s.meteor_interval_ms = random.randint(min_dyn, max_dyn)
            else:
                retry_game_ms = 250
                s.cas_posledni_meteoritu = int(aktualni_cas - (s.meteor_interval_ms - retry_game_ms) * inverzni_casovy_koeficient)
        herni_elapsed_astro = (aktualni_cas - s.cas_posledni_astronauta) * casovy_koeficient
        if herni_elapsed_astro >= s.astronaut_interval_ms:
            nova_pozice_x = self.najdi_bezpecnou_pozici_x_astronauta()
            if nova_pozice_x is not None:
                novy = {'rect': pygame.Rect(nova_pozice_x, -ASTRONAUT_VYSKA, ASTRONAUT_SIRKA, ASTRONAUT_VYSKA), 'sprite_idx': ziskej_nahodny_sprite_index(self.astronaut_sprite_pool)}
                s.astronauti.append(novy)
                s.cas_posledni_astronauta = aktualni_cas
                s.astronaut_interval_ms = random.randint(6500, 11000)
            else:
                retry_game_ms = 250
                s.cas_posledni_astronauta = int(aktualni_cas - (s.astronaut_interval_ms - retry_game_ms) * inverzni_casovy_koeficient)
        herni_elapsed_pu = (aktualni_cas - s.cas_posledni_powerupu) * casovy_koeficient
        if herni_elapsed_pu >= s.powerup_interval_ms:
            self.spawn_powerup(aktualni_cas)
        for meteorit in s.meteority[:]:
            if 'y' not in meteorit:
                meteorit['y'] = float(meteorit['rect'].y)
            meteorit['y'] += aktualni_meteor_rychlost * dt_factor
            meteorit['rect'].y = int(meteorit['y'])
            meteorit_mask = ziskej_meteorit_mask(meteorit, self.meteor_mask_cache, self.meteor_surface_cache, self.meteor_sprite_pool, self.big_meteor_sprite_pool)
            if meteorit['rect'].top > ROZLISENI_Y:
                s.meteority.remove(meteorit)
                if not shield_aktivni:
                    s.zivoty -= 1
                    safe_play(self.sounds.get('hit'))
                trigger_shake(s, 5, 220)
                emit_explosion(s.particles, (meteorit['rect'].centerx, ROZLISENI_Y - 20), velky=meteorit['je_velky'])
                if s.zivoty <= 0:
                    self.trigger_dying('meteor')
                continue
            for strela in s.strely[:]:
                strela_mask = ziskej_masku_rectu(strela.width, strela.height, self.rect_mask_cache)
                if kolize_maska(meteorit['rect'], meteorit_mask, strela, strela_mask):
                    if strela in s.strely:
                        s.strely.remove(strela)
                    meteorit['hp'] -= 1
                    if meteorit['hp'] <= 0 and meteorit in s.meteority:
                        s.meteority.remove(meteorit)
                        s.score += SCORE_BIG_METEOR if meteorit['je_velky'] else SCORE_SMALL_METEOR
                        if not s.naboj_pripraveny:
                            s.naboj_pocitadlo += 1
                            if s.naboj_pocitadlo >= NABOJ_POTREBA:
                                s.naboj_pripraveny = True
                        safe_play(self.sounds.get('exploze'))
                        emit_explosion(s.particles, meteorit['rect'].center, velky=meteorit['je_velky'])
                        trigger_shake(s, 7 if meteorit['je_velky'] else 5, 280)
                    else:
                        emit_particles(s.particles, strela.center, 6, 0.4, 1.4, 1.5, 3.2, BARVA_EXPLOZE, life_ms=260)
                        trigger_shake(s, 3, 140)
                    break
            if meteorit in s.meteority and kolize_maska(meteorit['rect'], meteorit_mask, s.raketka, raketka_mask):
                s.meteority.remove(meteorit)
                if not shield_aktivni:
                    s.zivoty -= 1
                    safe_play(self.sounds.get('hit'))
                emit_explosion(s.particles, s.raketka.center, velky=True)
                trigger_shake(s, 9, 320)
                if s.zivoty <= 0:
                    self.trigger_dying('meteor')
        for powerup in s.powerupy[:]:
            if 'y' not in powerup:
                powerup['y'] = float(powerup['rect'].y)
            powerup['y'] += aktualni_powerup_rychlost * dt_factor
            powerup['rect'].y = int(powerup['y'])
            if powerup['rect'].top > ROZLISENI_Y:
                s.powerupy.remove(powerup)
                continue
            for strela in s.strely[:]:
                if powerup['rect'].colliderect(strela):
                    if strela in s.strely:
                        s.strely.remove(strela)
                    self.aktivuj_powerup(s, powerup['typ'], aktualni_cas)
                    safe_play(self.sounds.get('start'))
                    emit_particles(s.particles, powerup['rect'].center, 20, 0.6, 2.2, 2, 4, POWERUP_BARVY.get(powerup['typ'], (255, 255, 255)), life_ms=420)
                    if powerup in s.powerupy:
                        s.powerupy.remove(powerup)
                    break
        for astronaut in s.astronauti[:]:
            if 'y' not in astronaut:
                astronaut['y'] = float(astronaut['rect'].y)
            astronaut['y'] += aktualni_astronaut_rychlost * dt_factor
            astronaut['rect'].y = int(astronaut['y'])
            if astronaut['rect'].top > ROZLISENI_Y:
                s.astronauti.remove(astronaut)
                continue
            for strela in s.strely[:]:
                if astronaut['rect'].colliderect(strela):
                    if strela in s.strely:
                        s.strely.remove(strela)
                    if astronaut in s.astronauti:
                        s.astronauti.remove(astronaut)
                    s.zivoty = 0
                    safe_play(self.sounds.get('hit'))
                    emit_explosion(s.particles, strela.center, velky=False)
                    trigger_shake(s, 5, 200)
                    if s.zivoty <= 0:
                        self.trigger_dying('astronaut')
                    break
        for strela in s.strely[:]:
            emit_trail(s.particles, strela)
            strela.y -= STRELA_RYCHLOST * dt_factor
            if strela.bottom < 0:
                s.strely.remove(strela)
        limit_particles(s.particles)

    def update_dying(self, delta_ms, dt_factor):
        """Death animation: world continues, no spawns, no input, ship gone."""
        s = self.state
        s.dying_timer_ms -= delta_ms
        update_shake(s, delta_ms)
        aktualni_cas = pygame.time.get_ticks()
        slow_time_aktivni = aktualni_cas < s.slow_time_end_ms
        casovy_koeficient = 0.5 if slow_time_aktivni else 1.0
        koeficient_ztezovani = self.ziskej_koeficient_ztezovani(aktualni_cas - s.hra_zacatek_cas - s.pozastaveno_celkove_ms)
        aktualni_meteor_rychlost = METEOR_RYCHLOST_ZAKLAD * koeficient_ztezovani * casovy_koeficient
        aktualni_astronaut_rychlost = ASTRONAUT_RYCHLOST * casovy_koeficient
        aktualni_powerup_rychlost = POWERUP_RYCHLOST * casovy_koeficient
        for meteorit in s.meteority[:]:
            if 'y' not in meteorit:
                meteorit['y'] = float(meteorit['rect'].y)
            meteorit['y'] += aktualni_meteor_rychlost * dt_factor
            meteorit['rect'].y = int(meteorit['y'])
            if meteorit['rect'].top > ROZLISENI_Y:
                s.meteority.remove(meteorit)
        for astronaut in s.astronauti[:]:
            if 'y' not in astronaut:
                astronaut['y'] = float(astronaut['rect'].y)
            astronaut['y'] += aktualni_astronaut_rychlost * dt_factor
            astronaut['rect'].y = int(astronaut['y'])
            if astronaut['rect'].top > ROZLISENI_Y:
                s.astronauti.remove(astronaut)
        for powerup in s.powerupy[:]:
            if 'y' not in powerup:
                powerup['y'] = float(powerup['rect'].y)
            powerup['y'] += aktualni_powerup_rychlost * dt_factor
            powerup['rect'].y = int(powerup['y'])
            if powerup['rect'].top > ROZLISENI_Y:
                s.powerupy.remove(powerup)
        for strela in s.strely[:]:
            strela.y -= STRELA_RYCHLOST * dt_factor
            if strela.bottom < 0:
                s.strely.remove(strela)
        limit_particles(s.particles)
        if s.dying_timer_ms <= 0:
            self.trigger_game_over_state()

    def render(self, delta_ms, dt_factor):
        s = self.state
        if s.screen == 'main_menu':
            self.render_main_menu(dt_factor)
        elif s.screen == 'leaderboard':
            self.render_leaderboard(dt_factor)
        elif s.screen == 'how_to_play':
            self.render_how_to_play(dt_factor)
        elif s.screen == 'game_over':
            self.render_game_over(dt_factor)
        elif s.screen == 'paused':
            self.render_pause(dt_factor)
        elif s.screen == 'game':
            self.render_game(delta_ms, dt_factor)
        elif s.screen == 'dying':
            self.render_dying(delta_ms, dt_factor)

    def _render_bg(self, dt_factor):
        vykresli_pozadi_animovane(self.okno, self.pozadi_surface, self.nebula_surface, self.state.hvezdy, self.state.camera_offset, dt_factor)

    def render_main_menu(self, dt_factor):
        self._render_bg(dt_factor)
        self.okno.blit(self.overlay_surface, (0, 0))
        s = self.state
        draw_text(self.okno, self.fonts, 'Hlavní menu', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 4, velikost=80)
        draw_button(self.okno, self.fonts, PLAY_BUTTON_RECT.x, PLAY_BUTTON_RECT.y, PLAY_BUTTON_RECT.width, PLAY_BUTTON_RECT.height, DEFAULTNI_BARVA_TLACITKA, 'Hrát', (0, 255, 255), selected=s.main_menu_selected == 0)
        draw_button(self.okno, self.fonts, LEADERBOARD_BUTTON_RECT.x, LEADERBOARD_BUTTON_RECT.y, LEADERBOARD_BUTTON_RECT.width, LEADERBOARD_BUTTON_RECT.height, DEFAULTNI_BARVA_TLACITKA, 'Žebříček', (255, 255, 255), selected=s.main_menu_selected == 1)
        draw_button(self.okno, self.fonts, HOW_TO_PLAY_BUTTON_RECT.x, HOW_TO_PLAY_BUTTON_RECT.y, HOW_TO_PLAY_BUTTON_RECT.width, HOW_TO_PLAY_BUTTON_RECT.height, DEFAULTNI_BARVA_TLACITKA, 'Jak hrát', (255, 255, 255), selected=s.main_menu_selected == 2)
        draw_button(self.okno, self.fonts, QUIT_BUTTON_RECT.x, QUIT_BUTTON_RECT.y, QUIT_BUTTON_RECT.width, QUIT_BUTTON_RECT.height, DEFAULTNI_BARVA_TLACITKA, 'Konec', (255, 0, 0), selected=s.main_menu_selected == 3)
        draw_text(self.okno, self.fonts, 'F11 přepíná celou obrazovku', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 76, velikost=20)
        draw_text(self.okno, self.fonts, 'V menu se pohybuj šipkami nebo myší', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 52, velikost=20)
        draw_text(self.okno, self.fonts, 'Potvrď Enterem nebo levým kliknutím', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 28, velikost=20)

    def render_how_to_play(self, dt_factor):
        self._render_bg(dt_factor)
        self.okno.blit(self.overlay_surface, (0, 0))
        s = self.state
        draw_text(self.okno, self.fonts, 'Jak hrát', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 6, velikost=66)
        start_y = ROZLISENI_Y / 6 + 70
        radek = 38
        lines = [('Pohyb: šipka vlevo / vpravo', DEFAULTNI_BARVA_TEXTU, 26), ('Střelba: mezerník (jednou nebo držet)', DEFAULTNI_BARVA_TEXTU, 24), ('Začátek kola: hra se rozběhne až po prvním pohybu', DEFAULTNI_BARVA_TEXTU, 23), ('Nič meteority (malé i velké)', (0, 255, 255), 26), ('Do astronautů nikdy nestřílej', (255, 130, 130), 26), ('Když meteorit proletí dolů, ztratíš život', DEFAULTNI_BARVA_TEXTU, 23), ('Po ~30 s se objevují velké červené meteority (3 zásahy)', DEFAULTNI_BARVA_TEXTU, 22), ('Power-upy padají po 20-30 s, aktivuješ je zásahem', DEFAULTNI_BARVA_TEXTU, 22), ('S=Štít (10 s), T=Zpomalení času (10 s), B=Zrychlení (10 s)', DEFAULTNI_BARVA_TEXTU, 22), ('Ničením meteoritů se postupně dobíjí trojitá střela', (255, 200, 60), 24), ('Po nabití, šipka nahoru vystřelí tyto 3 rány naráz', (255, 200, 60), 24)]
        for i, (txt, col, sz) in enumerate(lines):
            draw_text(self.okno, self.fonts, txt, col, ROZLISENI_X / 2, start_y + radek * i, velikost=sz)
        s.how_to_play_back_rect = pygame.Rect(ROZLISENI_X / 2 - 100, ROZLISENI_Y * 0.8 - 25, 200, 50)
        draw_button(self.okno, self.fonts, s.how_to_play_back_rect.x, s.how_to_play_back_rect.y, s.how_to_play_back_rect.width, s.how_to_play_back_rect.height, DEFAULTNI_BARVA_TLACITKA, 'Zpět', (0, 255, 255), selected=True)
        draw_text(self.okno, self.fonts, 'Zpět: Enter, Esc nebo levý klik', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 28, velikost=20)

    def render_game_over(self, dt_factor):
        self._render_bg(dt_factor)
        self.okno.blit(self.overlay_surface, (0, 0))
        s = self.state
        draw_text(self.okno, self.fonts, 'Konec hry', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 4, velikost=80)
        draw_text(self.okno, self.fonts, f'Skóre: {s.score}', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 4 + 70, velikost=28)
        draw_text(self.okno, self.fonts, f'Čas: {s.konecny_cas_s:.1f}s', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 4 + 110, velikost=28)
        if s.zadani_jmena:
            self._render_name_modal()
        else:
            if s.zaznam_ulozen:
                draw_text(self.okno, self.fonts, 'Skóre uloženo', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 2 + 30, velikost=24)
            draw_button(self.okno, self.fonts, PLAY_BUTTON_RECT.x, PLAY_BUTTON_RECT.y, PLAY_BUTTON_RECT.width, PLAY_BUTTON_RECT.height, DEFAULTNI_BARVA_TLACITKA, 'Hrát znovu', (0, 255, 255), selected=s.game_over_selected == 0)
            draw_button(self.okno, self.fonts, QUIT_BUTTON_RECT.x, QUIT_BUTTON_RECT.y, QUIT_BUTTON_RECT.width, QUIT_BUTTON_RECT.height, DEFAULTNI_BARVA_TLACITKA, 'Konec do menu', (255, 0, 0), selected=s.game_over_selected == 1)

    def _render_name_modal(self):
        s = self.state
        dim = pygame.Surface((ROZLISENI_X, ROZLISENI_Y), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 120))
        self.okno.blit(dim, (0, 0))
        box = pygame.Rect(ROZLISENI_X / 2 - 220, ROZLISENI_Y / 2 - 120, 440, 240)
        pygame.draw.rect(self.okno, (25, 25, 35), box, border_radius=8)
        pygame.draw.rect(self.okno, (120, 120, 160), box, width=2, border_radius=8)
        draw_text(self.okno, self.fonts, 'Zadej iniciály', DEFAULTNI_BARVA_TEXTU, box.centerx, box.y + 28, velikost=32)
        draw_text(self.okno, self.fonts, 'Arkádový styl: 3 znaky', DEFAULTNI_BARVA_TEXTU, box.centerx, box.y + 60, velikost=20)
        slot_width = 80
        slot_height = 92
        slot_gap = 18
        total_width = ARCADE_JMENO_DELKA * slot_width + (ARCADE_JMENO_DELKA - 1) * slot_gap
        start_x = box.centerx - total_width // 2
        slot_y = box.centery - slot_height // 2 + 8
        for idx in range(ARCADE_JMENO_DELKA):
            rect = pygame.Rect(start_x + idx * (slot_width + slot_gap), slot_y, slot_width, slot_height)
            barva_ramu = (0, 255, 255) if idx == s.arcade_jmeno_index else (120, 120, 160)
            pygame.draw.rect(self.okno, (35, 35, 50), rect, border_radius=8)
            pygame.draw.rect(self.okno, barva_ramu, rect, width=3, border_radius=8)
            draw_text(self.okno, self.fonts, s.arcade_jmeno_znaky[idx], DEFAULTNI_BARVA_TEXTU, rect.centerx, rect.centery + 4, velikost=50)
            if idx == s.arcade_jmeno_index:
                draw_text(self.okno, self.fonts, '^', (0, 255, 255), rect.centerx, rect.y - 10, velikost=26)
                draw_text(self.okno, self.fonts, 'v', (0, 255, 255), rect.centerx, rect.bottom + 10, velikost=26)
                draw_text(self.okno, self.fonts, '<', (0, 255, 255), rect.x - 14, rect.centery + 4, velikost=26)
                draw_text(self.okno, self.fonts, '>', (0, 255, 255), rect.right + 14, rect.centery + 4, velikost=26)
        draw_text(self.okno, self.fonts, 'Enter potvrdí, Esc přeskočí uložení', DEFAULTNI_BARVA_TEXTU, box.centerx, box.bottom - 28, velikost=18)
        s.name_confirm_rect = None
        s.name_skip_rect = None

    def render_leaderboard(self, dt_factor):
        self._render_bg(dt_factor)
        self.okno.blit(self.overlay_surface, (0, 0))
        s = self.state
        draw_text(self.okno, self.fonts, 'Žebříček', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 5, velikost=70)
        if s.leaderboard_cache:
            start_y = ROZLISENI_Y / 5 + 60
            for idx, zaznam in enumerate(s.leaderboard_cache[:LEADERBOARD_SHOW_LIMIT]):
                name = zaznam.get('name', '?')[:MAX_JMENO_DELKA]
                sc = zaznam.get('score', zaznam.get('meteors', 0))
                cas_s = zaznam.get('time_s', 0.0)
                y = start_y + idx * 34
                draw_text(self.okno, self.fonts, f'{idx + 1}. {name} - {sc} bodů | {cas_s:.1f}s', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, y, velikost=24)
        else:
            draw_text(self.okno, self.fonts, 'Zatím žádné skóre', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 2, velikost=28)
        s.leaderboard_back_rect = pygame.Rect(ROZLISENI_X / 2 - 100, ROZLISENI_Y * 0.8 - 25, 200, 50)
        draw_button(self.okno, self.fonts, s.leaderboard_back_rect.x, s.leaderboard_back_rect.y, s.leaderboard_back_rect.width, s.leaderboard_back_rect.height, DEFAULTNI_BARVA_TLACITKA, 'Zpět', (0, 255, 255), selected=True)
        draw_text(self.okno, self.fonts, 'V menu se pohybuj šipkami nebo myší', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 52, velikost=20)
        draw_text(self.okno, self.fonts, 'Potvrď Enterem, Esc nebo levým kliknutím', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 28, velikost=20)

    def render_pause(self, dt_factor):
        self._render_bg(dt_factor)
        self.okno.blit(self.overlay_surface, (0, 0))
        s = self.state
        draw_text(self.okno, self.fonts, 'Pauza', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 4, velikost=80)
        draw_button(self.okno, self.fonts, PLAY_BUTTON_RECT.x, PLAY_BUTTON_RECT.y, PLAY_BUTTON_RECT.width, PLAY_BUTTON_RECT.height, DEFAULTNI_BARVA_TLACITKA, 'Pokračovat', (0, 255, 255), selected=s.pause_menu_selected == 0)
        draw_button(self.okno, self.fonts, QUIT_BUTTON_RECT.x, QUIT_BUTTON_RECT.y, QUIT_BUTTON_RECT.width, QUIT_BUTTON_RECT.height, DEFAULTNI_BARVA_TLACITKA, 'Konec do menu', (255, 0, 0), selected=s.pause_menu_selected == 1)
        draw_text(self.okno, self.fonts, 'V menu se pohybuj šipkami nebo myší', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 52, velikost=20)
        draw_text(self.okno, self.fonts, 'Potvrď Enterem nebo levým kliknutím', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 28, velikost=20)

    def render_game(self, delta_ms, dt_factor):
        s = self.state
        self._render_bg(dt_factor)
        vykresli_raketku(self.okno, s.raketka, s.camera_offset)
        if s.cekani_na_prvni_pohyb:
            draw_text(self.okno, self.fonts, 'Pohybuj se šipkami vlevo a vpravo', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 2 - 12, velikost=28)
            draw_text(self.okno, self.fonts, 'Esc pozastaví hru', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 2 + 22, velikost=22)
            draw_text(self.okno, self.fonts, 'Pohybem spustíš kolo', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y / 2 + 54, velikost=22)
            draw_text(self.okno, self.fonts, 'F11 přepíná celou obrazovku', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X / 2, ROZLISENI_Y - 28, velikost=20)
            self._render_hud(0)
            return
        odehrane_ms = pygame.time.get_ticks() - s.hra_zacatek_cas - s.pozastaveno_celkove_ms
        self._render_entities(delta_ms, dt_factor)
        self._render_hud(odehrane_ms)

    def render_dying(self, delta_ms, dt_factor):
        """Render dying animation — world visible, ship gone."""
        s = self.state
        self._render_bg(dt_factor)
        self._render_entities(delta_ms, dt_factor)
        if s.dying_type == 'astronaut' and s.dying_timer_ms > 0:
            fade = max(0.0, s.dying_timer_ms / DEATH_ANIM_DURATION_MS)
            alpha = int(120 * fade)
            flash = pygame.Surface((ROZLISENI_X, ROZLISENI_Y), pygame.SRCALPHA)
            flash.fill((255, 30, 30, alpha))
            self.okno.blit(flash, (0, 0))
        odehrane_ms = max(0, pygame.time.get_ticks() - s.hra_zacatek_cas - s.pozastaveno_celkove_ms)
        self._render_hud(odehrane_ms)

    def _render_entities(self, delta_ms, dt_factor):
        """Render all entities (meteors, astronauts, powerups, bullets, particles, warnings)."""
        s = self.state
        for meteorit in s.meteority:
            vykresli_meteorit(self.okno, meteorit, s.camera_offset, self.meteor_surface_cache, self.meteor_sprite_pool, self.big_meteor_sprite_pool)
        for powerup in s.powerupy:
            vykresli_powerup(self.okno, self.fonts, powerup, s.camera_offset)
        for astronaut in s.astronauti:
            rect = astronaut['rect'].move(-int(s.camera_offset.x), -int(s.camera_offset.y))
            self.okno.blit(ziskej_astronaut_surface(astronaut, self.astronaut_surface_cache, self.astronaut_sprite_pool), rect)
        for strela in s.strely:
            vykresli_strelu(self.okno, strela, s.camera_offset)
        update_and_draw_particles(self.okno, s.particles, delta_ms, s.camera_offset, dt_factor)
        vykresli_varovani(self.okno, self.fonts, s.meteority, s.astronauti, s.camera_offset)

    def _render_hud(self, odehrane_ms):
        s = self.state
        aktualni_cas = pygame.time.get_ticks()
        odehrane_sekundy = max(0, odehrane_ms / 1000)
        draw_text_topright_glow(self.okno, self.fonts, f'Životy: {s.zivoty}', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X - 10, 10, velikost=24, offset=s.camera_offset)
        draw_text_topright_glow(self.okno, self.fonts, f'Skóre: {s.score}', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X - 10, 34, velikost=24, offset=s.camera_offset)
        draw_text_topright_glow(self.okno, self.fonts, f'Čas: {odehrane_sekundy:.1f}s', DEFAULTNI_BARVA_TEXTU, ROZLISENI_X - 10, 58, velikost=24, offset=s.camera_offset)
        if s.autoplay_enabled:
            draw_text_glow(self.okno, self.fonts, 'AUTOPLAY', (255, 220, 90), 96, 96, velikost=24, offset=s.camera_offset)
        shield_aktivni = aktualni_cas < s.shield_end_ms
        slow_time_aktivni = aktualni_cas < s.slow_time_end_ms
        boost_aktivni = aktualni_cas < s.boost_end_ms
        if shield_aktivni:
            draw_text_glow(self.okno, self.fonts, f'Štít {self.zbyvajici_sekundy(aktualni_cas, s.shield_end_ms):.1f}s', POWERUP_BARVY['shield'], 122, 18, velikost=22, offset=s.camera_offset)
        if slow_time_aktivni:
            draw_text_glow(self.okno, self.fonts, f'Zpomalený čas {self.zbyvajici_sekundy(aktualni_cas, s.slow_time_end_ms):.1f}s', POWERUP_BARVY['slow_time'], 142, 44, velikost=22, offset=s.camera_offset)
        if boost_aktivni:
            draw_text_glow(self.okno, self.fonts, f'Zrychlení {self.zbyvajici_sekundy(aktualni_cas, s.boost_end_ms):.1f}s', POWERUP_BARVY['boost'], 115, 70, velikost=22, offset=s.camera_offset)
        naboj_y = ROZLISENI_Y - 36
        naboj_x_start = ROZLISENI_X / 2 - 50
        if s.naboj_pripraveny:
            draw_text_glow(self.okno, self.fonts, '^ NABITO! ^', BARVA_NABOJ, ROZLISENI_X / 2, naboj_y, velikost=22, offset=s.camera_offset)
        else:
            for i in range(NABOJ_POTREBA):
                bx = int(naboj_x_start + i * 22)
                by = int(naboj_y - 8)
                ox_i = int(s.camera_offset.x)
                oy_i = int(s.camera_offset.y)
                if i < s.naboj_pocitadlo:
                    pygame.draw.rect(self.okno, BARVA_NABOJ, (bx - ox_i, by - oy_i, 16, 16), border_radius=4)
                else:
                    pygame.draw.rect(self.okno, (80, 80, 80), (bx - ox_i, by - oy_i, 16, 16), border_radius=4)
                    pygame.draw.rect(self.okno, (120, 120, 120), (bx - ox_i, by - oy_i, 16, 16), width=1, border_radius=4)

# ====== inlined: main.py ======

import asyncio
import pygame

pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=256)
pygame.init()


async def main():
    game = Game()
    await game.run()


asyncio.run(main())