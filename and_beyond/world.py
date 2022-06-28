import abc
import asyncio
import enum
import json
import logging
import random
import time
from asyncio.events import AbstractEventLoop
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from json.decoder import JSONDecodeError
from mmap import ACCESS_WRITE, mmap
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, ByteString, Callable, Optional, TypedDict, Union
from uuid import UUID

import aiofiles
from typing_extensions import Self

from and_beyond import blocks
from and_beyond.abstract_player import AbstractPlayer
from and_beyond.blocks import Block, get_block_by_id
from and_beyond.utils import autoslots

if TYPE_CHECKING:
    from and_beyond.server.world_gen.core import WorldGenerator

ALLOWED_FILE_CHARS = ' ._'
SECTION_SIZE = 262176
DATA_VERSION = 1


def safe_filename(name: str) -> str:
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
    player_cache: dict[str, int]


class AbstractWorld(abc.ABC):
    def get_chunk(self, x: int, y: int) -> 'WorldChunk':
        chunk = self.get_chunk_or_none(x, y)
        if chunk is None:
            raise KeyError(f'No chunk at {x}/{y}')
        return chunk

    def get_chunk_or_none(self, x: int, y: int) -> Optional['WorldChunk']:
        return self.get_chunk(x, y)

    def _get_chunk_for_block(self, x: int, y: int) -> tuple[int, int, int, int]:
        cx = x >> 4
        cy = y >> 4
        bx = x - (cx << 4)
        by = y - (cy << 4)
        return cx, cy, bx, by

    def get_tile_type(self, x: int, y: int) -> Block:
        cx, cy, bx, by = self._get_chunk_for_block(x, y)
        return self.get_chunk(cx, cy).get_tile_type(bx, by)

    def get_tile_type_or_none(self, x: int, y: int) -> Optional[Block]:
        cx, cy, bx, by = self._get_chunk_for_block(x, y)
        chunk = self.get_chunk_or_none(cx, cy)
        if chunk is None:
            return None
        return chunk.get_tile_type(bx, by)

    def set_tile_type(self, x: int, y: int, type: Block) -> None:
        cx, cy, bx, by = self._get_chunk_for_block(x, y)
        self.get_chunk(cx, cy).set_tile_type(bx, by, type)

    def set_tile_type_if_loaded(self, x: int, y: int, type: Block) -> bool:
        cx, cy, bx, by = self._get_chunk_for_block(x, y)
        chunk = self.get_chunk_or_none(cx, cy)
        if chunk is None:
            return False
        chunk.set_tile_type(bx, by, type)
        return True


