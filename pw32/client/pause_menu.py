# pyright: reportWildcardImportFromLibrary=false
import logging
from typing import Callable

import pygame
from pw32.client import button_ui, globals
from pw32.client.ui_menus.options_menu import OptionsMenu
from pw32.pipe_commands import PipeCommands
from pygame import *
from pygame.locals import *


class PauseMenu:
    buttons: button_ui.Buttons

    def __init__(self) -> None:
        self.buttons = [
            ('Continue Game', self.continue_game),
            ('Options', self.show_options),
            ('Save and Quit', self.save_and_quit),
        ]

    def render(self, surf: Surface) -> None:
        gray = Surface(surf.get_size()).convert_alpha()
        gray.fill((0, 0, 0, 128))
        surf.blit(gray, gray.get_rect())
        if globals.ui_override is not None:
            return globals.ui_override.draw_and_call(surf)
        button_ui.draw_buttons_and_call(surf, self.buttons)

    def pause_game(self) -> None:
        logging.debug('Sending pause command...')
        if globals.singleplayer_pipe is not None:
            globals.singleplayer_pipe.write(PipeCommands.PAUSE.to_bytes(2, 'little'))
            globals.singleplayer_pipe.flush()
        globals.paused = True

    def continue_game(self) -> None:
        logging.debug('Sending unpause command...')
        if globals.singleplayer_pipe is not None:
            globals.singleplayer_pipe.write(PipeCommands.UNPAUSE.to_bytes(2, 'little'))
            globals.singleplayer_pipe.flush()
        globals.paused = False

    def show_options(self) -> None:
        globals.ui_override = OptionsMenu()

    def save_and_quit(self) -> None:
        globals.game_status = globals.GameStatus.STOPPING
        globals.connecting_status = 'Disconnecting'
        if globals.game_connection is not None:
            globals.game_connection.stop()
        if globals.singleplayer_pipe is not None:
            globals.connecting_status = 'Stopping singleplayer server'
            globals.close_singleplayer_server(False)
        globals.paused = False
