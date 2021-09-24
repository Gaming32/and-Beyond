# pyright: reportWildcardImportFromLibrary=false
from pw32.client import globals
from pw32.client.ui import Ui, UiButton, UiToggleButton
from pygame import *
from pygame.locals import *


class OptionsMenu(Ui):
    fullscreen_toggle: UiToggleButton

    def __init__(self) -> None:
        self.fullscreen_toggle = UiToggleButton('Fullscreen', self.fullscreen_toggle_cb)
        super().__init__([
            self.fullscreen_toggle,
            UiButton('Back', self.close_option_menu),
        ])

    def draw_and_call(self, surf: Surface):
        self.fullscreen_toggle.toggled = globals.fullscreen
        return super().draw_and_call(surf)

    def close_option_menu(self) -> None:
        self.close()

    def fullscreen_toggle_cb(self, fullscreen: bool) -> None:
        globals.fullscreen = fullscreen
