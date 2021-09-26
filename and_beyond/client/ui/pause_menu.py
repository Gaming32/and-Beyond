# pyright: reportWildcardImportFromLibrary=false
import logging

import pygame
from and_beyond.client import globals
from and_beyond.client.ui import Ui, UiButton, UiLabel
from and_beyond.client.ui.options_menu import OptionsMenu
from and_beyond.pipe_commands import PipeCommands
from pygame import *
from pygame.locals import *


class PauseMenu(Ui):
    def __init__(self) -> None:
        super().__init__([
            UiLabel('Game Paused'),
            UiButton('Continue Game', self.continue_game),
            UiButton('Options', self.show_options),
            UiButton('Save and Quit', self.save_and_quit),
        ])

    def draw_and_call(self, surf: Surface):
        gray = Surface(surf.get_size()).convert_alpha()
        gray.fill((0, 0, 0, 128))
        surf.blit(gray, gray.get_rect())
        if globals.ui_override is not None:
            return globals.ui_override.draw_and_call(surf)
        return super().draw_and_call(surf)

    def pause_game(self) -> None:
        if globals.singleplayer_pipe is not None:
            logging.debug('Sending pause command...')
            globals.singleplayer_pipe.write(PipeCommands.PAUSE.to_bytes(2, 'little'))
            globals.singleplayer_pipe.flush()
        globals.paused = True

    def continue_game(self) -> None:
        if globals.singleplayer_pipe is not None:
            logging.debug('Sending unpause command...')
            globals.singleplayer_pipe.write(PipeCommands.UNPAUSE.to_bytes(2, 'little'))
            globals.singleplayer_pipe.flush()
        globals.paused = False

    def show_options(self) -> None:
        globals.ui_override = OptionsMenu()

    def save_and_quit(self) -> None:
        globals.game_status = globals.GameStatus.STOPPING
        globals.mixer.stop_all_music()
        globals.mixer.play_song()
        globals.connecting_status = 'Disconnecting'
        if globals.game_connection is not None:
            globals.game_connection.stop()
            globals.game_connection = None
        if globals.singleplayer_pipe is not None:
            globals.connecting_status = 'Stopping singleplayer server'
            globals.close_singleplayer_server(False)
            globals.singleplayer_pipe = None
        globals.paused = False
