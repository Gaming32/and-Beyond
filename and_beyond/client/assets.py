# pyright: reportWildcardImportFromLibrary=false
import logging

import and_beyond.client.mixer  # Load music files now
import pygame
import pygame.font
import pygame.image
import pygame.surface
import pygame.transform
from and_beyond.client.consts import BLOCK_RENDER_SIZE
from pygame import *
from pygame.locals import *


_missing_texture_cache: dict[str, pygame.surface.Surface] = {}
_MISSING_MAGENTA = (255, 0, 220)
def try_load_texture(filename: str, desired_size: tuple[int, int]) -> pygame.surface.Surface:
    try:
        return pygame.image.load(filename)
    except Exception:
        logging.warn('Unabel to load texture "%s". Using missing texture.', filename, exc_info=True)
        if desired_size == (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE):
            return MISSING_TEXTURE[0]
        if filename not in _missing_texture_cache:
            width, height = desired_size
            tex = pygame.surface.Surface(desired_size)
            tex.fill(_MISSING_MAGENTA, (
                0, 0,
                width // 2, (height + 1) // 2
            ))
            tex.fill(_MISSING_MAGENTA, (
                width // 2, (height + 1) // 2,
                (width + 1) // 2, height // 2
            ))
            _missing_texture_cache[filename] = tex
        return _missing_texture_cache[filename]

pygame.font.init()
GAME_FONT = pygame.font.SysFont('Calibri', 30)
DEBUG_FONT = pygame.font.SysFont('Courier', 20, bold=True)
CHAT_FONT = pygame.font.SysFont('Courier', 20)

MISSING_TEXTURE = [pygame.surface.Surface((BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE))]
MISSING_TEXTURE[0].fill(_MISSING_MAGENTA, (
    0, 0,
    BLOCK_RENDER_SIZE // 2, (BLOCK_RENDER_SIZE + 1) // 2
))
MISSING_TEXTURE[0].fill(_MISSING_MAGENTA, (
    BLOCK_RENDER_SIZE // 2, (BLOCK_RENDER_SIZE + 1) // 2,
    (BLOCK_RENDER_SIZE + 1) // 2, BLOCK_RENDER_SIZE // 2
))

PERSON_SPRITES = [
    try_load_texture('assets/sprites/person1.png', (6, 9)),
    try_load_texture('assets/sprites/person2.png', (6, 9)),
]

_BLOCK_SPRITES = [
    try_load_texture('assets/sprites/stone.png', (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)),
    try_load_texture('assets/sprites/dirt.png', (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)),
    try_load_texture('assets/sprites/grass.png', (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)),
    try_load_texture('assets/sprites/wood.png', (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)),
    try_load_texture('assets/sprites/planks.png', (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)),
    try_load_texture('assets/sprites/leaves.png', (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)),
]

BLOCK_SPRITES: list[list[pygame.surface.Surface]] = []
ROTATABLE_BLOCKS = [False, True, True, False, False, False, True]


SELECTED_ITEM_BG = [Surface((70, 70))]

def transform_assets() -> int:
    count = 0
    for (i, sprite) in enumerate(PERSON_SPRITES):
        sprite = sprite.convert_alpha()
        PERSON_SPRITES[i] = pygame.transform.scale(sprite, (25, 37))
        count += 1
    for (i, sprite) in enumerate(_BLOCK_SPRITES):
        BLOCK_SPRITES.append([sprite.convert_alpha()])
        if ROTATABLE_BLOCKS[i + 1]:
            for j in range(1, 4):
                rot = pygame.transform.rotate(sprite, j * 90)
                BLOCK_SPRITES[i].append(rot.convert_alpha())
        count += 1
    MISSING_TEXTURE[0] = MISSING_TEXTURE[0].convert()
    SELECTED_ITEM_BG[0] = SELECTED_ITEM_BG[0].convert_alpha() # type: ignore
    SELECTED_ITEM_BG[0].fill((0, 0, 0, 192))
    count += 2
    return count

ASSET_COUNT = 12
