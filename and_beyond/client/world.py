from functools import lru_cache
import math as pymath
import random
from typing import Optional

import pygame
import pygame.draw
import pygame.mouse
from pygame import *
from pygame.locals import *

from and_beyond import blocks
from and_beyond.blocks import Block
from and_beyond.client import globals
from and_beyond.client.assets import BLOCK_SPRITES, EMPTY_TEXTURE, MISSING_TEXTURE, SELECTED_ITEM_BG
from and_beyond.client.consts import BLOCK_RENDER_SIZE, MAX_RENDER_CHUNKS
from and_beyond.client.utils import world_to_screen
from and_beyond.utils import autoslots
from and_beyond.world import AbstractWorld, WorldChunk

CHUNK_RENDER_SIZE = BLOCK_RENDER_SIZE * 16


@autoslots
class ClientWorld(AbstractWorld):
    loaded_chunks: dict[tuple[int, int], 'ClientChunk']
    chunks_rendered_this_frame: int

    def __init__(self) -> None:
        self.loaded_chunks = {}
        self.chunks_rendered_this_frame = 0

    def load(self) -> None:
        pass

    def unload(self) -> None:
        self.loaded_chunks.clear()

    def tick(self, surf: pygame.surface.Surface) -> None:
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
        surf.blit(SELECTED_ITEM_BG[0], (15, surf.get_height() - 85, 70, 70))
        surf.blit(
            globals.player.selected_block_texture,
            (25, surf.get_height() - 75, 50, 50)
        )
        if globals.paused:
            return
        if globals.mouse_world[0] == pymath.inf:
            return
        sel_x = pymath.ceil(globals.mouse_world[0]) - 1
        sel_y = pymath.ceil(globals.mouse_world[1])
        if not globals.player.can_reach(sel_x, sel_y, None):
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
            2
        )
        buttons = pygame.mouse.get_pressed(3)
        if buttons[0]:
            globals.player.set_block(sel_cx, sel_cy, sel_bx, sel_by, blocks.AIR)
        elif buttons[2] and globals.player.can_reach(
            sel_x, sel_y,
            globals.player.selected_block.bounding_box,
            (player.physics.offset_bb for player in globals.all_players.values())
        ):
            globals.player.set_block(sel_cx, sel_cy, sel_bx, sel_by, globals.player.selected_block)

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
            if block != blocks.AIR:
                return True
        if (cx, cy + 1) not in self.loaded_chunks:
            return False
        chunk = self.loaded_chunks[(cx, cy + 1)]
        for by in range(16):
            block = chunk.get_tile_type(bx, by)
            if block != blocks.AIR:
                return True
        return False

    def get_chunk_or_none(self, x: int, y: int) -> Optional['ClientChunk']:
        return self.loaded_chunks.get((x, y))

    def get_chunk(self, x: int, y: int) -> 'ClientChunk':
        return self.loaded_chunks[(x, y)]


@autoslots
class ClientChunk(WorldChunk):
    redraw: set[tuple[int, int]]
    dirty: bool
    surf: pygame.surface.Surface

    def __init__(self, chunk: WorldChunk) -> None:
        # Copy self
        self.section = chunk.section
        self.x = chunk.x
        self.y = chunk.y
        self.abs_x = chunk.abs_x
        self.abs_y = chunk.abs_y
        self.address = chunk.address
        self.fp = chunk.fp
        self._version = chunk._version
        self.load_counter = chunk.load_counter
        # Initialization
        self.redraw = set()
        self.dirty = True
        self.surf = Surface((CHUNK_RENDER_SIZE, CHUNK_RENDER_SIZE)).convert_alpha()

    def render(self) -> pygame.surface.Surface:
        if self.dirty:
            globals.dirty_chunks += 1
            if globals.chunks_rendered_this_frame < MAX_RENDER_CHUNKS:
                globals.chunks_rendered_this_frame += 1
                self.surf.fill((0, 0, 0, 0))
                for x in range(16):
                    for y in range(16):
                        block = self.get_tile_type(x, y)
                        if block.texture_path is None:
                            continue
                        tex = get_lit_texture(get_block_texture(block), self.get_visual_light(x, y))
                        rpos = Vector2(x, 15 - y) * BLOCK_RENDER_SIZE
                        self.surf.blit(tex, Rect(rpos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)))
                self.dirty = False
        elif self.redraw:
            for (x, y) in list(self.redraw):
                block = self.get_tile_type(x, y)
                rpos = Vector2(x, 15 - y) * BLOCK_RENDER_SIZE
                rect = Rect(rpos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE))
                self.surf.fill((0, 0, 0, 0), rect)
                if block.texture_path is not None:
                    tex = get_lit_texture(get_block_texture(block), self.get_visual_light(x, y))
                    self.surf.blit(tex, Rect(rpos, (BLOCK_RENDER_SIZE, BLOCK_RENDER_SIZE)))
            self.redraw.clear()
        return self.surf

    def set_tile_type(self, x: int, y: int, type: Block) -> None:
        super().set_tile_type(x, y, type)
        self.redraw.add((x, y))


def get_block_texture(block: Block) -> pygame.surface.Surface:
    if block is None:
        tex = MISSING_TEXTURE[0]
    elif block.texture_path is None:
        tex = EMPTY_TEXTURE[0]
    else:
        sprites = BLOCK_SPRITES[block.id]
        assert sprites is not None
        if block.turnable_texture:
            tex = random.choice(sprites)
        else:
            tex = sprites[0]
    return tex


@lru_cache
def change_texture_brightness(tex: pygame.surface.Surface, brightness: int) -> pygame.surface.Surface:
    res = tex.copy()
    res.fill((brightness, brightness, brightness), special_flags=pygame.BLEND_RGB_MULT)
    return res


def get_lit_texture(tex: pygame.surface.Surface, light: int) -> pygame.surface.Surface:
    if globals.config.config['spooky_lighting']:
        brightness = 255 * light // 15
    else:
        brightness = 255 * (light + 1) // 16
    return change_texture_brightness(tex, brightness)
