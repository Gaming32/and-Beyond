# pyright: reportWildcardImportFromLibrary=false
import logging

import pygame
import pygame.event
from and_beyond.client import globals
from and_beyond.client.consts import SERVER_DISCONNECT_EVENT
from and_beyond.client.ui import Ui, UiButton, UiLabel
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.client.ui.options_menu import OptionsMenu
from and_beyond.client.ui.question_screen import QuestionScreen
from and_beyond.common import PORT
from and_beyond.pipe_commands import PipeCommandsToServer, write_pipe
from pygame import *
from pygame.locals import *


class PauseMenu(Ui):
    open_to_lan_button: UiButton
    disconnect_button: UiButton

    def __init__(self) -> None:
        super().__init__([
            UiLabel('Game Paused'),
            UiButton('Continue Game', self.continue_game),
            UiButton('Options', self.show_options),
        ])
        self.open_to_lan_button = UiButton('Open to LAN', self.open_to_lan)
        self.disconnect_button = UiButton('Disconnect', self.disconnect)
        self.elements.extend((
            self.open_to_lan_button,
            self.disconnect_button,
        ))

    def draw_and_call(self, surf: pygame.surface.Surface):
        gray = Surface(surf.get_size()).convert_alpha()
        gray.fill((0, 0, 0, 128))
        surf.blit(gray, gray.get_rect())
        if globals.ui_override is not None:
            return globals.ui_override.draw_and_call(surf)
        self.open_to_lan_button.hidden = globals.singleplayer_popen is None
        self.disconnect_button.label = 'Disconnect' if globals.singleplayer_popen is None else 'Save and Quit'
        return super().draw_and_call(surf)

    def pause_game(self) -> None:
        pipe = globals.singleplayer_pipe_out
        if pipe is not None:
            logging.debug('Sending pause command...')
            write_pipe(pipe, PipeCommandsToServer.PAUSE)
            pipe.flush()
        globals.paused = True

    def continue_game(self) -> None:
        pipe = globals.singleplayer_pipe_out
        if pipe is not None:
            logging.debug('Sending unpause command...')
            write_pipe(pipe, PipeCommandsToServer.UNPAUSE)
            pipe.flush()
        globals.paused = False

    def show_options(self) -> None:
        globals.ui_override = OptionsMenu()

    def open_to_lan(self) -> None:
        def internal(port_str: str):
            port_str = port_str.strip()
            if not port_str:
                port = 0
            else:
                try:
                    port = int(port_str)
                except ValueError:
                    LabelScreen.show_message(f'Not a valid integer: {port_str}', closed_callback=screen.show)
                    return
            if 0 <= port < 65536:
                pipe = globals.singleplayer_pipe_out
                if pipe is None:
                    return
                write_pipe(pipe, PipeCommandsToServer.OPEN_TO_LAN)
                write_pipe(pipe, port)
                pipe.flush()
                globals.paused = False
            else:
                LabelScreen.show_message(f'Port number must be between 0 and 65535 (inclusive)', closed_callback=screen.show)
        screen = QuestionScreen('Enter a port number (empty for random):', ok_callback=internal, default_text=str(PORT))
        screen.show()

    def disconnect(self) -> None:
        pygame.event.post(pygame.event.Event(SERVER_DISCONNECT_EVENT, reason=None))
        globals.paused = False
