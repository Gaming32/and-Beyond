# pyright: reportWildcardImportFromLibrary=false

import pygame
from and_beyond.client import globals
from and_beyond.client.globals import GameStatus
from and_beyond.client.server_connection import ServerConnection
from and_beyond.client.ui import Ui, UiButton, UiLabel, UiTextInput
from and_beyond.client.ui.options_menu import OptionsMenu
from and_beyond.client.ui.question_screen import QuestionScreen
from pygame import *
from pygame.locals import *


class TitleScreen(Ui):
    def __init__(self) -> None:
        super().__init__([
            UiLabel('...and BEYOND'),
            UiButton('Singleplayer', self.singleplayer),
            UiButton('Multiplayer', self.multiplayer),
            UiButton('Options', self.show_options),
            UiButton('Quit', self.quit),
        ])

    def draw_and_call(self, surf: Surface) -> None:
        surf.fill((0, 0, 0))
        if globals.ui_override is not None:
            return globals.ui_override.draw_and_call(surf)
        return super().draw_and_call(surf)

    def singleplayer(self) -> None:
        globals.ui_override = WorldScreen()

    def multiplayer(self) -> None:
        def connect_clicked(ip: str) -> None:
            globals.game_status = GameStatus.CONNECTING
            TitleScreen.load_multiplayer(ip)
        globals.ui_override = QuestionScreen(
            'Enter Server Address/IP:',
            'Connect',
            ok_callback=connect_clicked,
        )
        globals.ui_override.text_input.selected = True

    def show_options(self) -> None:
        globals.ui_override = OptionsMenu()

    @staticmethod
    def load_multiplayer(server: str):
        conn = ServerConnection()
        globals.game_connection = conn
        conn.start(server)

    def quit(self) -> None:
        globals.running = False


from and_beyond.client.ui.world_screen import WorldScreen
