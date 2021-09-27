import asyncio
import enum
import json
import logging
import time
from functools import partial
from json.decoder import JSONDecodeError
from mmap import ACCESS_WRITE, mmap
from pathlib import Path
from typing import TYPE_CHECKING, ByteString, Optional, TypedDict, Union

import aiofiles

from and_beyond.utils import MaxSizedDict, autoslots

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

ALLOWED_FILE_CHARS = ' ._'
UINT32_MAX = 2 ** 32 - 1
SECTION_SIZE = 262176


def safe_filename(name: str):
    return (
        ''.join(c for c in name if c.isalnum() or c in ALLOWED_FILE_CHARS)
          .strip()
          .encode('utf-8', errors='ignore')
          [:248]
          .decode('utf-8', errors='ignore')
    )


class WorldMeta(TypedDict):
    name: str
    seed: int
    spawn_x: Optional[int]
    spawn_y: Optional[int]


@autoslots
class World:
    name: str
    safe_name: str
    root: Path

    aloop: asyncio.AbstractEventLoop

    meta_path: Path
    meta: WorldMeta
    players_path: Path
    sections_path: Path

    open_sections: dict[tuple[int, int], 'WorldSection']

    def __init__(self, name: str) -> None:
        self.name = name
        self.safe_name = safe_filename(name)
        self.root = Path('worlds') / self.safe_name
        self.players_path = self.root / 'players'
        self.sections_path = self.root / 'sections'
        self.open_sections = {}

    def _default_meta(self) -> None:
        meta = DEFAULT_META.copy()
        meta['name'] = self.name
        meta['seed'] = time.time_ns() & (2 ** 64 - 1)
        self.meta = meta

    async def ainit(self):
        self.aloop = asyncio.get_running_loop()
        await self.ensure_exists()

    async def ensure_exists(self) -> None:
        await self.mkdirs(self.root, self.players_path, self.sections_path)
        self.meta_path = self.root / 'meta.json'
        meta = self.meta_path.exists()
        if meta:
            try:
                await self.load_meta()
            except JSONDecodeError:
                meta = False
        if not meta:
            self._default_meta()
            await self.save_meta()
            meta = True

    async def mkdirs(self, *paths: Path) -> None:
        await asyncio.gather(
            *(
                self.aloop.run_in_executor(None, partial(path.mkdir, parents=True, exist_ok=True))
                for path in paths
            )
        )

    async def load_meta(self) -> None:
        async with aiofiles.open(self.meta_path, 'r') as fp:
            self.meta = await self.aloop.run_in_executor(None, json.loads, await fp.read())

    async def save_meta(self) -> None:
        async with aiofiles.open(self.meta_path, 'w') as fp:
            await fp.write(await self.aloop.run_in_executor(None, json.dumps, self.meta))

    def find_spawn(self, gen: 'WorldGenerator') -> tuple[int, int]:
        if self.meta['spawn_x'] is not None:
            if self.meta['spawn_y'] is not None:
                return self.meta['spawn_x'], self.meta['spawn_y']
            else:
                logging.warn('Invalid world spawn location (is partially null). Regenerating.')
        x = 0
        y = 0
        cmp = self._compare_valid_spawn(x, y, gen)
        if cmp != 0: # If it == 0, we've already found it
            y += -cmp * 16
            last_cmp = cmp
            while True:
                cmp = self._compare_valid_spawn(x, y, gen)
                if cmp == 0:
                    break
                y += -cmp * 16
                if cmp == -last_cmp:
                    dir = cmp
                    break
                last_cmp = cmp
            while cmp != 0:
                y += dir
                cmp = self._compare_valid_spawn(x, y, gen)
        self.meta['spawn_x'] = x
        self.meta['spawn_y'] = y
        return x, y

    def is_valid_spawn(self, x: int, y: int, gen: 'WorldGenerator') -> bool:
        return self._compare_valid_spawn(x, y, gen) == 0

    def _compare_valid_spawn(self, x: int, y: int, gen: 'WorldGenerator') -> int:
        if self.get_generated_tile_type(x, y, gen) != BlockTypes.AIR:
            return -1
        if self.get_generated_tile_type(x, y + 1, gen) != BlockTypes.AIR:
            return -1
        if self.get_generated_tile_type(x, y - 1, gen) == BlockTypes.AIR:
            return 1
        return 0

    def get_section(self, x: int, y: int) -> 'WorldSection':
        if (x, y) in self.open_sections:
            return self.open_sections[(x, y)]
        return WorldSection(self, x, y)

    def get_chunk(self, x: int, y: int) -> 'WorldChunk':
        sx = x >> 4
        sy = y >> 4
        cx = x - (sx << 4)
        cy = y - (sy << 4)
        return self.get_section(sx, sy).get_chunk(cx, cy)

    def get_tile_type(self, x: int, y: int) -> 'BlockTypes':
        cx = x >> 4
        cy = y >> 4
        bx = x - (cx << 4)
        by = y - (cy << 4)
        return self.get_chunk(cx, cy).get_tile_type(bx, by)

    def set_tile_type(self, x: int, y: int, type: 'BlockTypes') -> None:
        cx = x >> 4
        cy = y >> 4
        bx = x - (cx << 4)
        by = y - (cy << 4)
        self.get_chunk(cx, cy).set_tile_type(bx, by, type)

    def get_generated_chunk(self, x: int, y: int, gen: 'WorldGenerator') -> 'WorldChunk':
        c = self.get_chunk(x, y)
        if not c.has_generated:
            gen.generate_chunk(c)
            c.has_generated = True
        return c

    def get_generated_tile_type(self, x: int, y: int, gen: 'WorldGenerator') -> 'BlockTypes':
        cx = x >> 4
        cy = y >> 4
        bx = x - (cx << 4)
        by = y - (cy << 4)
        return self.get_generated_chunk(cx, cy, gen).get_tile_type(bx, by)

    async def close(self) -> None:
        await self.save_meta()
        for s in self.open_sections.values():
            s._close()
        self.open_sections.clear()

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<World {self.name!r} safe_name={self.safe_name!r} len(open_sections)={len(self.open_sections)}>'


