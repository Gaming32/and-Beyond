from typing import Any

from pygame import *
from pygame.locals import *

from and_beyond import text
from and_beyond.client import globals
from and_beyond.client.ui import BACK_TEXT, SliderCallback, Ui, UiButton, UiLabel, UiSlider, UiToggleButton
from and_beyond.text import translatable_text


class FramerateSlider(UiSlider):
    def __init__(self, callback: SliderCallback) -> None:
        super().__init__(translatable_text('options.framerate'), callback, 30, 122)

    def draw_and_call(self, surf: Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        number = text.translate('options.framerate.unlimited') if self.value > 120 else str(self.value)
        # return self.draw_and_call_text(surf, at, preseed, released, f'Framerate: {number}')
        return self.draw_and_call_text(
            surf, at, preseed, released,
            text.translate('options.framerate') + text.translate('ui.option.sep') + number
        )


class OptionsMenu(Ui):
    fullscreen_toggle: UiToggleButton
    framerate_slider: UiSlider
    fps_toggle: UiToggleButton
    volume_slider: UiSlider

    def __init__(self) -> None:
        self.fullscreen_toggle = UiToggleButton(translatable_text('options.fullscreen'), self.fullscreen_toggle_cb)
        self.framerate_slider = FramerateSlider(self.framerate_slider_cb)
        self.fps_toggle = UiToggleButton(translatable_text('options.always_show_fps'), self.fps_toggle_cb)
        self.volume_slider = UiSlider(translatable_text('options.volume'), self.volume_slider_cb, 0, 101)
        super().__init__([
            UiLabel(translatable_text('options.title')),
            self.fullscreen_toggle,
            self.framerate_slider,
            self.fps_toggle,
            self.volume_slider,
            UiButton(BACK_TEXT, self.close_option_menu),
        ])

    def draw_and_call(self, surf: Surface) -> None:
        self.fullscreen_toggle.toggled = globals.fullscreen
        framerate = globals.config.config['max_framerate']
        self.framerate_slider.value = 121 if framerate == 0 else framerate
        self.fps_toggle.toggled = globals.config.config['always_show_fps']
        self.volume_slider.value = int(globals.config.config['volume'] * 100)
        return super().draw_and_call(surf)

    def close_option_menu(self) -> None:
        self.close()

    def fullscreen_toggle_cb(self, fullscreen: bool) -> None:
        globals.fullscreen = fullscreen

    def framerate_slider_cb(self, value: int) -> None:
        globals.config.config['max_framerate'] = 0 if value > 120 else value

    def fps_toggle_cb(self, show: bool) -> None:
        globals.config.config['always_show_fps'] = show

    def volume_slider_cb(self, value: int) -> None:
        volume = value / 100
        globals.config.config['volume'] = volume
        globals.mixer.set_volume(volume)
