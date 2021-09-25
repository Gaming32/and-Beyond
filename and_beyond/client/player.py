# pyright: reportWildcardImportFromLibrary=false
import math as pymath
from math import inf

import pygame
from and_beyond.abstract_player import AbstractPlayer
from and_beyond.client import globals
from and_beyond.client.consts import BLOCK_RENDER_SIZE
from and_beyond.client.utils import world_to_screen
from and_beyond.packet import (AddVelocityPacket, ChunkUpdatePacket,
                               PlayerPositionPacket)
from and_beyond.physics import PlayerPhysics
from and_beyond.utils import autoslots
from and_beyond.world import BlockTypes
from pygame import *
from pygame.locals import *

PHYSICS_FPS = 50
PHYSICS_FTIME = 1 / PHYSICS_FPS


@autoslots
class ClientPlayer(AbstractPlayer):
    last_x: float
    last_y: float
    render_x: float
    render_y: float
    is_local: bool
    physics: PlayerPhysics
    physics_time: float

    def __init__(self) -> None:
        self.x = inf
        self.y = inf
        self.last_x = 0
        self.last_y = 0
        self.is_local = True
        # We know better than https://mypy.readthedocs.io/en/latest/generics.html#variance-of-generic-types here :)
        self.loaded_chunks = globals.local_world.loaded_chunks # type: ignore
        self.physics = PlayerPhysics(self)
        self.physics_time = 0

    def render(self, surf: Surface) -> None:
        if self.x == inf or self.y == inf:
            self.x = self.last_x
            self.y = self.last_y
        if self.is_local:
            self._render_local()
        else:
            self._render_other()
        globals.camera = Vector2(self.x, self.y + 3)
        draw_pos = world_to_screen(self.last_x, self.last_y + 1, surf)
        surf.fill((0, 0, 0), Rect(draw_pos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE * 2)))
        draw_pos = world_to_screen(self.render_x, self.render_y + 1, surf)
        surf.fill((128, 0, 128), Rect(draw_pos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE * 2)))

    def _render_local(self) -> None:
        self.physics_time += globals.delta
        while self.physics_time >= PHYSICS_FTIME:
            self.physics.tick(globals.delta)
            self.physics_time -= PHYSICS_FTIME
        self.render_x = self.x
        self.render_y = self.y
        # return self._render_other() # Temporary solution
        # if self.last_x == inf or pymath.isclose(self.render_x, self.x):
        #     self.last_x = self.render_x = self.x
        # else:
        #     self.render_x += (self.x - self.last_x) * globals.delta
        # if self.last_y == inf or pymath.isclose(self.render_y, self.y):
        #     self.last_y = self.render_y = self.y
        # else:
        #     self.render_y += (self.y - self.last_y) * globals.delta

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

    def send_position(self) -> None:
        packet = PlayerPositionPacket(self.x, self.y, self.physics.x_velocity, self.physics.y_velocity)
        assert globals.game_connection is not None
        globals.game_connection.write_packet_sync(packet)

    def add_velocity(self, x: float = 0, y: float = 0) -> None:
        self.physics.x_velocity += x
        self.physics.y_velocity += y
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
