from collections import ChainMap
import json
import locale
import logging
from typing import MutableMapping, Optional

TranslateMapping = MutableMapping[str, str]

_en_us: Optional[TranslateMapping] = None
_current_language = locale.getdefaultlocale()[0] or 'en_US'
_language_mapping: Optional[TranslateMapping] = None


class Text:
    value: str
    localized: bool

    def __init__(self, value: str, localized: bool = False) -> None:
        self.value = value
        self.localized = localized

    def __str__(self) -> str:
        if self.localized:
            return translate(self.value)
        return self.value

    def formatted(self, *args: str, **kwargs: str) -> str:
        if self.localized:
            return translate_formatted(self.value, *args, **kwargs)
        return self.value.format(*args, **kwargs)

    def __repr__(self) -> str:
        return f'Text({self.value!r}, {self.localized!r})'


def get_current_language() -> str:
    return _current_language


def set_current_language(language: str) -> None:
    global _current_language
    _current_language = language
    _load()


def _load_language_mapping(language: str) -> Optional[TranslateMapping]:
    try:
        with open(f'assets/lang/{language}.json') as f:
            return json.load(f)
    except Exception:
        logging.warning('Failed to load translations for %s', language, exc_info=True)
        return None


def _load() -> None:
    global _en_us, _language_mapping
    if _en_us is None:
        _en_us = _load_language_mapping('en_US') or {}
    if _current_language == 'en_US':
        _language_mapping = _en_us
        return
    current_language = _load_language_mapping(_current_language)
    if current_language is None:
        _language_mapping = _en_us
        return
    _language_mapping = ChainMap(current_language, _en_us)


def translate(key: str) -> str:
    _load()
    assert _language_mapping is not None
    return _language_mapping.get(key, key)


def translate_formatted(key: str, *args: str, **kwargs: str) -> str:
    _load()
    assert _language_mapping is not None
    format_string = _language_mapping.get(key)
    if format_string is None:
        return key
    return format_string.format(*args, **kwargs)


def plain_text(text: str) -> Text:
    return Text(text, False)


def translatable_text(key: str) -> Text:
    return Text(key, True)
