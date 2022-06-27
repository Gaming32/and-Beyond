import enum
import json
import logging
import subprocess
import sys
from typing import TYPE_CHECKING, BinaryIO, Optional, TypedDict
from uuid import UUID

from pygame import Vector2

from and_beyond.common import AUTH_SERVER
from and_beyond.http_auth import AuthClient
from and_beyond.pipe_commands import PipeCommandsToServer, write_pipe
from and_beyond.utils import get_opt

if TYPE_CHECKING:
    from pygame.display import _VidInfo
    from pygame.event import Event

    from and_beyond.client.chat import ChatClient
    from and_beyond.client.mixer import Mixer
    from and_beyond.client.player import ClientPlayer
    from and_beyond.client.server_connection import ServerConnection
    from and_beyond.client.ui import Ui
    from and_beyond.client.world import ClientWorld


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
    _uuid_cache: Optional[UUID]

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
            'last_server': '',
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
                json.dump(self.config, fp, indent=2)
        except (OSError, TypeError):
            logging.warn('Unable to save config', exc_info=True)
        else:
            logging.info('Saved config')

    @property
    def uuid(self) -> Optional[UUID]:
        if self._uuid_cache is None:
            if self.config['uuid'] is None:
                return None
            self._uuid_cache = UUID(self.config['uuid'])
        return self._uuid_cache

    @uuid.setter
    def uuid(self, new: Optional[UUID]) -> None:
        self._uuid_cache = new
        if new is None:
            self.config['uuid'] = None
        else:
            self.config['uuid'] = str(new)


def close_singleplayer_server(wait: bool = True) -> None:
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


async def get_auth_client() -> AuthClient:
    "NOTE: Main thread *only*"
    global auth_client
    if auth_client is None:
        auth_client = AuthClient(auth_server, allow_insecure_auth)
    return auth_client


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
all_players: dict[UUID, 'ClientPlayer']
camera: Vector2 = Vector2()
mouse_screen: Vector2 = Vector2()
mouse_world: tuple[float, float] = (0, 0)
chat_client: 'ChatClient'

try:
    auth_server = get_opt('--auth-server')
except (ValueError, IndexError):
    auth_server = AUTH_SERVER
if '://' not in auth_server:
    auth_server = 'http://' + auth_server
allow_insecure_auth = '--insecure-auth' in sys.argv
auth_client: Optional[AuthClient] = None # NOTE: Main thread *only*