@autoslots
class World(AbstractWorld):
    name: str
    safe_name: str
    root: Path

    aloop: asyncio.AbstractEventLoop

    meta_path: Path
    meta: WorldMeta
    players_path: Path
    sections_path: Path
    _players_by_name: dict[str, UUID]
    _players_by_uuid: dict[UUID, str]

    open_sections: dict[tuple[int, int], 'WorldSection']
    auto_optimize: bool

    def __init__(self, name: str, auto_optimize: bool = False) -> None:
        self.name = name
        self.safe_name = safe_filename(name)
        self.root = Path('worlds') / self.safe_name
        self.players_path = self.root / 'players'
        self.sections_path = self.root / 'sections'
        self._players_by_name = {}
        self._players_by_uuid = {}
        self.open_sections = {}
        self.auto_optimize = auto_optimize

    def _default_meta(self) -> None:
        meta = DEFAULT_META.copy()
        meta['name'] = self.name
        meta['seed'] = time.time_ns() & (2 ** 64 - 1)
        self.meta = meta

    async def ainit(self, optimize: Optional[bool] = None) -> None:
        if optimize is None:
            optimize = self.auto_optimize
        self.aloop = asyncio.get_running_loop()
        await self.ensure_exists()
        for (player_name, player_uuid_int) in self.meta['player_cache'].items():
            player_uuid = UUID(int=player_uuid_int)
            self._players_by_name[player_name] = player_uuid
            self._players_by_uuid[player_uuid] = player_name
        if optimize:
            start = time.perf_counter()
            with ThreadPoolExecutor(thread_name_prefix='Optimize') as executor:
                tasks: list[Awaitable[bool]] = []
                for sect_path in self.sections_path.glob('section_*_*.dat'):
                    try:
                        x, y = sect_path.name.split('_', 2)[1:]
                        x = int(x)
                        y = int(y.split('.', 1)[0])
                    except Exception:
                        logging.warn('Invalid section file name: %s', sect_path.name)
                        continue
                    sect = WorldSection(self, x, y, optimize=False)
                    tasks.append(self.aloop.run_in_executor(executor, sect.optimize))
                logging.info('Attempting to optimize %i sections', len(tasks))
                results: list[Union[bool, BaseException]] = await asyncio.gather(*tasks, return_exceptions=True)
                for sect in list(self.open_sections.values()):
                    sect.close()
            end = time.perf_counter()
            success_count = results.count(True)
            errors_count = sum(isinstance(r, Exception) for r in results)
            if errors_count:
                logging.info(
                    'Optimized %i sections (with %i failures) in %f seconds',
                    success_count, errors_count, end - start
                )
            else:
                logging.info(
                    'Successfully optimized %i sections (with no failures) in %f seconds',
                    success_count, end - start
                )

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
        self.meta.setdefault('player_cache', {})

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
        self.meta['player_cache'].clear()
        for (player_name, player_uuid) in self._players_by_name.items():
            if player_uuid.int != 0:
                self.meta['player_cache'][player_name] = player_uuid.int
        async with aiofiles.open(self.meta_path, 'w') as fp:
            await fp.write(await self.aloop.run_in_executor(None, partial(json.dumps, self.meta, indent=2)))

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
        if self.get_generated_tile_type(x, y, gen) != blocks.AIR:
            return -1
        if self.get_generated_tile_type(x, y + 1, gen) != blocks.AIR:
            return -1
        if self.get_generated_tile_type(x, y - 1, gen) == blocks.AIR:
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

    def get_generated_chunk(self, x: int, y: int, gen: 'WorldGenerator') -> 'WorldChunk':
        c = self.get_chunk(x, y)
        if not c.has_generated:
            gen.generate_chunk(c)
            c.version = CHUNK_VERSION
        return c

    def get_generated_tile_type(self, x: int, y: int, gen: 'WorldGenerator') -> Block:
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

    def get_player_by_name(self, name: str) -> 'OfflinePlayer':
        return OfflinePlayer(name, self._players_by_name[name], self)

    def get_player_by_uuid(self, uuid: UUID) -> 'OfflinePlayer':
        try:
            return OfflinePlayer(self._players_by_uuid[uuid], uuid, self)
        except KeyError:
            return OfflinePlayer(None, uuid, self)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<World {self.name!r} safe_name={self.safe_name!r} len(open_sections)={len(self.open_sections)}>'


