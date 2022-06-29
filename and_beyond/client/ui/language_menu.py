from and_beyond import text
from and_beyond.client import globals
from and_beyond.client.ui import Ui, UiButton, UiElement, UiLabel
from and_beyond.text import get_available_languages, translatable_text


class LanguageMenu(Ui):
    current_language_label: UiLabel

    def __init__(self) -> None:
        elements: list[UiElement] = [UiLabel(translatable_text('language_menu.title'))]
        self.current_language_label = UiLabel('')
        self.set_current_language_label(text.get_current_language())
        elements.append(self.current_language_label)
        languages = get_available_languages()
        for lang_name in sorted(languages):
            elements.append(UiButton(
                languages[lang_name].get('language.name', lang_name),
                lambda lang_name=lang_name: self.set_language(lang_name)
            ))
        elements.append(UiButton(translatable_text('ui.back'), self.close))
        super().__init__(elements)

    def set_language(self, language: str) -> None:
        globals.config.config['language'] = language
        text.set_current_language(language)
        self.set_current_language_label(language)

    def set_current_language_label(self, language: str) -> None:
        self.current_language_label.text = text.translate_formatted(
            'language_menu.current_language',
            text.translate(f'language.name')
        )
