import abc
import sys
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator
    from and_beyond.world import WorldChunk

DEFAULT_HEIGHTMAP = sys.intern('DEFAULT')


class AbstractPhase(abc.ABC):
    generator: 'WorldGenerator'

    def __init__(self, generator: 'WorldGenerator') -> None:
        self.generator = generator

    @abc.abstractmethod
    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        raise NotImplementedError


class HeightmappedPhase(AbstractPhase):
    heightmaps: dict[str, dict[int, int]]

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.heightmaps = {DEFAULT_HEIGHTMAP: {}}

    @abc.abstractmethod
    def _get_height(self, x: int, heightmap: str) -> int:
        raise NotImplementedError

    def get_height(self, x: int, heightmap_name: str = DEFAULT_HEIGHTMAP) -> int:
        heightmap = self.heightmaps.setdefault(heightmap_name, {})
        height = heightmap.get(x)
        if height is None:
            height = self._get_height(x, heightmap_name)
            heightmap[x] = height
        return height
