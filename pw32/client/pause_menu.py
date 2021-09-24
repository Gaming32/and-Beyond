# pyright: reportWildcardImportFromLibrary=false
from typing import Callable

import pygame
from pw32.client import button_ui, globals
from pygame import *
from pygame.locals import *


class PauseMenu:
    buttons: button_ui.Buttons

    def __init__(self) -> None:
        self.buttons = [
            ('Continue Game', self.continue_game),
            # ('Options', self.show_options),
            ('Save and Quit', self.save_and_quit),
        ]

    def render(self, surf: Surface) -> None:
        gray = Surface(surf.get_size()).convert_alpha()
        gray.fill((0, 0, 0, 128))
        surf.blit(gray, gray.get_rect())
        button_ui.draw_buttons_and_call(surf, self.buttons)

    def continue_game(self) -> None:
        globals.paused = False

    def save_and_quit(self) -> None:
        globals.game_status = globals.GameStatus.STOPPING
        globals.connecting_status = 'Disconnecting'
        if globals.game_connection is not None:
            globals.game_connection.stop()
        if globals.singleplayer_pipe is not None:
            globals.connecting_status = 'Stopping singleplayer server'
            globals.close_singleplayer_server(False)
        globals.paused = False
