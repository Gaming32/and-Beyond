import enum
import json
import logging
import subprocess
import sys
import uuid as _uuid
from typing import TYPE_CHECKING, BinaryIO, Optional, TypedDict

from and_beyond.pipe_commands import PipeCommandsToServer, write_pipe
from pygame import Vector2

if TYPE_CHECKING:
    from and_beyond.client.chat import ChatClient
    from and_beyond.client.mixer import Mixer
    from and_beyond.client.player import ClientPlayer
    from and_beyond.client.server_connection import ServerConnection
    from and_beyond.client.ui import Ui
    from and_beyond.client.world import ClientWorld
    from pygame.display import _VidInfo
    from pygame.event import Event


class _Config(TypedDict):
    w_width: int
    w_height: int
    fullscreen: bool
    max_framerate: int
    always_show_fps: bool
    volume: float
    last_server: str
    auth_token: Optional[str]
    uuid: Optional[str]
    username: str


class ConfigManager:
    config: _Config
    _uuid_cache: Optional[_uuid.UUID]

    def __init__(self, winfo: '_VidInfo') -> None:
        logging.info('Loading config...')
        self.load_default_config(winfo)
        try:
            with open('config.json', encoding='utf-8') as fp:
                self.config.update(json.load(fp))
        except (OSError, json.JSONDecodeError):
            logging.warn('Unable to load config. Loading default config...', exc_info=True)
        logging.info('Loaded config')
        self._uuid_cache = None

    def load_default_config(self, winfo: '_VidInfo') -> None:
        self.config = {
            'w_width': winfo.current_w // 2,
            'w_height': winfo.current_h // 2,
            'fullscreen': False,
            'max_framerate': 75,
            'always_show_fps': False,
            'volume': 1.0,
            'last_server': 'mc.jemnetworks.com',
            'auth_token': None,
            'uuid': None,
            'username': 'Player',
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

    @property
    def uuid(self) -> Optional[_uuid.UUID]:
        if self._uuid_cache is None:
            if self.config['uuid'] is None:
                return None
            self._uuid_cache = _uuid.UUID(self.config['uuid'])
        return self._uuid_cache

    @uuid.setter
    def uuid(self, new: Optional[_uuid.UUID]) -> None:
        self._uuid_cache = new
        if new is None:
            self.config['uuid'] = None
        else:
            self.config['uuid'] = str(new)


def close_singleplayer_server(wait: bool = True):
    global singleplayer_pipe_out, singleplayer_pipe_in, singleplayer_popen
    logging.debug('Checking if singleplayer server needs shutdown...')
    if singleplayer_pipe_out is not None:
        logging.info('Shutting down singleplayer server...')
        write_pipe(singleplayer_pipe_out, PipeCommandsToServer.SHUTDOWN)
        singleplayer_pipe_out.flush()
        singleplayer_pipe_out.close()
        singleplayer_pipe_out = None
    if singleplayer_pipe_in is not None:
        singleplayer_pipe_in.close()
        singleplayer_pipe_in = None
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
mixer: 'Mixer'

fullscreen: bool
w_width: int
w_height: int
delta: float
released_mouse_buttons: list[bool]
events: list['Event']
frame_time: float
frame: int

game_status: GameStatus
game_connection: Optional['ServerConnection'] = None
singleplayer_popen: Optional[subprocess.Popen] = None
singleplayer_pipe_in: Optional[BinaryIO] = None
singleplayer_pipe_out: Optional[BinaryIO] = None
if sys.platform == 'win32':
    singleplayer_pipe_in_ih: int
    singleplayer_pipe_out_ih: int
connecting_status: str = ''

paused: bool = False
ui_override: Optional['Ui'] = None

local_world: 'ClientWorld'
player: 'ClientPlayer'
camera: Vector2 = Vector2()
mouse_screen: Vector2 = Vector2()
mouse_world: tuple[float, float] = (0, 0)
chat_client: 'ChatClient'
