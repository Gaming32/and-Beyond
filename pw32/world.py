import asyncio
import enum
import json
import time
from functools import partial
from json.decoder import JSONDecodeError
from mmap import ACCESS_WRITE, mmap
from pathlib import Path
from typing import ByteString, Optional, TypedDict, Union

import aiofiles
from pw32.utils import autoslots

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
        meta['seed'] = time.time_ns()
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

    async def close(self) -> None:
        await self.save_meta()
        for s in self.open_sections.values():
            s._close()
        self.open_sections.clear()


@autoslots
class WorldSection:
    world: World
    x: int
    y: int

    path: Path
    fp: mmap

    def __init__(self, world: World, x: int, y: int) -> None:
        self.world = world
        self.x = x
        self.y = y
        self.path = world.sections_path / f'section_{x}_{y}.dat'
        fp = open(self.path, 'a+b')
        self.fp = mmap(fp.fileno(), SECTION_SIZE, access=ACCESS_WRITE)
        fp.close()
        world.open_sections[(x, y)] = self

    def close(self) -> None:
        self._close()
        self.world.open_sections.pop((self.x, self.y))

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
        return WorldChunk(self, x, y)

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

    def __init__(self, section: WorldSection, x: int, y: int) -> None:
        self.section = section
        self.x = x
        self.y = y
        self.abs_x = x + (section.x << 4)
        self.abs_y = y + (section.y << 4)
        self.address = section._get_sect_address(x, y)
        self.fp = section.fp

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
        return self

    def _get_tile_address(self, x: int, y: int) -> int:
        return self.address + (x * 16 + y) * 2

    def get_tile_type(self, x: int, y: int) -> 'BlockTypes':
        addr = self._get_tile_address(x, y)
        return BlockTypes(self.fp[addr])

    def set_tile_type(self, x: int, y: int, type: 'BlockTypes') -> None:
        addr = self._get_tile_address(x, y)
        self.fp[addr] = type
    
    def get_data(self) -> bytes:
        return self.fp[self.address:self.address + 1024]


DEFAULT_META: WorldMeta = {
    'name': '',
    'seed': 0,
}


class BlockTypes(enum.IntEnum):
    AIR = 0
    STONE = 1
    DIRT = 2
    GRASS = 3
