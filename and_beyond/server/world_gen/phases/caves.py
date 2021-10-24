import random
from typing import TYPE_CHECKING

from and_beyond.server.world_gen.phase import AbstractPhase
from and_beyond.utils import autoslots
from and_beyond.world import BlockTypes, WorldChunk
from opensimplex import OpenSimplex

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

BOUND = 0.2
X_SCALE = 50
Y_SCALE = 50
Y_OFFSET = 0
OCTAVES = 3


@autoslots
class CavePhase(AbstractPhase):
    simplex: OpenSimplex

    def __init__(self, generator: 'WorldGenerator') -> None:
        super().__init__(generator)
        self.simplex = OpenSimplex(generator.seed)

    def noise(self, x: float, y: float) -> float:
        return sum(self.simplex.noise2d(2 ** i * x, 2 ** i * y) ** 2 for i in range(OCTAVES))

    def generate_chunk(self, chunk: 'WorldChunk') -> None:
        if chunk.abs_y > -5:
            return
        cx = chunk.abs_x << 4
        cy = chunk.abs_y << 4
        rand = random.Random((((self.generator.seed << 32) + chunk.abs_x) << 32) + chunk.abs_y)
        for x in range(16):
            for y in range(16):
                old_block = chunk.get_tile_type(x, y)
                if old_block == BlockTypes.AIR:
                    continue
                if old_block in (BlockTypes.DIRT, BlockTypes.GRASS) and rand.random() < 0.1:
                    continue
                abs_x = cx + x
                abs_y = cy + y
                noise = self.noise(abs_x / X_SCALE, abs_y / Y_SCALE) + Y_OFFSET
                if noise > BOUND:
                    continue
                chunk.set_tile_type(x, y, BlockTypes.AIR)


def test() -> None:
    from types import SimpleNamespace

    from PIL import Image

    im = Image.new('L', (2048, 20148))
    ns = SimpleNamespace(simplex=OpenSimplex(1632267049575376200))

    for x in range(-256, 256):
        for y in range(-256, 256):
            noise = CavePhase.noise(ns, x / X_SCALE, y / Y_SCALE) + Y_OFFSET # type: ignore
            im.putpixel((x + 256, y + 256), int(noise * 256))

    im.save(f'test{X_SCALE}_{Y_SCALE}_{OCTAVES}_1.png')


if __name__ == '__main__':
    test()
