import abc
import asyncio
import enum
import json
import struct
from typing import Optional, TypeVar, cast
from uuid import UUID

from and_beyond import blocks
from and_beyond.abc import JsonSerializable, ValidJson
from and_beyond.blocks import Block, get_block_by_id
from and_beyond.common import KEY_LENGTH, PROTOCOL_VERSION
from and_beyond.middleware import ReaderMiddleware, WriterMiddleware
from and_beyond.text import EMPTY_TEXT, MaybeText, Text, maybe_text_to_text
from and_beyond.world import WorldChunk

_T_int = TypeVar('_T_int', bound=int)
_T_JsonSerializable = TypeVar('_T_JsonSerializable', bound=JsonSerializable)
_D = struct.Struct('<d')


class PacketType(enum.IntEnum):
    CLIENT_REQUEST = 0
    SERVER_INFO = 1
    BASIC_AUTH = 2
    PLAYER_INFO = 3
    REMOVE_PLAYER = 4
    DISCONNECT = 5
    PING = 6
    CHUNK = 7
    CHUNK_UNLOAD = 8
    CHUNK_UPDATE = 9
    PLAYER_POS = 10
    SIMPLE_PLAYER_POS = 11
    CHAT = 12


class Packet(abc.ABC):
    type: PacketType

    async def read(self, reader: ReaderMiddleware) -> None:
        pass

    def write(self, writer: WriterMiddleware) -> None:
        pass


async def read_packet(reader: ReaderMiddleware) -> Packet:
    pack_type = await _read_ushort(reader, PacketType)
    packet = PACKET_CLASSES[pack_type]()
    await packet.read(reader)
    return packet


async def read_packet_timeout(reader: ReaderMiddleware, timeout: float = 3) -> Packet:
    return await asyncio.wait_for(read_packet(reader), timeout)


async def write_packet(packet: Packet, writer: WriterMiddleware) -> None:
    _write_ushort(packet.type, writer)
    packet.write(writer)
    await writer.drain()


async def _read_ushort(reader: ReaderMiddleware, factory: type[_T_int] = int) -> _T_int:
    return cast(_T_int, factory.from_bytes(await reader.readexactly(2), 'little', signed=False))


async def _read_varint(reader: ReaderMiddleware) -> int:
    r = 0
    i = 0
    while True:
        e = (await reader.readexactly(1))[0]
        r += (e & 0x7f) << (i * 7)
        if not (e & 0x80):
            break
        i += 1
    if e & 0x40:
        r |= -(1 << (i * 7) + 7)
    return r


async def _read_double(reader: ReaderMiddleware) -> float:
    return _D.unpack(await reader.readexactly(8))[0]


async def _read_binary(reader: ReaderMiddleware) -> bytes:
    return await reader.readexactly(await _read_varint(reader))


async def _read_string(reader: ReaderMiddleware) -> str:
    return (await _read_binary(reader)).decode('utf-8')


async def _read_json(reader: ReaderMiddleware) -> ValidJson:
    return json.loads(await _read_string(reader))


async def _read_json_serializable(
    reader: ReaderMiddleware,
    factory: type[_T_JsonSerializable]
) -> Optional[_T_JsonSerializable]:
    value = await _read_json(reader)
    if value is None:
        return None
    return factory.from_json(value)


async def _read_uuid(reader: ReaderMiddleware) -> UUID:
    return UUID(bytes=await reader.readexactly(16))


async def _read_bool(reader: ReaderMiddleware) -> bool:
    return (await reader.readexactly(1))[0] != 0


