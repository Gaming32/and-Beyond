import math

from pw32.abstract_player import AbstractPlayer
from pw32.common import GRAVITY
from pw32.utils import autoslots
from pw32.world import BlockTypes

EPSILON = 0.001


@autoslots
class PlayerPhysics:
    x_velocity: float
    y_velocity: float
    player: AbstractPlayer
    dirty: bool

    fix_dx: float
    fix_dy: float
    sequential_fixes: int

    def __init__(self, player: AbstractPlayer) -> None:
        self.x_velocity = 0
        self.y_velocity = 0
        self.player = player
        self.dirty = True
        self.sequential_fixes = 0

    def tick(self, delta: float) -> None:
        old_x = self.player.x
        old_y = self.player.y
        self.y_velocity += GRAVITY * delta
        if self.x_velocity > 0.1 or self.x_velocity < -0.1:
            self.x_velocity *= 0.7
        else:
            self.x_velocity = 0
        self.player.x += self.x_velocity
        if self.fix_collision_in_direction(self.x_velocity, 0):
            self.x_velocity = 0
        self.player.y += self.y_velocity
        if self.fix_collision_in_direction(0, self.y_velocity):
            self.y_velocity = 0
        if self.y_velocity < -4:
            self.y_velocity = -4
        self.dirty = self.player.y != old_y or self.player.x != old_x

    # Thanks to Griffpatch and his amazing Tile Scrolling Platformer series for this code :)
    def fix_collision_in_direction(self, dx: float, dy: float) -> bool:
        self.fix_dx = dx
        self.fix_dy = dy
        fixes = (
            self.fix_collision_at_point(self.player.x + 0.2, self.player.y - EPSILON),
            self.fix_collision_at_point(self.player.x + 0.2, self.player.y),
            self.fix_collision_at_point(self.player.x + 0.2, self.player.y + 1),
            self.fix_collision_at_point(self.player.x + 0.8, self.player.y - EPSILON),
            self.fix_collision_at_point(self.player.x + 0.8, self.player.y),
            self.fix_collision_at_point(self.player.x + 0.8, self.player.y + 1),
        )
        fix = any(fixes)
        if fix and all(fixes):
            self.sequential_fixes += 1
            if self.sequential_fixes > 30:
                # TODO: (in the far future) apply suffocation damage
                # (not right here in the code, but this is a good place to say it)
                x = math.floor(self.player.x)
                y = math.floor(self.player.y)
                i = 0
                for i in range(128):
                    y += 2
                    self.player.y += 2
                    if self._get_tile_type(x, y) == BlockTypes.AIR:
                        break
                if i < 127:
                    self.sequential_fixes = 0
        else:
            self.sequential_fixes = 0
        return fix

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
            if tile == BlockTypes.AIR:
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

    def _get_tile_type(self, x: int, y: int) -> BlockTypes:
        cx = x >> 4
        cy = y >> 4
        bx = x - (cx << 4)
        by = y - (cy << 4)
        cpos = (cx, cy)
        if cpos in self.player.loaded_chunks:
            return self.player.loaded_chunks[cpos].get_tile_type(bx, by)
        return BlockTypes.STONE # If we get in an unloaded chunk (assume solid)
