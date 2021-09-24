import abc
from typing import TYPE_CHECKING

from pw32.server.world_gen.perlin import PerlinNoise
from pw32.utils import autoslots
from pw32.world import WorldChunk

if TYPE_CHECKING:
    from pw32.server.world_gen.core import WorldGenerator


@autoslots
class AbstractPhase(abc.ABC):
    generator: 'WorldGenerator'

    def __init__(self, generator: 'WorldGenerator') -> None:
        self.generator = generator

    @abc.abstractmethod
    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        raise NotImplementedError
