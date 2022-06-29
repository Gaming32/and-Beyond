import json
import locale
import logging
from collections import ChainMap
from typing import Any, MutableMapping, Optional, Union, cast

from typing_extensions import Self

from and_beyond.abc import ValidJson
from and_beyond.en_us import EN_US

TranslateMapping = MutableMapping[str, str]
MaybeText = Union[str, 'Text']

_current_language = locale.getdefaultlocale()[0] or 'en_US'
_language_mapping: Optional[TranslateMapping] = None


class Text:
    value: str
    localized: bool
    format_args: tuple[ValidJson, ...]
    format_kwargs: dict[str, ValidJson]

    def __init__(self, value: str, localized: bool) -> None:
        self.value = value
        self.localized = localized
        self.format_args = ()
        self.format_kwargs = {}

    def with_format_params(self, *args: ValidJson, **kwargs: ValidJson) -> 'Text':
        new = Text(self.value, self.localized)
        new.format_args = args
        new.format_kwargs = kwargs
        return new

    def __str__(self) -> str:
        if self.format_args or self.format_kwargs:
            if self.localized:
                return translate_formatted(self.value, *self.format_args, **self.format_kwargs)
            return self.value.format(*self.format_args, **self.format_kwargs)
        if self.localized:
            return translate(self.value)
        return self.value

    def format(self, *args: Any, **kwargs: Any) -> str:
        if self.localized:
            return translate_formatted(self.value, *args, **kwargs)
        return self.value.format(*args, **kwargs)

    def __repr__(self) -> str:
        base = f'Text({self.value!r}, {self.localized!r})'
        if self.format_args or self.format_kwargs:
            base += '.with_format_params('
            if self.format_args:
                base += repr(self.format_args[0])
                for i in range(1, len(self.format_args)):
                    base += ', ' + repr(self.format_args[i])
                if self.format_kwargs:
                    base += ', '
            if self.format_kwargs:
                for (k, v) in self.format_kwargs.items():
                    base += f'{k}={v!r}, '
                base = base[:-2]
            return base + ')'
        return base

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, Text):
            return NotImplemented
        return self.localized == o.localized and self.value == o.value

    def __hash__(self) -> int:
        return hash((self.value, self.localized))

    def to_json(self) -> ValidJson:
        if self.localized or self.format_args or self.format_kwargs:
            result: ValidJson = {
                'value': self.value,
                'localized': self.localized
            }
            if self.format_args:
                result['format_args'] = self.format_args
            if self.format_kwargs:
                result['format_kwargs'] = self.format_kwargs
            return result
        return self.value

    @classmethod
    def from_json(cls, data: ValidJson) -> Self:
        if isinstance(data, str):
            return cls(data, False)
        assert isinstance(data, dict)
        self = cls.__new__(cls)
        self.value = cast(str, data['value'])
        self.localized = cast(bool, data['localized'])
        if 'format_args' in data:
            self.format_args = tuple(cast(list[ValidJson], data['format_args']))
        else:
            self.format_args = ()
        if 'format_kwargs' in data:
            self.format_kwargs = cast(dict[str, ValidJson], data['format_kwargs'])
        else:
            self.format_kwargs = {}
        return self

def get_current_language() -> str:
    return _current_language


def set_current_language(language: str) -> None:
    global _current_language, _language_mapping
    _current_language = language
    _language_mapping = None # Reset cache


def _load_language_mapping(language: str) -> Optional[TranslateMapping]:
    try:
        with open(f'assets/lang/{language}.json') as f:
            return json.load(f)
    except Exception:
        logging.warning('Failed to load translations for %s', language, exc_info=True)
        return None


def _load() -> None:
    global _language_mapping
    if _language_mapping is not None:
        return
    if _current_language == 'en_US':
        _language_mapping = EN_US
        return
    current_language = _load_language_mapping(_current_language)
    if current_language is None:
        _language_mapping = EN_US
        return
    _language_mapping = ChainMap(current_language, EN_US)


def translate(key: str) -> str:
    _load()
    assert _language_mapping is not None
    return _language_mapping.get(key, key)


def translate_formatted(key: str, *args: Any, **kwargs: Any) -> str:
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


def maybe_text_to_text(text: MaybeText) -> Text:
    if isinstance(text, Text):
        return text
    return Text(text, False)
