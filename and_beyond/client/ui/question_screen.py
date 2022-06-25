import textwrap
from typing import Optional

import pygame
from and_beyond.client import globals
from and_beyond.client.ui import (TextInputCallback, Ui, UiButton, UiLabel,
                                  UiTextInput)
from and_beyond.utils import NO_OP
from pygame import Surface
from pygame.constants import KEYUP


class QuestionScreen(Ui):
    text_input: UiTextInput
    callback: Optional[TextInputCallback]
    allow_cancel: bool

    def __init__(
            self,
            label: str,
            ok_text: str = 'Ok',
            allow_cancel: bool = True,
            cancel_text: str = 'Cancel',
            ok_callback: Optional[TextInputCallback] = None,
            default_text: str = ''
        ) -> None:
        self.text_input = UiTextInput(NO_OP, default_text)
        super().__init__([
            UiLabel(textwrap.fill(label, width=100, replace_whitespace=False)),
            self.text_input,
            UiButton(ok_text, self.done),
        ])
        self.callback = ok_callback
        self.allow_cancel = allow_cancel
        if allow_cancel:
            self.elements.append(UiButton(cancel_text, self.close))

    def draw_and_call(self, surf: Surface) -> None:
        for event in globals.events:
            if event.type == KEYUP:
                if event.key == pygame.K_RETURN:
                    self.done()
                    return
                elif event.key == pygame.K_ESCAPE and self.allow_cancel:
                    self.close()
                    return
        return super().draw_and_call(surf)

    def done(self) -> None:
        self.close()
        if self.callback is not None:
            self.callback(self.text_input.text)
