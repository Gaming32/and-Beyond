import ipaddress

import pygame
from and_beyond.client import globals
from and_beyond.client.globals import GameStatus
from and_beyond.client.server_connection import ServerConnection
from and_beyond.client.ui import Ui, UiButton, UiLabel
from and_beyond.client.ui.accounts import AccountsMenu
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.client.ui.options_menu import OptionsMenu
from and_beyond.client.ui.question_screen import QuestionScreen
from and_beyond.common import PORT
from pygame import *
from pygame.locals import *


class TitleScreen(Ui):
    def __init__(self) -> None:
        super().__init__([
            UiLabel('...and BEYOND'),
            UiButton('Singleplayer', self.singleplayer),
            UiButton('Multiplayer', self.multiplayer),
            UiButton('Options', self.show_options),
            UiButton('Account', self.show_account_menu),
            UiButton('Quit', self.quit),
        ])

    def draw_and_call(self, surf: pygame.surface.Surface) -> None:
        surf.fill((0, 0, 0))
        if globals.ui_override is not None:
            return globals.ui_override.draw_and_call(surf)
        return super().draw_and_call(surf)

    def singleplayer(self) -> None:
        globals.ui_override = WorldScreen()

    def multiplayer(self) -> None:
        def connect_clicked(ip: str) -> None:
            if ':' in ip:
                try:
                    ipaddress.IPv6Address(ip)
                except ValueError:
                    host, port = ip.rsplit(':', 1)
                    try:
                        port = int(port)
                    except ValueError:
                        globals.ui_override = LabelScreen(f'Invalid address or host:port pair: {ip}')
                        globals.ui_override.parent = screen
                        return
                else:
                    host = ip
                    port = PORT
            else:
                host = ip
                port = PORT
            globals.config.config['last_server'] = ip
            globals.game_status = GameStatus.CONNECTING
            TitleScreen.load_multiplayer(host, port)
        if globals.config.uuid is None:
            globals.ui_override = LabelScreen(
                'You must have logged in to play multiplayer'
            )
            return
        screen = globals.ui_override = QuestionScreen(
            'Enter Server Address/IP:',
            'Connect',
            ok_callback=connect_clicked,
            default_text=globals.config.config['last_server']
        )
        globals.ui_override.text_input.selected = True

    def show_options(self) -> None:
        globals.ui_override = OptionsMenu()

    def show_account_menu(self) -> None:
        AccountsMenu().show()

    @staticmethod
    def load_multiplayer(server: str, port: int = PORT):
        conn = ServerConnection()
        globals.game_connection = conn
        conn.start(server, port)

    def quit(self) -> None:
        globals.running = False


from and_beyond.client.ui.world_screen import WorldScreen
