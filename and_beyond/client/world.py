# pyright: reportWildcardImportFromLibrary=false
import math as pymath

import pygame
import pygame.draw
import pygame.mouse
from and_beyond.client import globals
from and_beyond.client.consts import BLOCK_RENDER_SIZE
from and_beyond.client.utils import world_to_screen
from and_beyond.common import MAX_LOADED_CHUNKS
from and_beyond.utils import autoslots
from and_beyond.world import BlockTypes, WorldChunk
from pygame import *
from pygame.locals import *

CHUNK_RENDER_SIZE = BLOCK_RENDER_SIZE * 16


@autoslots
class ClientWorld:
    loaded_chunks: dict[tuple[int, int], 'ClientChunk']

    def __init__(self) -> None:
        self.loaded_chunks = {}

    def load(self) -> None:
        pass

    def unload(self) -> None:
        self.loaded_chunks.clear()

    def tick(self, surf: Surface) -> None:
        if globals.player.y < -80: # or self._is_under_block_in_2_chunks(): # This just looks wrong
            surf.fill((125, 179, 179)) # Darker blue
        else:
            surf.fill((178, 255, 255)) # Sky blue
        render_chunks = self.loaded_chunks.copy()
        half_size = Vector2(surf.get_size()) / 2
        for ((cx, cy), chunk) in render_chunks.items():
            chunk_render = chunk.render()
            rpos = (Vector2(cx, cy + 1) * 16 - globals.camera) * BLOCK_RENDER_SIZE
            rpos += half_size
            rpos.y = surf.get_height() - rpos.y
            surf.blit(chunk_render, chunk_render.get_rect().move(rpos))
        if globals.paused:
            return
        if globals.mouse_world[0] == pymath.inf:
            return
        sel_x = pymath.ceil(globals.mouse_world[0]) - 1
        sel_y = pymath.ceil(globals.mouse_world[1])
        if not globals.player.can_reach(sel_x, sel_y):
            return
        sel_cx = sel_x >> 4
        sel_cy = sel_y >> 4
        sel_chunk = (sel_cx, sel_cy)
        if sel_chunk not in render_chunks:
            return
        sel_bx = sel_x - (sel_cx << 4)
        sel_by = sel_y - (sel_cy << 4)
        pygame.draw.rect(
            surf,
            (0, 0, 0),
            Rect(
                world_to_screen(sel_x, sel_y, surf),
                (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)
            ),
            3
        )
        buttons = pygame.mouse.get_pressed(3)
        if buttons[0]:
            globals.player.set_block(sel_cx, sel_cy, sel_bx, sel_by, BlockTypes.AIR)
        elif buttons[2]:
            globals.player.set_block(sel_cx, sel_cy, sel_bx, sel_by, BlockTypes.STONE)

    def _is_under_block_in_2_chunks(self) -> bool:
        if globals.player.x == pymath.inf or globals.player.y == pymath.inf:
            return False
        x = int(globals.player.x)
        y = int(globals.player.y)
        cx = x >> 4
        cy = y >> 4
        if (cx, cy) not in self.loaded_chunks:
            return False
        chunk = self.loaded_chunks[(cx, cy)]
        bx = x - (cx << 4)
        for by in range(y - (cy << 4), 16):
            block = chunk.get_tile_type(bx, by)
            if block != BlockTypes.AIR:
                return True
        if (cx, cy + 1) not in self.loaded_chunks:
            return False
        chunk = self.loaded_chunks[(cx, cy + 1)]
        for by in range(16):
            block = chunk.get_tile_type(bx, by)
            if block != BlockTypes.AIR:
                return True
        return False


@autoslots
class ClientChunk(WorldChunk):
    dirty: bool
    surf: Surface

    def __init__(self, chunk: WorldChunk) -> None:
        # Copy self
        self.section = chunk.section
        self.x = chunk.x
        self.y = chunk.y
        self.abs_x = chunk.abs_x
        self.abs_y = chunk.abs_y
        self.address = chunk.address
        self.fp = chunk.fp
        self._has_generated = chunk._has_generated
        # Initialization
        self.dirty = True
        self.surf = Surface((CHUNK_RENDER_SIZE, CHUNK_RENDER_SIZE)).convert_alpha() # type: ignore

    def render(self) -> Surface:
        if self.dirty:
           self.surf.fill((0, 0, 0, 0))
           for x in range(16):
                for y in range(16):
                    block = self.get_tile_type(x, y)
                    if block == BlockTypes.AIR:
                        continue
                    elif block == BlockTypes.DIRT:
                        color = (155, 118, 83) # Dirt color
                    elif block == BlockTypes.GRASS:
                        color = (65, 152, 10) # Grass color
                    elif block == BlockTypes.STONE:
                        color = (119, 119, 119) # Stone color
                    rpos = Vector2(x, 15 - y) * BLOCK_RENDER_SIZE
                    self.surf.fill(color, Rect(rpos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)))
           self.dirty = False
        return self.surf