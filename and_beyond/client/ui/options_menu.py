from typing import Any

from pygame import *
from pygame.locals import *

from and_beyond.client import globals
from and_beyond.client.ui import SliderCallback, Ui, UiButton, UiLabel, UiSlider, UiToggleButton


class FramerateSlider(UiSlider):
    def __init__(self, callback: SliderCallback) -> None:
        super().__init__('Framerate', callback, 30, 122)

    def draw_and_call(self, surf: Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        number = 'Unlimited' if self.value > 120 else str(self.value)
        return self.draw_and_call_text(surf, at, preseed, released, f'Framerate: {number}')


class OptionsMenu(Ui):
    fullscreen_toggle: UiToggleButton
    framerate_slider: UiSlider
    fps_toggle: UiToggleButton
    volume_slider: UiSlider

    def __init__(self) -> None:
        self.fullscreen_toggle = UiToggleButton('Fullscreen', self.fullscreen_toggle_cb)
        self.framerate_slider = FramerateSlider(self.framerate_slider_cb)
        self.fps_toggle = UiToggleButton('Always Show FPS', self.fps_toggle_cb)
        self.volume_slider = UiSlider('Volume', self.volume_slider_cb, 0, 101)
        super().__init__([
            UiLabel('Options'),
            self.fullscreen_toggle,
            self.framerate_slider,
            self.fps_toggle,
            self.volume_slider,
            UiButton('Back', self.close_option_menu),
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
