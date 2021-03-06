from typing import TYPE_CHECKING

from and_beyond import blocks
from and_beyond.server.world_gen.perlin import PerlinNoise
from and_beyond.server.world_gen.phase import HeightmappedPhase
from and_beyond.world import WorldChunk

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

OCTAVES = 3
X_SCALE = 150
Y_SCALE = 96
Y_OFFSET = -32


class GroundPhase(HeightmappedPhase):
    perlin: PerlinNoise

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.perlin = PerlinNoise(generator.seed)

    def _get_height(self, x: int, heightmap: str) -> int:
        return int(self.perlin.fbm_1d(x / X_SCALE, OCTAVES) * Y_SCALE + Y_OFFSET)

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        if chunk.abs_y > 6:
            return
        cx = chunk.abs_x << 4
        cy = chunk.abs_y << 4
        for x in range(16):
            abs_x = cx + x
            height = self.get_height(abs_x)
            for y in range(16):
                abs_y = cy + y
                if abs_y > height:
                    type = blocks.AIR
                elif abs_y == height:
                    type = blocks.GRASS
                elif height - abs_y < 4:
                    type = blocks.DIRT
                else:
                    type = blocks.STONE
                chunk.set_tile_type_no_event(x, y, type)
