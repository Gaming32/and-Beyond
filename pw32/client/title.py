# pyright: reportWildcardImportFromLibrary=false
from typing import Callable

import pygame
from pw32.client import button_ui, globals
from pygame import *
from pygame.locals import *


class TitleScreen:
    buttons: button_ui.Buttons

    def __init__(self) -> None:
        self.buttons = [
            ('Start game', self.start_game),
            # ('Options', self.show_options),
            ('Quit', self.quit),
        ]

    def render(self, surf: Surface) -> None:
        surf.fill((0, 0, 0))
        button_ui.draw_buttons_and_call(surf, self.buttons)
    
    def start_game(self) -> None:
        globals.at_title = False
    
    def quit(self) -> None:
        globals.running = False
