import random
import sys
from typing import TYPE_CHECKING

from and_beyond import blocks
from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import HeightmappedPhase
from and_beyond.world import WorldChunk

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

OCTAVES = 3
X_SCALE_ISLAND = 150
Y_SCALE_ISLAND = 96
Y_OFFSET_ISLAND = 448
X_SCALE_SURFACE = 225
Y_SCALE_SURFACE = 32
Y_OFFSET_SURFACE = 480

ISLAND_HEIGHTMAP = sys.intern('ISLAND')


class SkyIslandsPhase(HeightmappedPhase):
    perlin: PerlinNoise

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        flip = random.Random(generator.seed).randrange(2**30)
        self.perlin = PerlinNoise(generator.seed ^ flip)

    def _get_height(self, x: int, heightmap: str) -> int:
        if heightmap == ISLAND_HEIGHTMAP:
            return int(self.perlin.fbm_1d(x / X_SCALE_ISLAND, OCTAVES) * Y_SCALE_ISLAND)
        return int(self.perlin.noise_1d(x / X_SCALE_SURFACE) * Y_SCALE_SURFACE + Y_OFFSET_SURFACE)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        if chunk.abs_y < 24 or chunk.abs_y > 36:
            return
        cx = chunk.abs_x << 4
        cy = chunk.abs_y << 4
        for x in range(16):
            abs_x = cx + x
            island_height = self.get_height(abs_x, ISLAND_HEIGHTMAP)
            surface_height = self.get_height(abs_x)
            island_height += Y_OFFSET_ISLAND
            if island_height > surface_height:
                continue
            for y in range(16):
                abs_y = cy + y
                if abs_y > surface_height or abs_y < island_height:
                    type = blocks.AIR
                elif abs_y == surface_height:
                    type = blocks.GRASS
                elif surface_height - abs_y < 4:
                    type = blocks.DIRT
                else:
                    type = blocks.STONE
                chunk.set_tile_type_no_event(x, y, type)
