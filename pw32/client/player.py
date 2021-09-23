# pyright: reportWildcardImportFromLibrary=false
import math as pymath
from math import inf

import pygame
from pw32.abstract_player import AbstractPlayer
from pw32.client import globals
from pw32.client.consts import BLOCK_RENDER_SIZE
from pw32.client.utils import world_to_screen
from pw32.utils import autoslots
from pygame import *
from pygame.locals import *


@autoslots
class ClientPlayer(AbstractPlayer):
    last_x: float
    last_y: float
    render_x: float
    render_y: float
    is_local: bool

    def __init__(self) -> None:
        self.x = inf
        self.y = inf
        self.last_x = inf
        self.last_y = inf
        self.is_local = True
        # We know better than https://mypy.readthedocs.io/en/latest/generics.html#variance-of-generic-types here :)
        self.loaded_chunks = globals.local_world.loaded_chunks # type: ignore

    def render(self, surf: Surface) -> None:
        if self.x == inf or self.y == inf:
            return
        if self.is_local:
            self._render_local()
        else:
            self._render_other()
        draw_pos = world_to_screen(self.render_x, self.render_y + 1, surf)
        surf.fill((128, 0, 128), Rect(draw_pos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE * 2)))

    def _render_local(self) -> None:
        return self._render_other() # Temporary solution
        if self.last_x == inf or pymath.isclose(self.render_x, self.x):
            self.last_x = self.render_x = self.x
        else:
            self.render_x += (self.x - self.last_x) * globals.delta
        if self.last_y == inf or pymath.isclose(self.render_y, self.y):
            self.last_y = self.render_y = self.y
        else:
            self.render_y += (self.y - self.last_y) * globals.delta

    def _render_other(self) -> None:
        self.render_x = self.x
        self.render_y = self.y
        # if self.last_x == inf or pymath.isclose(self.render_x, self.x):
        #     self.last_x = self.render_x = self.x
        # else:
        #     self.render_x += (self.x - self.last_x) * globals.delta
        # if self.last_y == inf or pymath.isclose(self.render_y, self.y):
        #     self.last_y = self.render_y = self.y
        # else:
        #     self.render_y += (self.y - self.last_y) * globals.delta
