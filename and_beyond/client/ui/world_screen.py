import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

from and_beyond.client import globals
from and_beyond.client.globals import GameStatus
from and_beyond.client.ui import BACK_TEXT, Ui, UiButton, UiLabel
from and_beyond.text import translatable_text
from and_beyond.utils import DEBUG

if sys.platform == 'win32':
    import msvcrt

    import _winapi


class WorldScreen(Ui):
    worlds_path: Path

    def __init__(self) -> None:
        super().__init__([
            UiLabel(translatable_text('singleplayer.title'))
        ])
        self.worlds_path = Path('worlds')
        if self.worlds_path.exists():
            worlds: list[Path] = []
            for subdir in self.worlds_path.iterdir():
                if subdir.name.startswith('world'):
                    worlds.append(subdir)
            worlds.sort(key=(lambda path: int(path.name.removeprefix('world') or '0')))
            for world in worlds:
                text = f'{world.name.capitalize()}'
                self.elements.append(UiButton(text, (lambda world=world: self.load_world(world.name))))
            world_n = (int(worlds[-1].name.removeprefix('world') or '0') + 1) if worlds else 1
        else:
            self.worlds_path.mkdir()
            world_n = 1
        self.elements.extend([
            UiButton(translatable_text('singleplayer.new_world'), (lambda: self.new_world(world_n))),
            UiButton(BACK_TEXT, self.close),
        ])
        if sys.platform == 'win32':
            self.elements.insert(-1, UiButton(
                translatable_text('singleplayer.open_worlds_folder'),
                (lambda: os.startfile('worlds'))
            ))

    def new_world(self, n: int) -> None:
        self.load_world(f'world{n}')

    def load_world(self, name: str) -> None:
        self.close()
        globals.game_status = GameStatus.CONNECTING
        logging.info('Starting singleplayer server')
        globals.connecting_status = translatable_text('connect_status.starting_sp_server')
        (ro, wo) = os.pipe()
        (ri, wi) = os.pipe()
        # Thanks to
        # https://www.digitalenginesoftware.com/blog/archives/47-Passing-pipes-to-subprocesses-in-Python-in-Windows.html
        # for teaching how to work with subprocess pipes on Windows :)
        if sys.platform == 'win32':
            curproc = _winapi.GetCurrentProcess()
            roh = msvcrt.get_osfhandle(ro)
            wih = msvcrt.get_osfhandle(wi)
            roih = _winapi.DuplicateHandle(curproc, roh, curproc, 0, True, _winapi.DUPLICATE_SAME_ACCESS)
            wiih = _winapi.DuplicateHandle(curproc, wih, curproc, 0, True, _winapi.DUPLICATE_SAME_ACCESS)
            pipe_out = roih
            pipe_in = wiih
            globals.singleplayer_pipe_out_ih = roih
            globals.singleplayer_pipe_in_ih = wiih
            os.close(ro)
            os.close(wi)
            rih = msvcrt.get_osfhandle(ri)
            _winapi.SetNamedPipeHandleState(rih, 1, None, None)
        else:
            os.set_inheritable(ro, True)
            os.set_inheritable(wi, True)
            os.set_blocking(ri, False)
            pipe_out = ro
            pipe_in = wi
        globals.singleplayer_pipe_out = os.fdopen(wo, 'wb')
        globals.singleplayer_pipe_in = os.fdopen(ri, 'rb')
        server_args = [
            sys.executable,
            '-m', 'and_beyond.server',
            '--singleplayer', str(pipe_out), str(pipe_in),
            '--world', name,
            '--auth-server', globals.auth_server,
            '--no-optimize',
        ]
        if DEBUG:
            server_args.append('--debug')
        if globals.allow_insecure_auth:
            server_args.append('--insecure-auth')
        env = os.environ.copy()
        import __main__
        if hasattr(__main__, 'GAME_DIR'):
            GAME_DIR = str(__main__.GAME_DIR.absolute())
            if 'PYTHONPATH' in env:
                env['PYTHONPATH'] = str(GAME_DIR) + os.pathsep + env['PYTHONPATH']
            else:
                env['PYTHONPATH'] = str(GAME_DIR)
        logging.debug('Starting singleplayer server with args: %s', shlex.join(server_args))
        globals.singleplayer_popen = subprocess.Popen(server_args, close_fds=False, env=env)
