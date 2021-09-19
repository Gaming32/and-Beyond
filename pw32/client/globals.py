import json
import logging
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from pygame.display import _VidInfo


class _Config(TypedDict):
    w_width: int
    w_height: int
    fullscreen: bool


class ConfigManager:
    config: _Config

    def __init__(self, winfo: '_VidInfo') -> None:
        logging.info('Loading config...')
        try:
            with open('config.json', encoding='utf-8') as fp:
                self.config = json.load(fp)
        except (OSError, json.JSONDecodeError):
            logging.warn('Unable to load config. Loading default config...', exc_info=True)
            self.load_default_config(winfo)
        logging.info('Loaded config')

    def load_default_config(self, winfo: '_VidInfo') -> None:
        self.config = {
            'w_width': winfo.current_w // 2,
            'w_height': winfo.current_h // 2,
            'fullscreen': False,
        }

    def save(self) -> None:
        logging.info('Saving config...')
        try:
            with open('config.json', 'w', encoding='utf-8') as fp:
                json.dump(self.config, fp)
        except (OSError, TypeError):
            logging.warn('Unable to save config', exc_info=True)
        else:
            logging.info('Saved config')


config: ConfigManager
running: bool

fullscreen: bool
w_width: int
w_height: int
