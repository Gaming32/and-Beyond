import abc
from typing import TYPE_CHECKING

from and_beyond.utils import autoslots

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator
    from and_beyond.world import WorldChunk


@autoslots
class AbstractPhase(abc.ABC):
    generator: 'WorldGenerator'

    def __init__(self, generator: 'WorldGenerator') -> None:
        self.generator = generator

    @abc.abstractmethod
    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        raise NotImplementedError


class HeightmappedPhase(AbstractPhase):
    heightmap_cache: dict[int, int]

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.heightmap_cache = {}

    @abc.abstractmethod
    def _get_height(self, x: int) -> int:
        raise NotImplementedError

    def get_height(self, x: int) -> int:
        height = self.heightmap_cache.get(x)
        if height is None:
            height = self._get_height(x)
            self.heightmap_cache[x] = height
        return height
