import asyncio
import enum
import json
import logging
import random
import time
from functools import partial
from json.decoder import JSONDecodeError
from mmap import ACCESS_WRITE, mmap
from pathlib import Path
from typing import (TYPE_CHECKING, Any, ByteString, Callable, Optional, TypedDict,
                    Union)

import aiofiles

from and_beyond.utils import autoslots

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

ALLOWED_FILE_CHARS = ' ._'
SECTION_SIZE = 262176
DATA_VERSION = 1


def safe_filename(name: str):
    return (
        ''.join(c for c in name if c.isalnum() or c in ALLOWED_FILE_CHARS)
          .strip()
          .encode('utf-8', errors='ignore')
          [:248]
          .decode('utf-8', errors='ignore')
    )


class SectionFormatError(Exception):
    pass


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
        rand = random.Random(gen.seed)
        x = rand.randint(-128, 128)
        y = 0
        cmp = self._compare_valid_spawn(x, y, gen)
        dir = 1
        if cmp != 0: # If cmp == 0, we've already found the spawn
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
            c.version = CHUNK_VERSION
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
    """
    Section format:
        0:32      -- Unused
        32:262176 -- Chunk data (see chunk data format)
    Chunk data format:
        Each chunk is stored at an address (relative to the start of the
        section) of `32 + (x * 16 + y) * 1024`. Each chunk is stored in
        chunk format (see the WorldChunk doc)
    """
    world: World
    x: int
    y: int

    path: Path
    fp: mmap
    cached_chunks: dict[tuple[int, int], 'WorldChunk']
    load_counter: int
    _data_version: int

    def __init__(self, world: World, x: int, y: int) -> None:
        self.world = world
        self.x = x
        self.y = y
        self.path = world.sections_path / f'section_{x}_{y}.dat'
        with open(self.path, 'a+b') as fp:
            if fp.tell() == 0:
                fp.write(b'BEYOND')
                fp.write(DATA_VERSION.to_bytes(4, 'little', signed=False))
            if fp.tell() < SECTION_SIZE:
                fp.write(bytes(SECTION_SIZE - fp.tell()))
            self.fp = mmap(fp.fileno(), SECTION_SIZE, access=ACCESS_WRITE)
        self._load_magic()
        world.open_sections[(x, y)] = self
        self.cached_chunks = {}
        self.load_counter = 0

    def _load_magic(self) -> None:
        magic = self.fp[:6]
        version = self.fp[6:10]
        if magic + version == b'\0' * 10:
            self._data_version = 0
            return
        if magic != b'BEYOND':
            raise SectionFormatError('Magic mismatch')
        self._data_version = int.from_bytes(version, 'little', signed=False)

    def close(self) -> None:
        self._close()
        self.world.open_sections.pop((self.x, self.y), None)

    def _close(self) -> None:
        self.fp.close()

    def __enter__(self) -> 'WorldSection':
        self.mark_loaded()
        return self

    def __exit__(self, *args) -> None:
        self.mark_unloaded(self.__class__.close)

    def __del__(self) -> None:
        self._close()

    def _get_chunk_address(self, x: int, y: int) -> int:
        return 32 + (x * 16 + y) * 1024

    def get_chunk(self, x: int, y: int) -> 'WorldChunk':
        if (x, y) not in self.cached_chunks:
            self.cached_chunks[(x, y)] = WorldChunk(self, x, y)
        return self.cached_chunks[(x, y)]

    def flush(self) -> None:
        self.fp.flush()

    def mark_loaded(self) -> int:
        self.load_counter += 1
        return self.load_counter

    def mark_unloaded(self, cb: Callable[['WorldSection'], Any] = None) -> int:
        self.load_counter -= 1
        if self.load_counter <= 0 and cb is not None:
            cb(self)
        return self.load_counter

    @property
    def data_version(self) -> int:
        return self._data_version

    @data_version.setter
    def data_version(self, ver: int) -> None:
        self._data_version = ver
        # Add magic to file in case it wasn't there already
        self.fp[:10] = b'BEYOND' + ver.to_bytes(4, 'little', signed=False)


@autoslots
class WorldChunk:
    """
    Chunk format:
        0:512    -- Block data (see block data format)
        512:516  -- Chunk data version (UINT4)
        516:548  -- Biome data (see biome data format)
        548:1024 -- Unused
    Block data format:
        Each block is stored at an address (relative to the start of the
        chunk) of `(x * 16 + y) * 2`. Each block is two bytes: a UINT8
        representing the type, and a single representing any metadata
        (could be any format)
    Biome data format:
        Each biome is stored at an address (relative to the start of the
        chunk) of `516 + (x * 16 + y) * 2`. Each biome is two bytes: a UINT8
        representing the type, and a single representing any metadata
        (could be any format)
    """

    section: Optional[WorldSection]
    x: int
    y: int
    abs_x: int
    abs_y: int
    address: int
    fp: Union[bytearray, mmap]
    _version: Optional[int]
    load_counter: int

    def __init__(self, section: WorldSection, x: int, y: int) -> None:
        section.mark_loaded()
        self.section = section
        self.x = x
        self.y = y
        self.abs_x = x + (section.x << 4)
        self.abs_y = y + (section.y << 4)
        self.address = section._get_chunk_address(x, y)
        self.fp = section.fp
        self._version = None
        self.load_counter = 0

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
        self._version = None
        self.load_counter = 0
        return self

    def mark_loaded(self) -> int:
        self.load_counter += 1
        return self.load_counter

    def mark_unloaded(self, cb: Callable[['WorldChunk'], Any] = None) -> int:
        self.load_counter -= 1
        if self.load_counter <= 0 and cb is not None:
            cb(self)
        return self.load_counter

    def _get_tile_address(self, x: int, y: int) -> int:
        return self.address + (x * 16 + y) * 2

    def get_tile_type(self, x: int, y: int) -> 'BlockTypes':
        addr = self._get_tile_address(x, y)
        return BlockTypes(self.fp[addr])

    def set_tile_type(self, x: int, y: int, type: 'BlockTypes') -> None:
        addr = self._get_tile_address(x, y)
        self.fp[addr] = type

    def _get_biome_address(self, x: int, y: int) -> int:
        return self.address + (x * 16 + y) * 2

    def get_biome_type(self, x: int, y: int) -> 'BiomeTypes':
        addr = self._get_biome_address(x, y)
        return BiomeTypes(self.fp[addr])

    def set_biome_type(self, x: int, y: int, type: 'BiomeTypes') -> None:
        addr = self._get_biome_address(x, y)

    def get_data(self) -> memoryview:
        return memoryview(self.fp)[self.address:self.address + 1024]

    def get_metadata_view(self) -> memoryview:
        return memoryview(self.fp)[self.address + 512:self.address + 1024]

    @property
    def version(self) -> int:
        if self._version is None:
            self._version = int.from_bytes(
                self.fp[self.address + 512:self.address + 516],
                'little', signed=False
            )
        return self._version

    @version.setter
    def version(self, version: int) -> None:
        self._version = version
        self.fp[self.address + 512:self.address + 516] = (
            version.to_bytes(4, 'little', signed=False)
        )

    @property
    def has_generated(self) -> bool:
        return self.version > 0


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
    WOOD = 4
    PLANKS = 5
    LEAVES = 6


class BiomeTypes(enum.IntEnum):
    HILLS = 0


CHUNK_VERSION = 1
CHUNK_VERSION_MAP = [
    'NOT GENERATED', # 0
    'a1.0.0', # 1
]
CHUNK_VERSION_DISPLAY_NAME = 'a1.3.0'
