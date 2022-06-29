import random
from typing import TYPE_CHECKING, Union

from and_beyond import blocks
from and_beyond.blocks import Block
from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.utils import autoslots
from and_beyond.world import WorldChunk

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

REQUIREMENT = 0.5
FLIP_CONSTANT = 4009383296558120008
SCALE = 150

_N = None
_L = blocks.LEAVES
_W = blocks.WOOD
TREE: list[list[Union[None, Block]]] = [
    [_N, _N, _L, _N, _N],
    [_N, _L, _L, _L, _N],
    [_L, _L, _W, _L, _L],
    [_N, _N, _W, _N, _N],
    [_N, _N, _W, _N, _N],
]


@autoslots
class TreeDecorationPhase(AbstractPhase):
    perlin: PerlinNoise

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.perlin = PerlinNoise(generator.seed ^ FLIP_CONSTANT)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        if chunk.abs_y > 6:
            return
        cx = chunk.abs_x << 4
        cy = chunk.abs_y << 4
        if self.perlin.noise_1d(cx / SCALE) > REQUIREMENT:
            offset = random.Random(cx ^ FLIP_CONSTANT).randrange(12)
            abs_x = cx + offset
            height = self.generator.ground.get_height(abs_x + 2)
            rel = height - cy + 1
            if -6 < rel < 6 or 10 < rel:
                self.draw(chunk, offset, rel)

    def draw(self, chunk: 'WorldChunk', x: int, y: int) -> None:
        for row in reversed(TREE):
            if y < 0:
                y += 1
                continue
            if y > 15:
                break
            for (off, val) in enumerate(row):
                if val is None:
                    continue
                abs_x = x + off
                if chunk.get_tile_type(abs_x, y) == blocks.AIR:
                    chunk.set_tile_type_no_event(abs_x, y, val)
            y += 1