@autoslots
class WorldSection:
    world: World
    x: int
    y: int

    path: Path
    fp: mmap
    cached_chunks: dict[tuple[int, int], 'WorldChunk']

    def __init__(self, world: World, x: int, y: int) -> None:
        self.world = world
        self.x = x
        self.y = y
        self.path = world.sections_path / f'section_{x}_{y}.dat'
        with open(self.path, 'a+b') as fp:
            if fp.tell() < SECTION_SIZE:
                fp.write(bytes(SECTION_SIZE - fp.tell()))
            self.fp = mmap(fp.fileno(), SECTION_SIZE, access=ACCESS_WRITE)
        world.open_sections[(x, y)] = self
        self.cached_chunks = MaxSizedDict(max_size=8)

    def close(self) -> None:
        self._close()
        self.world.open_sections.pop((self.x, self.y), None)

    def _close(self) -> None:
        self.fp.close()

    def __enter__(self) -> 'WorldSection':
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __del__(self) -> None:
        self._close()

    def _get_sect_address(self, x: int, y: int) -> int:
        return 32 + (x * 16 + y) * 1024

    def get_chunk(self, x: int, y: int) -> 'WorldChunk':
        if (x, y) not in self.cached_chunks:
            self.cached_chunks[(x, y)] = WorldChunk(self, x, y)
        return self.cached_chunks[(x, y)]

    def flush(self) -> None:
        self.fp.flush()


@autoslots
class WorldChunk:
    section: Optional[WorldSection]
    x: int
    y: int
    abs_x: int
    abs_y: int
    address: int
    fp: Union[bytearray, mmap]
    _has_generated: Optional[bool]

    def __init__(self, section: WorldSection, x: int, y: int) -> None:
        self.section = section
        self.x = x
        self.y = y
        self.abs_x = x + (section.x << 4)
        self.abs_y = y + (section.y << 4)
        self.address = section._get_sect_address(x, y)
        self.fp = section.fp
        self._has_generated = None

    @classmethod
    def virtual_chunk(cls, x: int, y: int, abs_x: int, abs_y: int, data: ByteString) -> 'WorldChunk':
        self = cls.__new__(cls)
        self.section = None
        self.x = x
        self.y = y
        self.abs_x = abs_x
        self.abs_y = abs_y
        self.address = 0
        self.fp = data if isinstance(data, bytearray) else bytearray(data) # Copy if necessary, otherwise don't
        self._has_generated = None
        return self

    def _get_tile_address(self, x: int, y: int) -> int:
        return self.address + (x * 16 + y) * 2

    def get_tile_type(self, x: int, y: int) -> 'BlockTypes':
        addr = self._get_tile_address(x, y)
        return BlockTypes(self.fp[addr])

    def set_tile_type(self, x: int, y: int, type: 'BlockTypes') -> None:
        addr = self._get_tile_address(x, y)
        self.fp[addr] = type

    def get_data(self) -> 'ChunkDataView':
        return ChunkDataView(self.fp, self.address, self.address + 1024)

    def get_metadata_view(self) -> 'ChunkDataView':
        return ChunkDataView(self.fp, self.address + 512, self.address + 1024)

    @property
    def has_generated(self) -> bool:
        if self._has_generated is None:
            self._has_generated = self.fp[self.address + 512] > 0
        return self._has_generated

    @has_generated.setter
    def has_generated(self, gen: bool) -> None:
        self._has_generated = gen
        self.fp[self.address + 512] = gen


@autoslots
class ChunkDataView:
    fp: Union[bytearray, mmap]
    start: int
    end: int

    def __init__(self, fp: Union[bytearray, mmap], start: int, end: int) -> None:
        self.fp = fp
        self.start = start
        self.end = end

    def _index_error(self, i: int):
        fp_repr = self.fp if isinstance(self.fp, mmap) else f'<bytearray len={len(self.fp)}>'
        raise IndexError(f'{i} out of bounds for View({fp_repr}, {self.start}, {self.end})')

    def _get_index(self, i):
        if isinstance(i, slice):
            start = self._get_index(i.start)
            stop = None if slice.stop is None else self._get_index(i.stop)
            return slice(start, i.step, stop)
        if i < 0:
            index = self.end + i
        else:
            index = self.start + i
        if index < self.start or index >= self.end:
            self._index_error(i)
        return index

    def __getitem__(self, i: Union[int, slice]) -> Union[int, bytes]:
        return self.fp[self._get_index(i)]

    def __setitem__(self, i: Union[int, slice], v: Union[int, bytes]) -> None:
        self.fp[self._get_index(i)] = v # type: ignore

    def __bytes__(self) -> bytes:
        return self.fp[self.start:self.end]


DEFAULT_META: WorldMeta = {
    'name': '',
    'seed': 0,
    'spawn_x': None,
    'spawn_y': None,
}


class BlockTypes(enum.IntEnum):
    AIR = 0
    STONE = 1
    DIRT = 2
    GRASS = 3
