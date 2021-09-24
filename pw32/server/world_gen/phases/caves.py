from typing import TYPE_CHECKING

from pw32.server.world_gen.perlin import PerlinNoise
from pw32.server.world_gen.phase import AbstractPhase
from pw32.utils import autoslots
from pw32.world import BlockTypes, WorldChunk

if TYPE_CHECKING:
    from pw32.server.world_gen.core import WorldGenerator

BOUND = 0.5
SCALE = 100
Y_OFFSET = 0


@autoslots
class CavePhase(AbstractPhase):
    perlin: PerlinNoise

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.perlin = PerlinNoise(generator.seed)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        pass
        # cx = chunk.abs_x << 4
        # cy = chunk.abs_y << 4
        # for x in range(16):
        #     abs_x = cx + x
        #     for y in range(16):
        #         abs_y = cy + y
        #         noise = self.perlin.noise_2d(abs_x / SCALE, abs_y / SCALE) + Y_OFFSET
        #         if abs(noise) < BOUND:
        #             continue
        #         chunk.set_tile_type(x, y, BlockTypes.AIR)
