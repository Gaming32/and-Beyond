import math
from typing import Sequence, Union

from and_beyond import blocks
from and_beyond.abstract_player import AbstractPlayer
from and_beyond.common import GRAVITY, TERMINAL_VELOCITY
from and_beyond.utils import autoslots

EPSILON = 0.001


class AABB:
    x1: float
    y1: float
    x2: float
    y2: float

    def __init__(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def __add__(self, vec: Union[tuple[float, float], Sequence[float]]) -> 'AABB':
        return AABB(self.x1 + vec[0], self.y1 + vec[1], self.x2 + vec[0], self.y2 + vec[1])


@autoslots
class PlayerPhysics:
    x_velocity: float
    y_velocity: float
    player: AbstractPlayer
    dirty: bool

    fix_dx: float
    fix_dy: float
    air_time: int

    def __init__(self, player: AbstractPlayer) -> None:
        self.x_velocity = 0
        self.y_velocity = 0
        self.player = player
        self.dirty = True
        self.sequential_fixes = 0
        self.air_time = 0

    def tick(self, delta: float) -> None:
        old_x = self.player.x
        old_y = self.player.y
        if old_x == math.inf or old_y == math.inf:
            return
        self.y_velocity += GRAVITY * delta
        self.x_velocity *= 0.75
        # if self.x_velocity > 0.1 or self.x_velocity < -0.1:
        #     pass # self.x_velocity *= 0.7
        # else:
        #     self.x_velocity = 0
        self.player.x += self.x_velocity
        if self.fix_collision_in_direction(self.x_velocity, 0):
            self.x_velocity = 0
        self.player.y += self.y_velocity
        if self.fix_collision_in_direction(0, self.y_velocity):
            self.y_velocity = 0
            self.air_time = 0
        else:
            self.air_time += 1
        if self.y_velocity < TERMINAL_VELOCITY:
            self.y_velocity = TERMINAL_VELOCITY
        self.dirty = self.player.y != old_y or self.player.x != old_x

    # Thanks to Griffpatch and his amazing Tile Scrolling Platformer series for this code :)
    def fix_collision_in_direction(self, dx: float, dy: float) -> bool:
        self.fix_dx = dx
        self.fix_dy = dy
        return any((
            self.fix_collision_at_point(self.player.x + 0.2, self.player.y - EPSILON),
            self.fix_collision_at_point(self.player.x + 0.2, self.player.y + 0.5),
            self.fix_collision_at_point(self.player.x + 0.2, self.player.y + 1),
            self.fix_collision_at_point(self.player.x + 0.2, self.player.y + 1.5),
            self.fix_collision_at_point(self.player.x + 0.8, self.player.y - EPSILON),
            self.fix_collision_at_point(self.player.x + 0.8, self.player.y + 0.5),
            self.fix_collision_at_point(self.player.x + 0.8, self.player.y + 1),
            self.fix_collision_at_point(self.player.x + 0.8, self.player.y + 1.5),
        ))

    def fix_collision_in_direction_reduced_hitbox(self, dx: float, dy: float) -> bool:
        self.fix_dx = dx
        self.fix_dy = dy
        return any((
            self.fix_collision_at_point(self.player.x + 0.4, self.player.y + 0.2),
            self.fix_collision_at_point(self.player.x + 0.4, self.player.y + 1.3),
            self.fix_collision_at_point(self.player.x + 0.6, self.player.y + 0.2),
            self.fix_collision_at_point(self.player.x + 0.6, self.player.y + 1.3),
        ))

    def fix_collision_at_point(self, x: float, y: float) -> bool:
        ix = math.floor(x)
        iy = math.floor(y)
        cx = ix >> 4
        cy = iy >> 4
        bx = ix - (cx << 4)
        by = iy - (cy << 4)
        cpos = (cx, cy)
        if cpos in self.player.loaded_chunks:
            tile = self.player.loaded_chunks[cpos].get_tile_type(bx, by)
            if tile.bounding_box is None:
                return False
        mx = x - ix
        my = y - iy
        if self.fix_dy < 0:
            self.player.y += 1 - my
        if self.fix_dx < 0:
            self.player.x += 1 - mx
        if self.fix_dy > 0:
            self.player.y -= EPSILON + my
        if self.fix_dx > 0:
            self.player.x -= EPSILON + mx
        return True

    def is_grounded(self) -> bool:
        x = self.player.x
        iy = math.floor(self.player.y - 2 * EPSILON)
        return (
            self.get_tile_type(math.floor(x + 0.2), iy).bounding_box is not None
            or self.get_tile_type(math.floor(x + 0.8), iy).bounding_box is not None
        )

    def get_tile_type(self, x: int, y: int) -> 'blocks.Block':
        cx = x >> 4
        cy = y >> 4
        bx = x - (cx << 4)
        by = y - (cy << 4)
        cpos = (cx, cy)
        if cpos in self.player.loaded_chunks:
            return self.player.loaded_chunks[cpos].get_tile_type(bx, by)
        return blocks.STONE # If we get in an unloaded chunk (assume solid)
