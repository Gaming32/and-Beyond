from typing import TYPE_CHECKING

from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.utils import autoslots
from and_beyond.world import BiomeTypes, WorldChunk

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

FLIP_CONSTANT = 8112343193046603085

SCALE = 250


def biome_from_val(val: float) -> BiomeTypes:
    return BiomeTypes.HILLS


@autoslots
class BiomeTypesPhase(AbstractPhase):
    perlin: PerlinNoise

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.perlin = PerlinNoise(generator.seed ^ FLIP_CONSTANT)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        cx = chunk.abs_x << 2
        for x in range(4):
            abs_x = cx + x
            val = self.perlin.noise_1d(abs_x / SCALE)
            biome = biome_from_val(val)
            for y in range(4):
                chunk.set_biome_type(x, y, biome)
