import textwrap

from and_beyond.client.ui import Ui, UiButton, UiElement, UiLabel


class LabelScreen(Ui):
    def __init__(self, text: str, ok_text: str = 'Back') -> None:
        super().__init__(self.get_wrapped_elements(text) + [
            UiButton(ok_text, self.close),
        ])

    def get_wrapped_elements(self, text: str) -> list[UiElement]:
        return [UiLabel(line) for line in textwrap.wrap(text)]
