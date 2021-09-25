# pyright: reportWildcardImportFromLibrary=false
import abc
from typing import Any, Callable, Optional

import pygame
import pygame.draw
import pygame.font
import pygame.mouse
from and_beyond.client import globals
from and_beyond.client.assets import GAME_FONT
from and_beyond.client.consts import UI_BG, UI_FG
from pygame import *
from pygame.locals import *

BUTTON_WIDTH = 350
BUTTON_HEIGHT = 50

BUTTON_HEIGHT_PAD = BUTTON_HEIGHT + 25

ButtonCallback = Callable[[], Any]
ToggleButtonCallback = Callable[[bool], Any]
SliderCallback = Callable[[int], Any]


class UiElement(abc.ABC):
    def __init__(self) -> None:
        pass

    @abc.abstractmethod
    def draw_and_call(self, surf: Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        pass


class UiLabel(UiElement):
    text: str

    def __init__(self, text: str) -> None:
        self.text = text

    def draw_and_call(self, surf: Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        area = Rect(at, (BUTTON_WIDTH, BUTTON_HEIGHT))
        text_render = GAME_FONT.render(self.text, True, UI_FG)
        surf.blit(
            text_render,
            (
                area.x + area.width // 2 - text_render.get_width() // 2,
                area.y + area.height // 2 - text_render.get_height() // 2,
            )
        )


class UiButton(UiElement):
    label: str
    callback: ButtonCallback

    def __init__(self, label: str, callback: ButtonCallback) -> None:
        self.label = label
        self.callback = callback

    def draw_and_call(self, surf: Surface, at: Vector2, pressed: list[bool], released: list[bool]) -> Any:
        area = Rect(at, (BUTTON_WIDTH, BUTTON_HEIGHT))
        pygame.draw.rect(surf, UI_BG, area, 0, 5)
        text_render = GAME_FONT.render(self.label, True, UI_FG)
        surf.blit(
            text_render,
            (
                area.x + area.width // 2 - text_render.get_width() // 2,
                area.y + area.height // 2 - text_render.get_height() // 2,
            )
        )
        if area.collidepoint(globals.mouse_screen): # type: ignore
            pygame.draw.rect(surf, UI_FG, area, 5, 5)
            if released[0]:
                return self.callback()


class UiToggleButton(UiButton):
    tb_label: str
    tb_callback: ToggleButtonCallback
    _toggled: bool

    def __init__(self, label: str, callback: ToggleButtonCallback, toggled: bool = False) -> None:
        super().__init__(label, self._callback)
        self.tb_label = label
        self.tb_callback = callback
        self.toggled = toggled

    def _set_label(self) -> None:
        label = f'{self.tb_label}: '
        if self._toggled:
            label += ' On'
        else:
            label += ' Off'
        self.label = label

    def _callback(self) -> Any:
        self.toggled = not self.toggled
        return self.tb_callback(self.toggled)

    @property
    def toggled(self) -> bool:
        return self._toggled

    @toggled.setter
    def toggled(self, toggled: bool) -> None:
        self._toggled = toggled
        self._set_label()


class UiSlider(UiElement):
    label: str
    min: int
    max: int
    value: int
    callback: SliderCallback

    def __init__(self, label: str, callback: SliderCallback, min: int, max: int, value: int = None) -> None:
        if value is None:
            value = min
        self.label = label
        self.min = min
        self.max = max
        self.value = value
        self.callback = callback

    def draw_and_call_text(self, surf: Surface, at: Vector2, pressed: list[bool], released: list[bool], text: str) -> Any:
        area = Rect(at, (BUTTON_WIDTH, BUTTON_HEIGHT))
        pygame.draw.rect(surf, UI_BG, area, 0, 5)
        text_render = GAME_FONT.render(text, True, UI_FG)
        surf.blit(
            text_render,
            (
                area.x + area.width // 2 - text_render.get_width() // 2,
                area.y + area.height // 2 - text_render.get_height() // 2,
            )
        )
        if area.collidepoint(globals.mouse_screen): # type: ignore
            pygame.draw.rect(surf, UI_FG, area, 5, 5)
            if pressed[0]:
                self.value = self._screen_to_value(int(globals.mouse_screen.x - area.x))
                self.callback(self.value)
        surf.fill(UI_FG, Rect(area.x + self._value_to_screen() - 2, area.y, 5, BUTTON_HEIGHT))

    def draw_and_call(self, surf: Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        return self.draw_and_call_text(surf, at, preseed, released, f'{self.label}: {self.value}')

    def _map_01(self) -> float:
        return (self.value - self.min) / (self.max - self.min)

    def _value_to_screen(self) -> int:
        return int(self._map_01() * BUTTON_WIDTH)

    def _screen_to_value(self, screen: int) -> int:
        return int((screen / BUTTON_WIDTH) * (self.max - self.min) + self.min)


class Ui:
    parent: Optional['Ui']
    elements: list[UiElement]

    def __init__(self, elements: list[UiElement] = None) -> None:
        if elements is None:
            elements = []
        self.parent = None
        self.elements = elements

    def close(self) -> None:
        if globals.ui_override is self:
            globals.ui_override = self.parent

    def draw_and_call(self, surf: Surface) -> None:
        pressed = list(pygame.mouse.get_pressed(5))
        released = globals.released_mouse_buttons

        x = surf.get_width() // 2 - BUTTON_WIDTH // 2
        y = surf.get_height() // 2 - BUTTON_HEIGHT_PAD * len(self.elements) // 2

        for element in self.elements:
            element.draw_and_call(surf, Vector2(x, y), pressed, released)
            y += BUTTON_HEIGHT_PAD
