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
