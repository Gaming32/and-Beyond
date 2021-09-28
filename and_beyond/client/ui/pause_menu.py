# pyright: reportWildcardImportFromLibrary=false
import logging

import pygame
import pygame.event
from and_beyond.client import globals
from and_beyond.client.consts import SERVER_DISCONNECT_EVENT
from and_beyond.client.ui import Ui, UiButton, UiLabel
from and_beyond.client.ui.options_menu import OptionsMenu
from and_beyond.pipe_commands import PipeCommandsToServer
from pygame import *
from pygame.locals import *


class PauseMenu(Ui):
    disconnect_button: UiButton

    def __init__(self) -> None:
        super().__init__([
            UiLabel('Game Paused'),
            UiButton('Continue Game', self.continue_game),
            UiButton('Options', self.show_options),
        ])
        self.disconnect_button = UiButton('Disconnect', self.disconnect)
        self.elements.append(self.disconnect_button)

    def draw_and_call(self, surf: Surface):
        gray = Surface(surf.get_size()).convert_alpha()
        gray.fill((0, 0, 0, 128))
        surf.blit(gray, gray.get_rect())
        if globals.ui_override is not None:
            return globals.ui_override.draw_and_call(surf)
        self.disconnect_button.label = 'Disconnect' if globals.singleplayer_popen is None else 'Save and Quit'
        return super().draw_and_call(surf)

    def pause_game(self) -> None:
        if globals.singleplayer_pipe_out is not None:
            logging.debug('Sending pause command...')
            globals.singleplayer_pipe_out.write(PipeCommandsToServer.PAUSE.to_bytes(2, 'little'))
            globals.singleplayer_pipe_out.flush()
        globals.paused = True

    def continue_game(self) -> None:
        if globals.singleplayer_pipe_out is not None:
            logging.debug('Sending unpause command...')
            globals.singleplayer_pipe_out.write(PipeCommandsToServer.UNPAUSE.to_bytes(2, 'little'))
            globals.singleplayer_pipe_out.flush()
        globals.paused = False

    def show_options(self) -> None:
        globals.ui_override = OptionsMenu()

    def disconnect(self) -> None:
        pygame.event.post(pygame.event.Event(SERVER_DISCONNECT_EVENT, reason=None))
        globals.paused = False
