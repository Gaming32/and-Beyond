from typing import TYPE_CHECKING

from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.utils import autoslots
from and_beyond.world import BlockTypes, WorldChunk

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

FLIP_CONSTANT = 10058735888722539265

OCTAVES = 3
X_SCALE_ISLAND = 150
Y_SCALE_ISLAND = 96
Y_OFFSET_ISLAND = 448
X_SCALE_SURFACE = 225
Y_SCALE_SURFACE = 32
Y_OFFSET_SURFACE = 480


@autoslots
class SkyIslandsPhase(AbstractPhase):
    perlin: PerlinNoise

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.perlin = PerlinNoise(generator.seed ^ FLIP_CONSTANT)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        if chunk.abs_y < 24:
            return
        cx = chunk.abs_x << 4
        cy = chunk.abs_y << 4
        for x in range(16):
            abs_x = cx + x
            island_height = int(self.perlin.fbm_1d(abs_x / X_SCALE_ISLAND, OCTAVES) * Y_SCALE_ISLAND)
            surface_height = int(self.perlin.noise_1d(abs_x / X_SCALE_SURFACE) * Y_SCALE_SURFACE + Y_OFFSET_SURFACE)
            island_height += Y_OFFSET_ISLAND
            if island_height > surface_height:
                continue
            for y in range(16):
                abs_y = cy + y
                if abs_y > surface_height or abs_y < island_height:
                    type = BlockTypes.AIR
                elif abs_y == surface_height:
                    type = BlockTypes.GRASS
                elif surface_height - abs_y < 4:
                    type = BlockTypes.DIRT
                else:
                    type = BlockTypes.STONE
                chunk.set_tile_type(x, y, type)
