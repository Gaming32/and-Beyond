import perlin_noise

from pw32.server.world import BlockTypes, WorldChunk
from pw32.utils import autoslots

OCTAVES = 3


@autoslots
class WorldGenerator:
    seed: int
    perlin: perlin_noise.PerlinNoise

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.perlin = perlin_noise.PerlinNoise(OCTAVES, seed)

    def generate_chunk(self, chunk: WorldChunk) -> None:
        cx = chunk.abs_x << 4
        cy = chunk.abs_y << 4
        for x in range(16):
            abs_x = cx + x
            height = int(self.perlin.noise(abs_x) * 96 - 32)
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
