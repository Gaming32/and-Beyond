# pyright: reportWildcardImportFromLibrary=false
import logging
import os
import subprocess
import sys
from typing import Callable

import pygame
from pw32.client import button_ui, globals
from pw32.client.globals import GameStatus
from pw32.client.server_connection import ServerConnection
from pw32.client.ui_menus.options_menu import OptionsMenu
from pw32.utils import DEBUG
from pygame import *
from pygame.locals import *


class TitleScreen:
    buttons: button_ui.Buttons

    def __init__(self) -> None:
        self.buttons = [
            ('Singleplayer', self.singleplayer),
            # ('Multiplayer', self.multiplayer),
            ('Options', self.show_options),
            ('Quit', self.quit),
        ]

    def render(self, surf: Surface) -> None:
        surf.fill((0, 0, 0))
        if globals.ui_override is not None:
            return globals.ui_override.draw_and_call(surf)
        button_ui.draw_buttons_and_call(surf, self.buttons)

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


from pw32.client.ui_menus.world_screen import WorldScreen
