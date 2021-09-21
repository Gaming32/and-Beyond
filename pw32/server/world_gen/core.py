# import perlin_noise

from pw32.server.world_gen.perlin import PerlinNoise
from pw32.utils import autoslots
from pw32.world import BlockTypes, WorldChunk

OCTAVES = 3
X_SCALE = 123.134123
Y_SCALE = 96
Y_OFFSET = -32


@autoslots
class WorldGenerator:
    seed: int
    perlin: PerlinNoise

    def __init__(self, seed: int) -> None:
        self.seed = seed & (2 ** 32 - 1)
        self.perlin = PerlinNoise(seed)

    def generate_chunk(self, chunk: WorldChunk) -> None:
        cx = chunk.abs_x << 4
        cy = chunk.abs_y << 4
        for x in range(16):
            abs_x = cx + x
            height = int(self.perlin.fbm_1d(abs_x / X_SCALE, OCTAVES) * Y_SCALE + Y_OFFSET)
            # height = int(self.perlin.noise(abs_x / X_SCALE) * Y_SCALE + Y_OFFSET)
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
