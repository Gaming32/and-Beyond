import math
from typing import TYPE_CHECKING, Optional, Sequence, Union

from and_beyond import blocks
from and_beyond.abstract_player import AbstractPlayer
from and_beyond.common import GRAVITY, TERMINAL_VELOCITY
from and_beyond.utils import autoslots
from and_beyond.world import AbstractWorld

if TYPE_CHECKING:
    import pygame

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

    def __sub__(self, vec: Union[tuple[float, float], Sequence[float]]) -> 'AABB':
        return AABB(self.x1 - vec[0], self.y1 - vec[1], self.x2 - vec[0], self.y2 - vec[1])

    def expand(self, x: float, y: Optional[float] = None) -> 'AABB':
        if y is None:
            y = x
        return AABB(self.x1 - x, self.y1 - y, self.x2 + x, self.y2 + y)

    def intersect(self, other: 'AABB') -> bool:
        return not (self.x2 < other.x1 or other.x2 < self.x1 or self.y2 < other.y1 or other.y2 < self.y1)

    def collides_with_world(self, world: AbstractWorld) -> bool:
        for x_off in range(-2, 3):
            for y_off in range(-2, 3):
                x = int(self.x1) + x_off
                y = int(self.y1) + y_off
                block = world.get_tile_type_or_none(x, y)
                if block is None or block.bounding_box is None:
                    continue
                if self.intersect(block.bounding_box + (x, y)):
                    return True
        return False

    def __repr__(self) -> str:
        return f'AABB({self.x1}, {self.y1}, {self.x2}, {self.y2})'

    def draw_debug(self, surf: 'pygame.surface.Surface') -> None:
        import pygame
        from and_beyond.client.utils import world_to_screen
        pygame.draw.lines(surf, (255, 0, 0), True, [
            world_to_screen(self.x1, self.y1, surf),
            world_to_screen(self.x1, self.y2, surf),
            world_to_screen(self.x2, self.y2, surf),
            world_to_screen(self.x2, self.y1, surf),
        ])


@autoslots
class PlayerPhysics:
    x_velocity: float
    y_velocity: float
    player: AbstractPlayer
    dirty: bool

    fix_dx: float
    fix_dy: float
    air_time: int
    bounding_box: AABB

    def __init__(self, player: AbstractPlayer) -> None:
        self.x_velocity = 0
        self.y_velocity = 0
        self.player = player
        self.dirty = True
        self.sequential_fixes = 0
        self.air_time = 0
        self.bounding_box = AABB(0.2, 0, 0.8, 1.5)

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
        if self.offset_bb.collides_with_world(self.player.world):
            self.player.x -= self.x_velocity
            self.x_velocity = 0
        self.player.y += self.y_velocity
        if self.offset_bb.collides_with_world(self.player.world):
            self.player.y -= self.y_velocity
            self.y_velocity = 0
            self.air_time = 0
        else:
            self.air_time += 1
        if self.y_velocity < TERMINAL_VELOCITY:
            self.y_velocity = TERMINAL_VELOCITY
        self.dirty = self.player.y != old_y or self.player.x != old_x

    @property
    def offset_bb(self) -> AABB:
        return self.bounding_box + (self.player.x, self.player.y)

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

    def get_tile_type(self, x: int, y: int) -> 'blocks.Block':
        cx = x >> 4
        cy = y >> 4
        bx = x - (cx << 4)
        by = y - (cy << 4)
        cpos = (cx, cy)
        if cpos in self.player.loaded_chunks:
            return self.player.loaded_chunks[cpos].get_tile_type(bx, by)
        return blocks.AIR # If we get in an unloaded chunk (assume non-solid)
