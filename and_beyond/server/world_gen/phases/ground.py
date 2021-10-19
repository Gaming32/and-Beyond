from typing import TYPE_CHECKING

from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.server.world_gen.phases.biomes import sample_biome_at
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
    ),
    BiomeTypes.PLAINS: (
        3, 225, 32, -32
    ),
}


def lerp(a: float, b: float, f: float) -> float:
    return a + f * (b - a)


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
        last_biome = self.generator.sample_biome_at((cx >> 2) - 1)
        biome = chunk.get_biome_type(0, 0)
        next_biome = chunk.get_biome_type(1, 0)
        for biome_x in range(4):
            if last_biome != biome:
                # Interpolate layer 2
                OCTAVES_LEFT, X_SCALE_LEFT, Y_SCALE_LEFT, Y_OFFSET_LEFT = ARGS_BY_BIOME.get(
                    last_biome, DEFAULT_BIOME
                )
                OCTAVES_RIGHT, X_SCALE_RIGHT, Y_SCALE_RIGHT, Y_OFFSET_RIGHT = ARGS_BY_BIOME.get(
                    biome, DEFAULT_BIOME
                )
                for biome_rel_x in range(4):
                    x = (biome_x << 2) + biome_rel_x
                    abs_x = cx + x
                    height_left = self.perlin.fbm_1d(abs_x / X_SCALE_LEFT, OCTAVES_LEFT) * Y_SCALE_LEFT + Y_OFFSET_LEFT
                    height_right = self.perlin.fbm_1d(abs_x / X_SCALE_RIGHT, OCTAVES_RIGHT) * Y_SCALE_RIGHT + Y_OFFSET_RIGHT
                    self.set_block_column(chunk, x, int(lerp(height_left, height_right, 0.5 + 0.125 * biome_rel_x)))
            elif biome != next_biome:
                # Interpolate layer 1
                OCTAVES_LEFT, X_SCALE_LEFT, Y_SCALE_LEFT, Y_OFFSET_LEFT = ARGS_BY_BIOME.get(
                    biome, DEFAULT_BIOME
                )
                OCTAVES_RIGHT, X_SCALE_RIGHT, Y_SCALE_RIGHT, Y_OFFSET_RIGHT = ARGS_BY_BIOME.get(
                    next_biome, DEFAULT_BIOME
                )
                for biome_rel_x in range(4):
                    x = (biome_x << 2) + biome_rel_x
                    abs_x = cx + x
                    height_left = self.perlin.fbm_1d(abs_x / X_SCALE_LEFT, OCTAVES_LEFT) * Y_SCALE_LEFT + Y_OFFSET_LEFT
                    height_right = self.perlin.fbm_1d(abs_x / X_SCALE_RIGHT, OCTAVES_RIGHT) * Y_SCALE_RIGHT + Y_OFFSET_RIGHT
                    self.set_block_column(chunk, x, int(lerp(height_left, height_right, 0.125 * biome_rel_x)))
            else:
                OCTAVES, X_SCALE, Y_SCALE, Y_OFFSET = ARGS_BY_BIOME.get(
                    biome, DEFAULT_BIOME
                )
                for biome_rel_x in range(4):
                    x = (biome_x << 2) + biome_rel_x
                    abs_x = cx + x
                    height = int(self.perlin.fbm_1d(abs_x / X_SCALE, OCTAVES) * Y_SCALE + Y_OFFSET)
                    self.set_block_column(chunk, x, height)
            last_biome = biome
            biome = next_biome
            if biome_x == 3:
                next_biome = self.generator.sample_biome_at((cx >> 2) + biome_x + 1)
            else:
                next_biome = chunk.get_biome_type(biome_x + 1, 0)

    def set_block_column(self, chunk: 'WorldChunk', x: int, height: int):
        cy = chunk.abs_y << 4
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
