# pyright: reportWildcardImportFromLibrary=false
from typing import Any

from and_beyond.client import globals
from and_beyond.client.ui import (SliderCallback, Ui, UiButton, UiLabel, UiSlider,
                            UiToggleButton)
from pygame import *
from pygame.locals import *


class FramerateSlider(UiSlider):
    def __init__(self, callback: SliderCallback) -> None:
        super().__init__('Framerate', callback, 30, 122)

    def draw_and_call(self, surf: Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        number = 'Unlimited' if self.value > 120 else str(self.value)
        return self.draw_and_call_text(surf, at, preseed, released, f'Framerate: {number}')


class OptionsMenu(Ui):
    fullscreen_toggle: UiToggleButton
    framerate_slider: UiSlider

    def __init__(self) -> None:
        self.fullscreen_toggle = UiToggleButton('Fullscreen', self.fullscreen_toggle_cb)
        self.framerate_slider = FramerateSlider(self.framerate_slider_cb)
        super().__init__([
            UiLabel('Options'),
            self.fullscreen_toggle,
            self.framerate_slider,
            UiButton('Back', self.close_option_menu),
        ])

    def draw_and_call(self, surf: Surface):
        self.fullscreen_toggle.toggled = globals.fullscreen
        framerate = globals.config.config['max_framerate']
        self.framerate_slider.value = 121 if framerate == 0 else framerate
        return super().draw_and_call(surf)

    def close_option_menu(self) -> None:
        self.close()

    def fullscreen_toggle_cb(self, fullscreen: bool) -> None:
        globals.fullscreen = fullscreen

    def framerate_slider_cb(self, value: int) -> None:
        globals.config.config['max_framerate'] = 0 if value > 120 else value
