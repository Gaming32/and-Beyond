# pyright: reportWildcardImportFromLibrary=false
from typing import Callable

import pygame
import pygame.draw
import pygame.font
import pygame.mouse
from pw32.client import globals
from pw32.client.assets import GAME_FONT
from pw32.client.consts import UI_BG, UI_FG
from pygame import *
from pygame.locals import *

BUTTON_WIDTH = 300
BUTTON_HEIGHT = 50

BUTTON_HEIGHT_PAD = BUTTON_HEIGHT + 25

Buttons = list[tuple[str, Callable[[], None]]]


def draw_buttons_and_call(surf: Surface, buttons: Buttons) -> None:
    is_click = pygame.mouse.get_pressed(3)[0]

    x = surf.get_width() // 2 - BUTTON_WIDTH // 2
    y = surf.get_height() // 2 - BUTTON_HEIGHT_PAD * len(buttons) // 2

    for (text, action) in buttons:
        area = Rect(x, y, BUTTON_WIDTH, BUTTON_HEIGHT)
        pygame.draw.rect(surf, UI_BG, area, 0, 5)
        text_render = GAME_FONT.render(text, True, UI_FG)
        surf.blit(
            text_render,
            (
                area.x + area.width // 2 - text_render.get_width() // 2,
                area.y + area.height // 2 - text_render.get_height() // 2,
            )
        )
        if area.collidepoint(globals.mouse_screen):
            pygame.draw.rect(surf, UI_FG, area, 5, 5)
            if is_click:
                return action()
        y += BUTTON_HEIGHT_PAD