@autoslots
class WorldSection:
    """
    Section format:
        0:6       -- The file magic, b'BEYOND'
        6:10      -- The section format version, stored as a UINT4
        10:32     -- Unused
        32:262176 -- Chunk data (see chunk data format)
    Chunk data format:
        Each chunk is stored at an address (relative to the start of the section) of `32 + (x * 16 + y) * 1024`. Each
        chunk is stored in chunk format (see the WorldChunk docstring)
    """
    world: World
    x: int
    y: int

    path: Path
    fp: mmap
    cached_chunks: dict[tuple[int, int], 'WorldChunk']
    load_counter: int
    _data_version: int

    def __init__(self, world: World, x: int, y: int, optimize: Optional[bool] = None) -> None:
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
        if (optimize is None and world.auto_optimize) or optimize:
            self.optimize()

    def _load_magic(self) -> None:
        magic = self.fp[:6]
        version = self.fp[6:10]
        if magic + version == b'\0' * 10:
            self._data_version = 0
            return
        if magic != b'BEYOND':
            raise SectionFormatError('Magic mismatch')
        self._data_version = int.from_bytes(version, 'little', signed=False)

    def optimize(self) -> bool:
        if self.data_version > DATA_VERSION:
            raise SectionFormatError(f'Section version too new! ({self.data_version} > {DATA_VERSION})')
        if self.data_version == DATA_VERSION:
            return False
        start = time.perf_counter()
        self.data_version = DATA_VERSION
        end = time.perf_counter()
        logging.info('Optimized section (%i, %i) in %f seconds', self.x, self.y, end - start)
        return True

    def close(self) -> None:
        logging.debug('Closing section (%i, %i)', self.x, self.y)
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

    def mark_unloaded(self, cb: Optional[Callable[['WorldSection'], Any]] = None) -> int:
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
        548:556  -- Chunk flags
        556:812  -- Lighting data
        812:1024 -- Unused
    Block data format:
        Each block is stored at an address (relative to the start of the chunk) of `(x * 16 + y) * 2`. Each block is
        two bytes: a UINT8 representing the type, and a single representing any metadata (could be any format)
    Biome data format:
        Each biome is stored at an address (relative to the start of the chunk) of `516 + (x * 16 + y) * 2`. Each biome
        is two bytes: a UINT8 representing the type, and a single representing any metadata (could be any format)
    Chunk flags:
        The chunk flags are an 64-bit bitmask that contains boolean information about the chunk.
            0x1 -- Whether skylight has been calculated yet
    Lighting data format:
        The lighting data for each block is stored at an address (relative to the start of the chunk) of
        `548 + x * 16 + y`. Each block is represented by one byte, which is used to store two nibbles. The lower 4 bits
        of the byte represent the skylight, and the upper 4 bits represent the blocklight.
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
    def virtual_chunk(cls, x: int, y: int, abs_x: int, abs_y: int, data: ByteString) -> Self:
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

    def mark_unloaded(self, cb: Optional[Callable[['WorldChunk'], Any]] = None) -> int:
        self.load_counter -= 1
        if self.load_counter <= 0 and cb is not None:
            cb(self)
        return self.load_counter

    def _get_tile_address(self, x: int, y: int) -> int:
        return self.address + (x * 16 + y) * 2

    def get_tile_type(self, x: int, y: int) -> Block:
        addr = self._get_tile_address(x, y)
        return get_block_by_id(self.fp[addr])

    def set_tile_type(self, x: int, y: int, type: Block) -> None:
        type.on_place(self, x, y)
        addr = self._get_tile_address(x, y)
        self.fp[addr] = type.id

    def _get_biome_address(self, x: int, y: int) -> int:
        return self.address + 516 + (x * 16 + y) * 2

    def get_biome_type(self, x: int, y: int) -> 'BiomeTypes':
        addr = self._get_biome_address(x, y)
        return BiomeTypes(self.fp[addr])

    def set_biome_type(self, x: int, y: int, type: 'BiomeTypes') -> None:
        addr = self._get_biome_address(x, y)
        self.fp[addr] = type

    def get_flags(self) -> 'ChunkFlags':
        return ChunkFlags.from_bytes(self.fp[self.address + 548:self.address + 556], 'little', signed=False)

    def set_flags(self, flags: int) -> None:
        self.fp[self.address + 548:self.address + 556] = flags.to_bytes(8, 'little', signed=False)

    def _get_lighting_address(self, x: int, y: int) -> int:
        return self.address + 548 + x * 16 + y

    def get_packed_lighting(self, x: int, y: int) -> int:
        return self.fp[self._get_lighting_address(x, y)]

    def set_packed_lighting(self, x: int, y: int, packed_lighting: int) -> None:
        self.fp[self._get_lighting_address(x, y)] = packed_lighting

    def get_skylight(self, x: int, y: int) -> int:
        return self.fp[self._get_lighting_address(x, y)] & 0xf

    def set_skylight(self, x: int, y: int, skylight: int) -> None:
        addr = self._get_lighting_address(x, y)
        self.fp[addr] = (self.fp[addr] & 0xf0) | skylight

    def get_blocklight(self, x: int, y: int) -> int:
        return self.fp[self._get_lighting_address(x, y)] >> 4

    def set_blocklight(self, x: int, y: int, blocklight: int) -> None:
        addr = self._get_lighting_address(x, y)
        self.fp[addr] = (self.fp[addr] & 0xf) | (blocklight << 4)

    def get_visual_light(self, x: int, y: int) -> int:
        packed = self.get_packed_lighting(x, y)
        return max(packed & 0xf, packed >> 4)

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


