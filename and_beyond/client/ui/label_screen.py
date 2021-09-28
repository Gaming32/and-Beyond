import textwrap

from and_beyond.client.ui import Ui, UiButton, UiLabel


class LabelScreen(Ui):
    def __init__(self, text: str, ok_text: str = 'Back') -> None:
        super().__init__([
            UiLabel(textwrap.fill(text, width=90, replace_whitespace=False)),
            UiButton(ok_text, self.close),
        ])
