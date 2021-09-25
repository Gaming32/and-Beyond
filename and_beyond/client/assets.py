# pyright: reportWildcardImportFromLibrary=false

import pygame
import pygame.font
import pygame.image
import pygame.surface
import pygame.transform
from pygame import *
from pygame.locals import *

pygame.font.init()
GAME_FONT = pygame.font.SysFont('Calibri', 30)
DEBUG_FONT = pygame.font.SysFont('Courier', 20, bold=True)

PERSON_SPRITES = [
    pygame.image.load('assets/sprites/person1.png'),
    pygame.image.load('assets/sprites/person2.png'),
]

_BLOCK_SPRITES = [
    pygame.image.load('assets/sprites/stone.png'),
    pygame.image.load('assets/sprites/dirt.png'),
    pygame.image.load('assets/sprites/grass.png'),
]

BLOCK_SPRITES: list[list[pygame.surface.Surface]] = []
ROTATABLE_BLOCKS = [False, True, True, False]

MISSING_TEXTURE = [pygame.image.load('assets/sprites/unknown.png')]

SELECTED_ITEM_BG = [Surface((70, 70))]

def transform_assets() -> int:
    count = 0
    for (i, sprite) in enumerate(PERSON_SPRITES):
        sprite = sprite.convert_alpha()
        PERSON_SPRITES[i] = pygame.transform.scale(sprite, (15, 37))
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
    count += 1
    return count

ASSET_COUNT = 3
