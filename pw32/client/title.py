# pyright: reportWildcardImportFromLibrary=false
import os
import subprocess
import sys
from typing import Callable

from pw32.utils import DEBUG

if sys.platform == 'win32':
    import msvcrt
    import _winapi # type: ignore

import pygame
from pw32.client import button_ui, globals
from pygame import *
from pygame.locals import *


class TitleScreen:
    buttons: button_ui.Buttons

    def __init__(self) -> None:
        self.buttons = [
            ('Singleplayer', self.singleplayer),
            ('Multiplayer', self.multiplayer),
            # ('Options', self.show_options),
            ('Quit', self.quit),
        ]

    def render(self, surf: Surface) -> None:
        surf.fill((0, 0, 0))
        button_ui.draw_buttons_and_call(surf, self.buttons)

    def singleplayer(self) -> None:
        globals.at_title = False
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
        else:
            os.set_inheritable(r, True)
            pipe = r
        os.close(r)
        globals.singleplayer_pipe = os.fdopen(w, 'wb')
        server_args = [sys.executable, '-m', 'pw32.server', '--singleplayer', str(pipe)]
        if DEBUG:
            server_args.append('--debug')
        subprocess.Popen(server_args, close_fds=False)

    def multiplayer(self) -> None:
        globals.at_title = False

    def load_multiplayer(self, server):
        pass
    
    def quit(self) -> None:
        globals.running = False
