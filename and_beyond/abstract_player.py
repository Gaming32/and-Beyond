import abc
import math
from typing import TYPE_CHECKING

from and_beyond.common import REACH_DISTANCE_SQ
from and_beyond.utils import autoslots

if TYPE_CHECKING:
    from and_beyond.world import AbstractWorld, WorldChunk


@autoslots
class AbstractPlayer(abc.ABC):
    x: float
    y: float
    loaded_chunks: dict[tuple[int, int], 'WorldChunk']
    world: 'AbstractWorld'

    def can_reach(self, x: float, y: float, check_at_self: bool = True) -> bool:
        rel_x = x - self.x
        rel_y = y - self.y
        if rel_x == math.inf or rel_y == math.inf:
            return False
        if check_at_self and abs(rel_x) < 0.79 and abs(rel_y) < 1:
            return False
        dist = rel_x * rel_x + rel_y * rel_y
        return dist <= REACH_DISTANCE_SQ
