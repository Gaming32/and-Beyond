import json
import locale
import logging
import os
from collections import ChainMap
from typing import Any, MutableMapping, Optional, Union, cast

from typing_extensions import Self

from and_beyond.abc import JsonObject, JsonPrimitive, ValidJson
from and_beyond.i18n_data import EN_US

TranslateMapping = MutableMapping[str, str]
MaybeText = Union[str, 'Text']
FormatValueType = Union[JsonPrimitive, 'Text']

_current_language = locale.getdefaultlocale()[0] or 'en_US'
_language_mapping: Optional[TranslateMapping] = None
_available_languages: dict[str, TranslateMapping] = {'en_US': EN_US}
_available_fallback_languages: dict[str, TranslateMapping] = {'en': EN_US}


class Text:
    value: str
    localized: bool
    format_args: tuple[FormatValueType, ...]
    format_kwargs: dict[str, FormatValueType]

    def __init__(self, value: str, localized: bool, *args: FormatValueType, **kwargs: FormatValueType) -> None:
        self.value = value
        self.localized = localized
        self.format_args = args
        self.format_kwargs = kwargs

    def with_format_params(self, *args: FormatValueType, **kwargs: FormatValueType) -> 'Text':
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
        base = ('translatable_text' if self.localized else 'plain_text') + f'({self.value!r}'
        if self.format_args or self.format_kwargs:
            base += ', '
            if self.format_args:
                for format_arg in self.format_args:
                    base += repr(format_arg) + ', '
            if self.format_kwargs:
                for (k, v) in self.format_kwargs.items():
                    base += f'{k}={v!r}, '
            base = base[:-2]
        return base + ')'

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
                result['format_args'] = []
                for format_arg in self.format_args:
                    if isinstance(format_arg, Text):
                        result['format_args'].append(format_arg.to_json())
                    else:
                        result['format_args'].append(format_arg)
            if self.format_kwargs:
                result['format_kwargs'] = {}
                for (key, value) in self.format_kwargs.items():
                    if isinstance(value, Text):
                        result['format_kwargs'][key] = value.to_json()
                    else:
                        result['format_kwargs'][key] = value
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
            format_args: list[FormatValueType] = []
            for format_arg in cast(list[ValidJson], data['format_args']):
                if isinstance(format_arg, dict):
                    format_args.append(Text.from_json(format_arg))
                else:
                    format_args.append(cast(JsonPrimitive, format_arg))
            self.format_args = tuple(format_args)
        else:
            self.format_args = ()
        if 'format_kwargs' in data:
            format_kwargs: dict[str, FormatValueType] = {}
            for (key, value) in cast(JsonObject, data['format_kwargs']).items():
                if isinstance(value, dict):
                    format_kwargs[key] = Text.from_json(value)
                else:
                    format_kwargs[key] = cast(JsonPrimitive, value)
            self.format_kwargs = format_kwargs
        else:
            self.format_kwargs = {}
        return self


def get_current_language() -> str:
    return _current_language


def set_current_language(language: str) -> None:
    global _current_language, _language_mapping
    _current_language = language
    _language_mapping = None # Reset cache


def _get_base_lang(lang: str) -> Optional[str]:
    underscore_index = lang.find('_')
    if underscore_index != -1:
        base_lang = lang[:underscore_index]
        return base_lang
    return None


def get_available_languages() -> dict[str, TranslateMapping]:
    if len(_available_languages) == 1:
        try:
            for lang_file in os.listdir('assets/lang'):
                if not lang_file.lower().endswith('.json') or lang_file.count('_') != 1:
                    continue
                lang_data, lang = _load_language_mapping(lang_file)
                if lang_data is None:
                    continue
                _available_languages[lang] = lang_data
                base_lang = _get_base_lang(lang)
                if base_lang is not None and base_lang not in _available_fallback_languages:
                    _available_fallback_languages[base_lang] = lang_data
        except Exception:
            logging.warning('Failed to load available languages', exc_info=True)
    return _available_languages


def _load_language_mapping(lang_file: str) -> tuple[Optional[TranslateMapping], str]:
    language = os.path.splitext(lang_file)[0]
    try:
        with open(f'assets/lang/{lang_file}') as f:
            return json.load(f), language
    except Exception:
        logging.warning('Failed to load translations for %s', language, exc_info=True)
        return None, language


def _load() -> None:
    global _language_mapping
    if _language_mapping is not None:
        return
    if _current_language == 'en_US':
        _language_mapping = EN_US
        return
    current_language = get_available_languages().get(_current_language)
    if current_language is None:
        base_lang = _get_base_lang(_current_language)
        if base_lang is not None:
            current_language = _available_fallback_languages.get(base_lang)
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


def plain_text(text: str, *args: FormatValueType, **kwargs: FormatValueType) -> Text:
    return Text(text, False, *args, **kwargs)


def translatable_text(key: str, *args: FormatValueType, **kwargs: FormatValueType) -> Text:
    return Text(key, True, *args, **kwargs)


def maybe_text_to_text(text: MaybeText) -> Text:
    if isinstance(text, Text):
        return text
    return Text(text, False)


EMPTY_TEXT = plain_text('')
