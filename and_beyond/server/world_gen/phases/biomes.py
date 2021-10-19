from typing import TYPE_CHECKING

from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.utils import autoslots
from and_beyond.world import BiomeTypes, WorldChunk

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

SCALE = 250


def biome_from_val(val: float) -> BiomeTypes:
    if val > 0:
        return BiomeTypes.HILLS
    else:
        return BiomeTypes.PLAINS


def sample_biome_at(x: int, noise: PerlinNoise) -> BiomeTypes:
    return biome_from_val(noise.noise_1d(x / SCALE))


@autoslots
class BiomeTypesPhase(AbstractPhase):
    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        cx = chunk.abs_x << 2
        for x in range(4):
            biome = self.generator.sample_biome_at(cx + x)
            for y in range(4):
                chunk.set_biome_type(x, y, biome)
