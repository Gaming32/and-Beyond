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

DEFAULT_ELEMENT_WIDTH = 350
DEFAULT_ELEMENT_HEIGHT = 50

ELEMENT_Y_PADDING = 25

ButtonCallback = Callable[[], Any]
ToggleButtonCallback = Callable[[bool], Any]
SliderCallback = Callable[[int], Any]
TextInputCallback = Callable[[str], Any]


class UiElement(abc.ABC):
    hidden: bool = False

    def __init__(self) -> None:
        pass

    def get_height(self) -> float:
        return DEFAULT_ELEMENT_HEIGHT

    @abc.abstractmethod
    def draw_and_call(self, surf: pygame.surface.Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        pass


class UiLabel(UiElement):
    _lines: list[str]
    _text: str

    def __init__(self, text: str) -> None:
        self.text = text

    def get_height(self) -> float:
        return (40 * len(self._lines) + 10) if self._lines else 0

    def draw_and_call(self, surf: Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        y_offset = self.get_height() - len(self._lines) * 40
        area = Rect(at, (DEFAULT_ELEMENT_WIDTH, DEFAULT_ELEMENT_HEIGHT))
        for line in self._lines:
            text_render = GAME_FONT.render(line, True, UI_FG)
            surf.blit(
                text_render,
                (
                    area.x + area.width // 2 - text_render.get_width() // 2,
                    area.y + y_offset + area.height // 2 - text_render.get_height() // 2,
                )
            )
            y_offset += 40

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, text: str) -> None:
        self._text = text
        self._lines = text.split('\n')


class UiTextInput(UiElement):
    text: str
    callback: TextInputCallback
    selected: bool
    width: int
    show_time: float
    mask: Optional[str]
    placeholder: str

    def __init__(self, update_cb: TextInputCallback, default_text: str = '', mask: Optional[str] = None, placeholder: str = '') -> None:
        self.text = default_text
        self.callback = update_cb
        self.selected = False
        self.width = DEFAULT_ELEMENT_WIDTH
        self.show_time = 0
        self.mask = mask
        self.placeholder = placeholder

    def draw_and_call(self, surf: Surface, at: Vector2, pressed: list[bool], released: list[bool]) -> Any:
        self.show_time += globals.delta
        text = self.text if self.mask is None else (self.mask * len(self.text))
        if not text:
            text = self.placeholder
            placeholder = True
        else:
            placeholder = False
        text_render = GAME_FONT.render(text, True, UI_FG)
        if text_render.get_width() > self.width - 20 or (text_render.get_width() < self.width - 20 and self.width > DEFAULT_ELEMENT_WIDTH):
            self.width = max(text_render.get_width() + 20, DEFAULT_ELEMENT_WIDTH)
        area = Rect(at + Vector2(DEFAULT_ELEMENT_WIDTH // 2 - self.width // 2, 0), (self.width, DEFAULT_ELEMENT_HEIGHT))
        pygame.draw.rect(surf, UI_BG, area, 0, 5)
        if pressed[0]:
            if area.collidepoint(globals.mouse_screen): # type: ignore
                self.selected = True
            else:
                self.selected = False
        changed = False
        if self.selected:
            for event in globals.events:
                if event.type == pygame.TEXTINPUT:
                    self.text += event.text
                    changed = True
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        if self.text:
                            if event.mod & pygame.KMOD_CTRL:
                                pos = self.text.rfind(' ')
                                if pos == -1:
                                    pos = 1
                                self.text = self.text[:pos - 1]
                            else:
                                self.text = self.text[:-1]
                            changed = True
                    elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                        if pygame.scrap.get_init():
                            clip = pygame.scrap.get(SCRAP_TEXT)
                            if clip is not None:
                                assert isinstance(clip, bytes)
                                self.text += clip.rstrip(b'\0').decode('utf-8')
        surf.blit(
            text_render,
            (
                area.x + 10,
                area.y + area.height // 2 - text_render.get_height() // 2,
            )
        )
        if self.selected and (int(self.show_time * 2) & 1):
            render_width = 0 if placeholder else text_render.get_width()
            surf.fill(UI_FG, (area.x + render_width + 10, area.y + 10, 3, area.height - 20))
        if changed:
            self.callback(self.text)


class UiButton(UiElement):
    label: str
    callback: ButtonCallback

    def __init__(self, label: str, callback: ButtonCallback) -> None:
        self.label = label
        self.callback = callback

    def draw_and_call(self, surf: Surface, at: Vector2, pressed: list[bool], released: list[bool]) -> Any:
        area = Rect(at, (DEFAULT_ELEMENT_WIDTH, DEFAULT_ELEMENT_HEIGHT))
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

    def __init__(self, label: str, callback: SliderCallback, min: int, max: int, value: Optional[int] = None) -> None:
        if value is None:
            value = min
        self.label = label
        self.min = min
        self.max = max
        self.value = value
        self.callback = callback

    def draw_and_call_text(self, surf: Surface, at: Vector2, pressed: list[bool], released: list[bool], text: str) -> Any:
        area = Rect(at, (DEFAULT_ELEMENT_WIDTH, DEFAULT_ELEMENT_HEIGHT))
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
        surf.fill(UI_FG, Rect(area.x + self._value_to_screen() - 2, area.y, 5, DEFAULT_ELEMENT_HEIGHT))

    def draw_and_call(self, surf: Surface, at: Vector2, preseed: list[bool], released: list[bool]) -> Any:
        return self.draw_and_call_text(surf, at, preseed, released, f'{self.label}: {self.value}')

    def _map_01(self) -> float:
        return (self.value - self.min) / (self.max - self.min)

    def _value_to_screen(self) -> int:
        return int(self._map_01() * DEFAULT_ELEMENT_WIDTH)

    def _screen_to_value(self, screen: int) -> int:
        return int((screen / DEFAULT_ELEMENT_WIDTH) * (self.max - self.min) + self.min)


class Ui:
    parent: Optional['Ui']
    elements: list[UiElement]

    def __init__(self, elements: Optional[list[UiElement]] = None) -> None:
        if elements is None:
            elements = []
        self.parent = None
        self.elements = elements

    def show(self, parent: Optional['Ui'] = None) -> None:
        self.parent = globals.ui_override if parent is None else parent
        globals.ui_override = self

    def close(self) -> None:
        if globals.ui_override is self:
            globals.ui_override = self.parent

    def draw_and_call(self, surf: pygame.surface.Surface) -> None:
        pressed = list(pygame.mouse.get_pressed(5))
        released = globals.released_mouse_buttons

        total_height = sum(e.get_height() + ELEMENT_Y_PADDING for e in self.elements if not e.hidden)
        x = surf.get_width() // 2 - DEFAULT_ELEMENT_WIDTH // 2
        y = surf.get_height() // 2 - total_height // 2

        for element in self.elements:
            if element.hidden:
                continue
            element.draw_and_call(surf, Vector2(x, y), pressed, released)
            y += element.get_height() + ELEMENT_Y_PADDING
