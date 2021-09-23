import abc

from pw32.common import REACH_DISTANCE_SQ
from pw32.utils import autoslots
from pw32.world import WorldChunk


@autoslots
class AbstractPlayer(abc.ABC):
    x: float
    y: float
    loaded_chunks: dict[tuple[int, int], WorldChunk]

    def can_reach(self, x: float, y: float) -> bool:
        rel_x = x - self.x
        rel_y = y - self.y
        dist = rel_x * rel_x + rel_y * rel_y
        return dist <= REACH_DISTANCE_SQ
