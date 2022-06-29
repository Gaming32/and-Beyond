import time
from typing import Optional

from pygame.rect import Rect
from pygame.surface import Surface

from and_beyond.chat import ChatMessage
from and_beyond.client import globals
from and_beyond.client.assets import CHAT_FONT
from and_beyond.client.consts import CHAT_DISPLAY_TIME
from and_beyond.text import MaybeText


class ClientChatMessage(ChatMessage):
    message_render: Surface
    dirty: bool

    def __init__(self, message: MaybeText, at: Optional[float] = None) -> None:
        super().__init__(message, at)
        self.dirty = True

    def render(self) -> Surface:
        if self.dirty:
            self.message_render = CHAT_FONT.render(str(self.message), True, (255, 255, 255))
        return self.message_render


class ChatClient:
    messages: list[ClientChatMessage]
    dirty: bool
    screen_render: Surface
    last_size: tuple[int, int]
    last_render_full: bool
    max_width: int
    chat_y: int
    should_show: bool

    current_chat: str

    def __init__(self) -> None:
        self.messages = []
        self.dirty = True
        self.last_size = (0, 0)
        self.last_render_full = False
        self.current_chat = ''

    def add_message(self, message: ClientChatMessage) -> None:
        lines = str(message.message).split('\n')
        if len(lines) == 1: # Common case
            self.messages.append(message)
        else:
            for line in lines:
                self.messages.append(ClientChatMessage(line, message.time))
        self.dirty = True

    def clear(self) -> None:
        self.messages.clear()
        self.dirty = True

    def render(self, surf: Surface, full: bool = False) -> None:
        if self.dirty or self.last_size != surf.get_size() or self.last_render_full != full:
            render = Surface(surf.get_size()).convert_alpha()
            render.fill((0, 0, 0, 0))
            if full:
                messages = self.messages + [ClientChatMessage('> ' + self.current_chat, time.time())]
            else:
                messages = self.messages[-(surf.get_height() - 100) // 40:]
            text_renders: list[Surface] = []
            max_width = 0
            for message in reversed(messages):
                if globals.frame_time - message.time > CHAT_DISPLAY_TIME and not full:
                    continue
                text_render = message.render()
                if text_render.get_width() > max_width:
                    max_width = text_render.get_width()
                text_renders.append(text_render)
            self.should_show = bool(text_renders)
            if not self.should_show:
                self.screen_render = render
                self.last_size = surf.get_size()
                self.last_render_full = full
                self.dirty = False
                return
            render_height = text_renders[0].get_height()
            show_renders = text_renders[-((render.get_height() - 35) // render_height):]
            chat_y = 5
            render.fill((0, 0, 0, 192))
            for text_render in reversed(show_renders):
                render.blit(text_render, (10, chat_y))
                chat_y = chat_y + render_height + 10
            self.screen_render = render
            self.last_size = surf.get_size()
            self.last_render_full = full
            self.dirty = False
            self.max_width = max_width
            self.chat_y = chat_y
        if self.should_show:
            surf.blit(self.screen_render, (0, surf.get_height() - self.chat_y - 30), Rect(0, 0, self.max_width + 20, self.chat_y))