async def _read_bools(count: int, reader: ReaderMiddleware) -> list[bool]:
    data = int.from_bytes(await reader.readexactly((count + 7) // 8), 'little', signed=False)
    result: list[bool] = []
    mask = 1
    for i in range(count):
        result.append((data & mask) != 0)
        mask <<= 1
    return result


def _write_ushort(value: int, writer: WriterMiddleware) -> None:
    writer.write(value.to_bytes(2, 'little', signed=False))


def _write_varint(value: int, writer: WriterMiddleware) -> None:
    while True:
        b = value & 0x7f
        value >>= 7
        if (value == 0 and b & 0x40 == 0) or (value == -1 and b & 0x40 != 0):
            writer.write(bytes((b,)))
            return
        writer.write(bytes((0x80 | b,)))


def _write_double(value: float, writer: WriterMiddleware) -> None:
    writer.write(_D.pack(value))


def _write_binary(value: bytes, writer: WriterMiddleware) -> None:
    _write_varint(len(value), writer)
    writer.write(value)


def _write_string(value: str, writer: WriterMiddleware) -> None:
    _write_binary(value.encode('utf-8'), writer)


def _write_json(value: ValidJson, writer: WriterMiddleware) -> None:
    _write_string(json.dumps(value, separators=(',', ':')), writer)


def _write_json_serializable(value: Optional[JsonSerializable], writer: WriterMiddleware) -> None:
    if value is None:
        _write_binary(b'null', writer)
        return
    _write_json(value.to_json(), writer)


def _write_uuid(value: UUID, writer: WriterMiddleware) -> None:
    writer.write(value.bytes)


def _write_bool(value: bool, writer: WriterMiddleware) -> None:
    writer.write(bytes((value,)))


def _write_bools(writer: WriterMiddleware, *bools: bool) -> None:
    r = 0
    for (i, v) in enumerate(bools):
        r += v << i
    writer.write(r.to_bytes((len(bools) + 7) // 8, 'little', signed=False))


# Packet classes

class ClientRequestPacket(Packet):
    type = PacketType.CLIENT_REQUEST
    protocol_version: int

    def __init__(self, protocol_version: int = PROTOCOL_VERSION) -> None:
        self.protocol_version = protocol_version

    async def read(self, reader: ReaderMiddleware) -> None:
        self.protocol_version = await _read_varint(reader)

    def write(self, writer: WriterMiddleware) -> None:
        _write_varint(self.protocol_version, writer)


class ServerInfoPacket(Packet):
    type = PacketType.SERVER_INFO
    offline: bool
    public_key: bytes

    def __init__(self, offline: bool = False, public_key: bytes = bytes(KEY_LENGTH)) -> None:
        self.offline = offline
        self.public_key = public_key

    async def read(self, reader: ReaderMiddleware) -> None:
        self.offline = await _read_bool(reader)
        self.public_key = await _read_binary(reader)

    def write(self, writer: WriterMiddleware) -> None:
        _write_bool(self.offline, writer)
        _write_binary(self.public_key, writer)


class BasicAuthPacket(Packet):
    type = PacketType.BASIC_AUTH
    token: bytes

    def __init__(self, token: bytes = b'') -> None:
        self.token = token

    async def read(self, reader: ReaderMiddleware) -> None:
        self.token = await _read_binary(reader)

    def write(self, writer: WriterMiddleware) -> None:
        _write_binary(self.token, writer)


class PlayerInfoPacket(Packet):
    type = PacketType.PLAYER_INFO
    uuid: UUID
    name: str

    def __init__(self, uuid: UUID = UUID(int=0), name: str = '') -> None:
        self.uuid = uuid
        self.name = name

    async def read(self, reader: ReaderMiddleware) -> None:
        self.uuid = await _read_uuid(reader)
        self.name = (await _read_binary(reader)).decode('ascii')

    def write(self, writer: WriterMiddleware) -> None:
        _write_uuid(self.uuid, writer)
        _write_binary(self.name.encode('ascii'), writer)


class RemovePlayerPacket(Packet):
    type = PacketType.REMOVE_PLAYER
    player: UUID

    def __init__(self, player: UUID = UUID(int=0)) -> None:
        self.player = player

    async def read(self, reader: ReaderMiddleware) -> None:
        self.player = await _read_uuid(reader)

    def write(self, writer: WriterMiddleware) -> None:
        _write_uuid(self.player, writer)


class DisconnectPacket(Packet):
    type = PacketType.DISCONNECT
    reason: Text

    def __init__(self, reason: MaybeText = EMPTY_TEXT) -> None:
        self.reason = maybe_text_to_text(reason)

    async def read(self, reader: ReaderMiddleware) -> None:
        self.reason = await _read_json_serializable(reader, Text) or EMPTY_TEXT

    def write(self, writer: WriterMiddleware) -> None:
        _write_json_serializable(self.reason, writer)


class PingPacket(Packet):
    type = PacketType.PING


class ChunkPacket(Packet):
    type = PacketType.CHUNK
    chunk: Optional[WorldChunk]

    def __init__(self, chunk: Optional[WorldChunk] = None) -> None:
        self.chunk = chunk

    async def read(self, reader: ReaderMiddleware) -> None:
        abs_x = await _read_varint(reader)
        abs_y = await _read_varint(reader)
        x = await _read_varint(reader)
        y = await _read_varint(reader)
        data = await reader.readexactly(1024)
        self.chunk = WorldChunk.virtual_chunk(x, y, abs_x, abs_y, data)

    def write(self, writer: WriterMiddleware) -> None:
        if self.chunk is None:
            writer.write(bytes(1028))
            return
        _write_varint(self.chunk.abs_x, writer)
        _write_varint(self.chunk.abs_y, writer)
        _write_varint(self.chunk.x, writer)
        _write_varint(self.chunk.y, writer)
        writer.write(self.chunk.get_data())


class UnloadChunkPacket(Packet):
    type = PacketType.CHUNK_UNLOAD
    x: int
    y: int

    def __init__(self, x: int = 0, y: int = 0) -> None:
        self.x = x
        self.y = y

    async def read(self, reader: ReaderMiddleware) -> None:
        self.x = await _read_varint(reader)
        self.y = await _read_varint(reader)

    def write(self, writer: WriterMiddleware) -> None:
        _write_varint(self.x, writer)
        _write_varint(self.y, writer)


class ChunkUpdatePacket(Packet):
    type = PacketType.CHUNK_UPDATE
    cx: int
    cy: int
    bx: int
    by: int
    block: Block
    packed_lighting: int

    def __init__(self,
        cx: int = 0, cy: int = 0,
        bx: int = 0, by: int = 0,
        block: Block = blocks.AIR,
        packed_lighting: int = 0
    ) -> None:
        self.cx = cx
        self.cy = cy
        self.bx = bx
        self.by = by
        self.block = block
        self.packed_lighting = packed_lighting

    async def read(self, reader: ReaderMiddleware) -> None:
        self.cx = await _read_varint(reader)
        self.cy = await _read_varint(reader)
        block_info = await reader.readexactly(4)
        self.bx = block_info[0]
        self.by = block_info[1]
        self.block = get_block_by_id(block_info[2])
        self.packed_lighting = block_info[3]

    def write(self, writer: WriterMiddleware) -> None:
        _write_varint(self.cx, writer)
        _write_varint(self.cy, writer)
        writer.write(bytes((self.bx, self.by, self.block.id, self.packed_lighting)))


class PlayerPositionPacket(Packet):
    type = PacketType.PLAYER_POS
    player: UUID
    x: float
    y: float

    def __init__(self, player: UUID = UUID(int=0), x: float = 0, y: float = 0) -> None:
        self.player = player
        self.x = x
        self.y = y

    async def read(self, reader: ReaderMiddleware) -> None:
        self.player = await _read_uuid(reader)
        self.x = await _read_double(reader)
        self.y = await _read_double(reader)

    def write(self, writer: WriterMiddleware) -> None:
        _write_uuid(self.player, writer)
        _write_double(self.x, writer)
        _write_double(self.y, writer)


class SimplePlayerPositionPacket(Packet):
    type = PacketType.SIMPLE_PLAYER_POS
    x: float
    y: float

    def __init__(self, x: float = 0, y: float = 0) -> None:
        self.x = x
        self.y = y

    async def read(self, reader: ReaderMiddleware) -> None:
        self.x = await _read_double(reader)
        self.y = await _read_double(reader)

    def write(self, writer: WriterMiddleware) -> None:
        _write_double(self.x, writer)
        _write_double(self.y, writer)


class ChatPacket(Packet):
    type = PacketType.CHAT
    message: Text
    time: float

    def __init__(self, message: MaybeText = EMPTY_TEXT, time: float = 0) -> None:
        self.message = maybe_text_to_text(message)
        self.time = time

    async def read(self, reader: ReaderMiddleware) -> None:
        self.message = await _read_json_serializable(reader, Text) or EMPTY_TEXT
        self.time = await _read_double(reader)

    def write(self, writer: WriterMiddleware) -> None:
        _write_json_serializable(self.message, writer)
        _write_double(self.time, writer)


PACKET_CLASSES: list[type[Packet]] = [
    ClientRequestPacket, # CLIENT_REQUEST
    ServerInfoPacket, # SERVER_INFO
    BasicAuthPacket, # BASIC_AUTH
    PlayerInfoPacket, # PLAYER_INFO
    RemovePlayerPacket, # REMOVE_PLAYER
    DisconnectPacket, # DISCONNECT
    PingPacket, # PING
    ChunkPacket, # CHUNK
    UnloadChunkPacket, # CHUNK_UNLOAD
    ChunkUpdatePacket, # CHUNK_UPDATE
    PlayerPositionPacket, # PLAYER_POS
    SimplePlayerPositionPacket, # SIMPLE_PLAYER_POS
    ChatPacket, # CHAT
]
