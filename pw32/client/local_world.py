# pyright: reportWildcardImportFromLibrary=false
import pygame
from pw32.client import globals
from pw32.utils import autoslots
from pw32.world import BlockTypes, WorldChunk
from pygame import *
from pygame.locals import *

BLOCK_RENDER_SIZE = 10


@autoslots
class LocalWorld:
    loaded_chunks: dict[tuple[int, int], WorldChunk]
    camera: Vector2
    dirty: bool

    def __init__(self) -> None:
        self.loaded_chunks = {}
        self.camera = Vector2()
        self.dirty = True
    
    def load(self) -> None:
        self.dirty = True
    
    def unload(self) -> None:
        self.loaded_chunks.clear()

    def render(self, surf: Surface) -> None:
        if not self.dirty:
            return
        surf.fill((178, 255, 255)) # Sky blue
        for ((cx, cy), chunk) in self.loaded_chunks.copy().items():
            for bx in range(16):
                for by in range(16):
                    block = chunk.get_tile_type(bx, by)
                    if block == BlockTypes.AIR:
                        continue
                    elif block == BlockTypes.DIRT:
                        color = (155, 118, 83) # Dirt color
                    elif block == BlockTypes.GRASS:
                        color = (65, 152, 10) # Grass color
                    elif block == BlockTypes.STONE:
                        color = (119, 119, 119) # Stone color
                    x = (cx << 4) + bx
                    y = (cy << 4) + by
                    rpos = (Vector2(x, y) - self.camera) * -BLOCK_RENDER_SIZE
                    surf.fill(color, Rect(rpos, rpos + Vector2(BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)))
        self.dirty = False
