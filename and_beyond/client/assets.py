# pyright: reportWildcardImportFromLibrary=false

import pygame
import pygame.font
import pygame.image
import pygame.transform
from pygame import *
from pygame.locals import *

pygame.font.init()
GAME_FONT = pygame.font.SysFont('Calibri', 30)

PERSON_SPRITES = [
    pygame.image.load('assets/sprites/person1.png'),
    pygame.image.load('assets/sprites/person2.png'),
]

def transform_assets() -> int:
    count = 0
    for (i, sprite) in enumerate(PERSON_SPRITES):
        PERSON_SPRITES[i] = sprite.convert_alpha()
        PERSON_SPRITES[i] = pygame.transform.scale(sprite, (15, 37))
        count += 1
    return count

ASSET_COUNT = 3
