import logging

import pygame
import pygame.event
from pygame import *
from pygame.locals import *
from and_beyond import text

from and_beyond.client import globals
from and_beyond.client.consts import SERVER_DISCONNECT_EVENT
from and_beyond.client.ui import Ui, UiButton, UiLabel
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.client.ui.options_menu import OptionsMenu
from and_beyond.client.ui.question_screen import QuestionScreen
from and_beyond.common import PORT
from and_beyond.pipe_commands import PipeCommandsToServer, write_pipe
from and_beyond.text import translatable_text


class PauseMenu(Ui):
    open_to_lan_button: UiButton
    disconnect_button: UiButton

    def __init__(self) -> None:
        super().__init__([
            UiLabel(translatable_text('pause.title')),
            UiButton(translatable_text('pause.continue'), self.continue_game),
            UiButton(translatable_text('options.title'), self.show_options),
        ])
        self.open_to_lan_button = UiButton(translatable_text('pause.open_to_lan'), self.open_to_lan)
        self.disconnect_button = UiButton(translatable_text('pause.disconnect'), self.disconnect)
        self.elements.extend((
            self.open_to_lan_button,
            self.disconnect_button,
        ))

    def draw_and_call(self, surf: pygame.surface.Surface) -> None:
        gray = Surface(surf.get_size()).convert_alpha()
        gray.fill((0, 0, 0, 128))
        surf.blit(gray, gray.get_rect())
        if globals.ui_override is not None:
            return globals.ui_override.draw_and_call(surf)
        self.open_to_lan_button.hidden = globals.singleplayer_popen is None
        self.disconnect_button.label = (
            text.translate('pause.disconnect')
            if globals.singleplayer_popen is None
            else text.translate('pause.save_and_quit')
        )
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
        def internal(port_str: str) -> None:
            port_str = port_str.strip()
            if not port_str:
                port = 0
            else:
                try:
                    port = int(port_str)
                except ValueError:
                    LabelScreen.show_message(
                        text.translatable_text('open_to_lan.not_valid_integer', port_str),
                        closed_callback=screen.show
                    )
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
                LabelScreen.show_message(
                    text.translatable_text('open_to_lan.port_out_of_range'), closed_callback=screen.show
                )
        screen = QuestionScreen(
            translatable_text('open_to_lan.enter_port_number'), ok_callback=internal, default_text=str(PORT)
        )
        screen.show()

    def disconnect(self) -> None:
        pygame.event.post(pygame.event.Event(SERVER_DISCONNECT_EVENT, reason=None))
        globals.paused = False
