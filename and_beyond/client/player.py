# pyright: reportWildcardImportFromLibrary=false
import math as pymath
from math import inf

import pygame
import pygame.time
from and_beyond.abstract_player import AbstractPlayer
from and_beyond.client import globals
from and_beyond.client.assets import PERSON_SPRITES
from and_beyond.client.consts import BLOCK_RENDER_SIZE
from and_beyond.client.utils import lerp, world_to_screen
from and_beyond.packet import (AddVelocityPacket, ChunkUpdatePacket,
                               PlayerPositionPacket)
from and_beyond.utils import autoslots
from and_beyond.world import BlockTypes
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
        self.render_x = inf
        self.render_y = inf
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
        globals.camera = Vector2(self.render_x, self.render_y + 3)
        draw_pos = world_to_screen(self.render_x, self.render_y + 1, surf)
        # image = PERSON_SPRITES[(pygame.time.get_ticks() // 200) & 1]
        # surf.blit(image, Rect((draw_pos.x, draw_pos.y + BLOCK_RENDER_SIZE / 2), (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE * 2)))
        surf.fill((128, 0, 128), Rect(draw_pos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE * 2)))

    def _render_local(self) -> None:
        # return self._render_other() # Temporary solution
        if self.render_x == inf or pymath.isclose(self.render_x, self.x):
            self.render_x = self.x
        else:
            self.render_x = lerp(self.render_x, self.x, 0.5)
        if self.render_y == inf or pymath.isclose(self.render_y, self.y, abs_tol=0.1):
            self.last_y = self.render_y = self.y
        else:
            self.render_y = lerp(self.render_y, self.y, 0.5)

    def _render_other(self) -> None:
        self.render_x = self.x
        self.render_y = self.y

    def send_position(self) -> None:
        packet = PlayerPositionPacket(self.x, self.y)
        assert globals.game_connection is not None
        globals.game_connection.write_packet_sync(packet)

    def add_velocity(self, x: float = 0, y: float = 0) -> None:
        packet = AddVelocityPacket(x, y)
        assert globals.game_connection is not None
        globals.game_connection.write_packet_sync(packet)

    def set_block(self, cx: int, cy: int, bx: int, by: int, block: BlockTypes) -> None:
        if (chunk := globals.local_world.loaded_chunks.get((cx, cy))) is not None:
            chunk.set_tile_type(bx, by, block)
            chunk.dirty = True
        packet = ChunkUpdatePacket(cx, cy, bx, by, block)
        assert globals.game_connection is not None
        globals.game_connection.write_packet_sync(packet)