class OfflinePlayer(AbstractPlayer):
    name: Optional[str]
    uuid: UUID
    data_path: Path
    world: World
    banned: Optional[str]
    operator_level: int
    aloop: AbstractEventLoop

    def __init__(self, name: Optional[str], uuid: UUID, world: 'World') -> None:
        self.name = name
        self.uuid = uuid
        self.world = world
        self.data_path = world.players_path / f'{uuid}.json'
        if uuid is not None and uuid.int == 0:
            old_path = world.players_path / '00000000-0000-0000-0000-000000005db0.json'
            if old_path.exists():
                logging.info('Player used old save filename, renaming...')
                old_path.rename(self.data_path) # Rename singleplayer saves
        self.loaded_chunks = {}

    async def ainit(self) -> None:
        self.aloop = asyncio.get_running_loop()
        if self.name is not None:
            if (old_name := self.world._players_by_uuid.pop(self.uuid, None)) is not None:
                self.world._players_by_name.pop(old_name, None)
            if (old_uuid := self.world._players_by_name.pop(self.name, None)) is not None:
                self.world._players_by_uuid.pop(old_uuid, None)
            self.world._players_by_name[self.name] = self.uuid
            self.world._players_by_uuid[self.uuid] = self.name
        spawn_x = self.world.meta['spawn_x']
        spawn_x = 0 if spawn_x is None else spawn_x
        spawn_y = self.world.meta['spawn_y']
        spawn_y = 0 if spawn_y is None else spawn_y
        banned = None
        operator_level = 0
        if self.data_path.exists():
            async with aiofiles.open(self.data_path) as fp:
                raw_data = await fp.read()
            try:
                data: dict[str, Any] = await self.aloop.run_in_executor(None, json.loads, raw_data)
            except json.JSONDecodeError:
                pass
            else:
                self.x = data.get('x', spawn_x)
                self.y = data.get('y', spawn_y)
                banned = data.get('banned', None)
                operator_level = data.get('operator', 0)
        else:
            self.x = spawn_x
            self.y = spawn_y
        self.banned = banned
        self.operator_level = operator_level

    async def save(self) -> None:
        data = {
            'x': self.x,
            'y': self.y,
            'banned': self.banned,
            'operator': self.operator_level,
        }
        raw_data = await self.aloop.run_in_executor(None, partial(json.dumps, data, indent=2))
        async with aiofiles.open(self.data_path, 'w') as fp:
            await fp.write(raw_data)

    def __str__(self) -> str:
        return self.name or repr(self)

    def __repr__(self) -> str:
        return f'<Player uuid={self.uuid!r} name={self.name!r} x={self.x} y={self.y}>'


DEFAULT_META: WorldMeta = {
    'name': '',
    'seed': 0,
    'spawn_x': None,
    'spawn_y': None,
    'player_cache': {},
}


class BiomeTypes(enum.IntEnum):
    HILLS = 0


class ChunkFlags(enum.IntFlag):
    SKYLIGHT_GENERATED = 1


CHUNK_VERSION = 1
CHUNK_VERSION_MAP = [
    'NOT GENERATED', # 0
    'a1.0.0', # 1
]
CHUNK_VERSION_DISPLAY_NAME = 'a1.3.0'
