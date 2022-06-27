import abc
import math
from typing import TYPE_CHECKING

from and_beyond.common import REACH_DISTANCE_SQ
from and_beyond.utils import autoslots

if TYPE_CHECKING:
    from and_beyond.physics import PlayerPhysics
    from and_beyond.world import AbstractWorld, WorldChunk


@autoslots
class AbstractPlayer(abc.ABC):
    x: float
    y: float
    loaded_chunks: dict[tuple[int, int], 'WorldChunk']
    world: 'AbstractWorld'
    physics: 'PlayerPhysics'

    def can_reach(self, x: float, y: float, for_place: bool) -> bool:
        rel_x = x - self.x
        rel_y = y - self.y
        if rel_x == math.inf or rel_y == math.inf:
            return False
        if for_place and self.physics.offset_bb.expand(0.15).contains_point(x, y):
            return False
        dist = rel_x * rel_x + rel_y * rel_y
        return dist <= REACH_DISTANCE_SQ
