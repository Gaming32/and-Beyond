from typing import TYPE_CHECKING

from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.utils import autoslots
from and_beyond.world import BiomeTypes, BlockTypes, WorldChunk

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

OCTAVES = 3
X_SCALE = 150
Y_SCALE = 96
Y_OFFSET = -32
DEFAULT_BIOME = (OCTAVES, X_SCALE, Y_SCALE, Y_OFFSET)

# OCTAVES, X_SCALE, Y_SCALE, Y_OFFSET
ARGS_BY_BIOME: dict[BiomeTypes, tuple[int, float, float, int]] = {
    BiomeTypes.HILLS: (
        3, 150, 96, -32
    )
}


@autoslots
class GroundPhase(AbstractPhase):
    perlin: PerlinNoise

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.perlin = PerlinNoise(generator.seed)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        if chunk.abs_y > 6:
            return
        cx = chunk.abs_x << 4
        cy = chunk.abs_y << 4
        for biome_x in range(4):
            biome = chunk.get_biome_type(biome_x, 0)
            OCTAVES, X_SCALE, Y_SCALE, Y_OFFSET = ARGS_BY_BIOME.get(
                biome, DEFAULT_BIOME
            )
            for biome_rel_x in range(4):
                x = (biome_x << 2) + biome_rel_x
                abs_x = cx + x
                height = int(self.perlin.fbm_1d(abs_x / X_SCALE, OCTAVES) * Y_SCALE + Y_OFFSET)
                for y in range(16):
                    abs_y = cy + y
                    if abs_y > height:
                        type = BlockTypes.AIR
                    elif abs_y == height:
                        type = BlockTypes.GRASS
                    elif height - abs_y < 4:
                        type = BlockTypes.DIRT
                    else:
                        type = BlockTypes.STONE
                    chunk.set_tile_type(x, y, type)
