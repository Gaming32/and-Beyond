# pyright: reportWildcardImportFromLibrary=false
import math as pymath
from math import inf

import pygame
from pw32.client import globals
from pw32.client.consts import BLOCK_RENDER_SIZE
from pw32.utils import autoslots
from pygame import *
from pygame.locals import *


@autoslots
class ClientPlayer:
    x: float
    y: float
    last_x: float
    last_y: float
    render_x: float
    render_y: float

    def __init__(self) -> None:
        self.x = inf
        self.y = inf
        self.last_x = inf
        self.last_y = inf

    def render(self, surf: Surface) -> None:
        if self.x == inf or self.y == inf:
            return
        if self.last_x == inf or pymath.isclose(self.render_x, self.x):
            self.last_x = self.render_x = self.x
        else:
            self.render_x += (self.x - self.last_x) * globals.delta
        if self.last_y == inf or pymath.isclose(self.render_y, self.y):
            self.last_y = self.render_y = self.y
        else:
            self.render_y += (self.y - self.last_y) * globals.delta
        draw_pos = (Vector2(self.render_x, self.render_y + 2) - globals.camera) * BLOCK_RENDER_SIZE
        draw_pos += Vector2(surf.get_size()) / 2
        draw_pos.y = surf.get_height() - draw_pos.y
        surf.fill((128, 0, 128), Rect(draw_pos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE * 2)))
