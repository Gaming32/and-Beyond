import enum
import json
import logging
import subprocess
import sys
from typing import TYPE_CHECKING, BinaryIO, Optional, TypedDict

from and_beyond.client.player import ClientPlayer
from and_beyond.client.world import ClientWorld
from and_beyond.pipe_commands import PipeCommands
from pygame import Vector2

if TYPE_CHECKING:
    from and_beyond.client.server_connection import ServerConnection
    from and_beyond.client.ui import Ui
    from pygame.display import _VidInfo


class _Config(TypedDict):
    w_width: int
    w_height: int
    fullscreen: bool
    max_framerate: int
    always_show_fps: bool


class ConfigManager:
    config: _Config

    def __init__(self, winfo: '_VidInfo') -> None:
        logging.info('Loading config...')
        self.load_default_config(winfo)
        try:
            with open('config.json', encoding='utf-8') as fp:
                self.config.update(json.load(fp))
        except (OSError, json.JSONDecodeError):
            logging.warn('Unable to load config. Loading default config...', exc_info=True)
        logging.info('Loaded config')

    def load_default_config(self, winfo: '_VidInfo') -> None:
        self.config = {
            'w_width': winfo.current_w // 2,
            'w_height': winfo.current_h // 2,
            'fullscreen': False,
            'max_framerate': 75,
            'always_show_fps': False,
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


def close_singleplayer_server(wait: bool = True):
    global singleplayer_pipe, singleplayer_popen
    logging.debug('Checking if singleplayer server needs shutdown...')
    if singleplayer_pipe is not None:
        logging.info('Shutting down singleplayer server...')
        singleplayer_pipe.write(PipeCommands.SHUTDOWN.to_bytes(2, 'little'))
        singleplayer_pipe.flush()
        singleplayer_pipe.close()
        singleplayer_pipe = None
    if wait and singleplayer_popen is not None:
        logging.info('Waiting for singleplayer server to stop...')
        if returncode := singleplayer_popen.wait():
            logging.warn('Singleplayer server stopped with exit code %i', returncode)
        singleplayer_popen = None


class GameStatus(enum.IntEnum):
    MAIN_MENU = 0
    CONNECTING = 1
    STOPPING = 2
    IN_GAME = 3


config: ConfigManager
running: bool
display_info: '_VidInfo'
frame: int

fullscreen: bool
w_width: int
w_height: int
delta: float
released_mouse_buttons: list[bool]

game_status: GameStatus
game_connection: Optional['ServerConnection'] = None
singleplayer_popen: Optional[subprocess.Popen] = None
singleplayer_pipe: Optional[BinaryIO] = None
if sys.platform == 'win32':
    singleplayer_pipe_ih: int
connecting_status: str = ''

paused: bool = False
ui_override: Optional['Ui'] = None

local_world: ClientWorld
player: ClientPlayer
camera: Vector2 = Vector2()
mouse_screen: Vector2 = Vector2()
mouse_world: tuple[float, float] = (0, 0)
