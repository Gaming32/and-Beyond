import json
import logging
import socket
import subprocess
import sys
from typing import TYPE_CHECKING, Any, BinaryIO, TypedDict

import janus
from pw32.client.server_connection import ServerConnection
from pw32.pipe_commands import PipeCommands
from pw32.world import WorldChunk

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

    def save(self, reassign: bool = True) -> None:
        logging.info('Saving config...')
        if reassign:
            self.config['fullscreen'] = fullscreen
        try:
            with open('config.json', 'w', encoding='utf-8') as fp:
                json.dump(self.config, fp)
        except (OSError, TypeError):
            logging.warn('Unable to save config', exc_info=True)
        else:
            logging.info('Saved config')


def close_singleplayer_server():
    logging.debug('Checking if singleplayer server needs shutdown...')
    if singleplayer_pipe is not None:
        logging.info('Shutting down singleplayer server...')
        singleplayer_pipe.write(PipeCommands.SHUTDOWN.to_bytes(2, 'little'))
        singleplayer_pipe.flush()
        singleplayer_pipe.close()
    if singleplayer_popen is not None:
        logging.info('Waiting for singleplayer server to stop...')
        if returncode := singleplayer_popen.wait():
            logging.warn('Singleplayer server stopped with exit code %i', returncode)


config: ConfigManager
running: bool
display_info: '_VidInfo'

fullscreen: bool
w_width: int
w_height: int

at_title: bool
game_connection: ServerConnection
singleplayer_popen: subprocess.Popen
singleplayer_pipe: BinaryIO
if sys.platform == 'win32':
    singleplayer_pipe_ih: Any

loaded_chunks: dict[tuple[int, int], WorldChunk]
