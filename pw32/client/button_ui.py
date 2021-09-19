# pyright: reportWildcardImportFromLibrary=false
from pw32.client.colors import BUTTON_BG, BUTTON_FG
from typing import Callable

import pygame
import pygame.draw
import pygame.font
import pygame.mouse
from pw32.client import globals
from pygame import *
from pygame.locals import *

BUTTON_WIDTH = 300
BUTTON_HEIGHT = 50

BUTTON_HEIGHT_PAD = BUTTON_HEIGHT + 25

pygame.font.init()
BUTTON_FONT = pygame.font.SysFont('Calibri', 30)

Buttons = list[tuple[str, Callable[[], None]]]


def draw_buttons_and_call(surf: Surface, buttons: Buttons) -> None:
    mouse_pos = pygame.mouse.get_pos()
    is_click = pygame.mouse.get_pressed(3)[0]

    x = surf.get_width() // 2 - BUTTON_WIDTH // 2
    y = surf.get_height() // 2 - BUTTON_HEIGHT_PAD * len(buttons) // 2

    for (text, action) in buttons:
        area = Rect(x, y, BUTTON_WIDTH, BUTTON_HEIGHT)
        # surf.fill(BUTTON_BG, area)
        pygame.draw.rect(surf, BUTTON_BG, area, 0, 5)
        text_render = BUTTON_FONT.render(text, True, BUTTON_FG)
        surf.blit(
            text_render,
            (
                area.x + area.width // 2 - text_render.get_width() // 2,
                area.y + area.height // 2 - text_render.get_height() // 2,
            )
        )
        if area.collidepoint(mouse_pos):
            pygame.draw.rect(surf, BUTTON_FG, area, 5, 5)
            if is_click:
                return action()
        y += BUTTON_HEIGHT_PAD
