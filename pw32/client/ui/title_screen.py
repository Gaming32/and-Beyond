# pyright: reportWildcardImportFromLibrary=false

import pygame
from pw32.client import globals
from pw32.client.globals import GameStatus
from pw32.client.server_connection import ServerConnection
from pw32.client.ui import Ui, UiButton, UiLabel
from pw32.client.ui.options_menu import OptionsMenu
from pw32.utils import DEBUG
from pygame import *
from pygame.locals import *


class TitleScreen(Ui):
    def __init__(self) -> None:
        super().__init__([
            UiLabel('...and BEYOND'),
            UiButton('Singleplayer', self.singleplayer),
            # UiButton('Multiplayer', self.multiplayer),
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
        globals.game_status = GameStatus.CONNECTING

    def show_options(self) -> None:
        globals.ui_override = OptionsMenu()

    @staticmethod
    def load_multiplayer(server: str):
        conn = ServerConnection()
        globals.game_connection = conn
        conn.start(server)

    def quit(self) -> None:
        globals.running = False


from pw32.client.ui.world_screen import WorldScreen
