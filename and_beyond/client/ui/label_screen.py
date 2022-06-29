from typing import Any, Callable, Optional

from and_beyond.client.ui import BACK_TEXT, Ui, UiButton, UiLabel
from and_beyond.text import MaybeText

CloseCallback = Callable[[], Any]


class LabelScreen(Ui):
    callback: Optional[CloseCallback]

    def __init__(self,
        text: MaybeText,
        ok_text: MaybeText = BACK_TEXT,
        closed_callback: Optional[CloseCallback] = None
    ) -> None:
        super().__init__([
            UiLabel(text, 75),
            UiButton(ok_text, self.close),
        ])
        self.callback = closed_callback

    def close(self) -> None:
        super().close()
        if self.callback is not None:
            self.callback()

    @classmethod
    def show_message(cls,
        text: MaybeText,
        ok_text: MaybeText = BACK_TEXT,
        closed_callback: Optional[CloseCallback] = None,
        parent: Optional['Ui'] = None
    ) -> 'LabelScreen':
        screen = LabelScreen(text, ok_text, closed_callback)
        screen.show(parent)
        return screen
