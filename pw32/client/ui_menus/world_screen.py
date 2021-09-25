import logging
import os
import subprocess
import sys
from pathlib import Path

from pw32.client import globals
from pw32.client.globals import GameStatus
from pw32.client.title import TitleScreen
from pw32.client.ui import Ui, UiButton, UiElement, UiLabel
from pw32.utils import DEBUG

if sys.platform == 'win32':
    import msvcrt

    import _winapi



class WorldScreen(Ui):
    worlds_path: Path

    def __init__(self) -> None:
        super().__init__([
            UiLabel('Select a world')
        ])
        self.worlds_path = Path('worlds')
        worlds: list[Path] = []
        for subdir in self.worlds_path.iterdir():
            if subdir.name.startswith('world'):
                worlds.append(subdir)
        worlds.sort(key=(lambda path: int(path.name.removeprefix('world') or '0')))
        for world in worlds:
            text = f'{world.name.capitalize()}'
            self.elements.append(UiButton(text, (lambda world=world: self.load_world(world.name))))
        world_n = (int(worlds[-1].name.removeprefix('world') or '0') + 1) if worlds else 1
        self.elements.append(UiButton('(New world)', (lambda: self.new_world(world_n))))
        self.elements.append(UiButton('Back', self.close))

    def new_world(self, n: int) -> None:
        self.load_world(f'world{n}')

    def load_world(self, name: str):
        self.close()
        globals.game_status = GameStatus.CONNECTING
        logging.info('Starting singleplayer server')
        globals.connecting_status = 'Starting singleplayer server'
        (r, w) = os.pipe()
        # Thanks to
        # https://www.digitalenginesoftware.com/blog/archives/47-Passing-pipes-to-subprocesses-in-Python-in-Windows.html
        # for teaching how to work with subprocess pipes on Windows :)
        if sys.platform == 'win32':
            curproc = _winapi.GetCurrentProcess()
            rh = msvcrt.get_osfhandle(r)
            rih = _winapi.DuplicateHandle(curproc, rh, curproc, 0, True, _winapi.DUPLICATE_SAME_ACCESS)
            pipe = rih
            globals.singleplayer_pipe_ih = rih
            os.close(r)
        else:
            os.set_inheritable(r, True)
            pipe = r
        globals.singleplayer_pipe = os.fdopen(w, 'wb')
        server_args = [sys.executable, '-m', 'pw32.server', '--singleplayer', str(pipe), '--world', name]
        if DEBUG:
            server_args.append('--debug')
        globals.singleplayer_popen = subprocess.Popen(server_args, close_fds=False)
        TitleScreen.load_multiplayer('localhost')
