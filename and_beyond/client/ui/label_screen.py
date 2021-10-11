import textwrap
from typing import Any, Callable, Optional

from and_beyond.client.ui import Ui, UiButton, UiLabel

CloseCallback = Callable[[], Any]


class LabelScreen(Ui):
    callback: Optional[CloseCallback]

    def __init__(self, text: str, ok_text: str = 'Back', closed_callback: Optional[CloseCallback] = None) -> None:
        super().__init__([
            UiLabel(textwrap.fill(text, width=75, replace_whitespace=False)),
            UiButton(ok_text, self.close),
        ])
        self.callback = closed_callback

    def close(self) -> None:
        super().close()
        if self.callback is not None:
            self.callback()

    @classmethod
    def show_message(cls,
            text: str,
            ok_text: str = 'Back',
            closed_callback: Optional[CloseCallback] = None,
            parent: Optional['Ui'] = None
        ):
        screen = LabelScreen(text, ok_text, closed_callback)
        screen.show(parent)
        return screen
