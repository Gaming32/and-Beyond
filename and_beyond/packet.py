import abc
import enum
import struct
import uuid
from asyncio import StreamReader
from asyncio.streams import StreamWriter
from io import BytesIO
from typing import Optional, TypeVar

from and_beyond.common import PROTOCOL_VERSION
from and_beyond.utils import BufferedStreamWriter, autoslots, copy_obj_to_class
from and_beyond.world import BlockTypes, WorldChunk

_T_int = TypeVar('_T_int', bound=int)
_D = struct.Struct('<d')


class PacketType(enum.IntEnum):
    ONLINE_AUTHENTICATE = 0
    OFFLINE_AUTHENTICATE = 1
    DISCONNECT = 2
    PING = 3
    CHUNK = 4
    CHUNK_UNLOAD = 5
    CHUNK_UPDATE = 6
    # PLAYER_INFO = 7 # Reserved for future use
    PLAYER_POS = 8
    ADD_VELOCITY = 9
    CHAT = 10


class Packet(abc.ABC):
    type: PacketType

    async def read(self, reader: StreamReader) -> None:
        pass

    def write(self, writer: StreamWriter) -> None:
        pass


async def read_packet(reader: StreamReader) -> Packet:
    pack_type = await _read_ushort(reader, PacketType)
    packet = PACKET_CLASSES[pack_type]()
    await packet.read(reader)
    return packet


async def write_packet(packet: Packet, writer: StreamWriter) -> None:
    if not isinstance(writer, BufferedStreamWriter):
        writer = copy_obj_to_class(writer, BufferedStreamWriter)
        writer._buffer = BytesIO()
    _write_ushort(packet.type, writer)
    packet.write(writer)
    await writer.drain()


async def _read_ushort(reader: StreamReader, factory: type[_T_int] = int) -> _T_int:
    # The typing is correct, but Pyright hates me
    return factory.from_bytes(await reader.readexactly(2), 'little', signed=False) # type: ignore


async def _read_varint(reader: StreamReader) -> int:
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


async def _read_double(reader: StreamReader) -> float:
    return _D.unpack(await reader.readexactly(8))[0]


async def _read_string(reader: StreamReader) -> str:
    return (await reader.readexactly(await _read_varint(reader))).decode('utf-8')


async def _read_uuid(reader: StreamReader) -> uuid.UUID:
    return uuid.UUID(bytes=await reader.readexactly(16))


def _write_ushort(value: int, writer: StreamWriter) -> None:
    writer.write(value.to_bytes(2, 'little', signed=False))


def _write_varint(value: int, writer: StreamWriter) -> None:
    while True:
        b = value & 0x7f
        value >>= 7
        if (value == 0 and b & 0x40 == 0) or (value == -1 and b & 0x40 != 0):
            writer.write(bytes((b,)))
            return
        writer.write(bytes((0x80 | b,)))


def _write_double(value: float, writer: StreamWriter) -> None:
    writer.write(_D.pack(value))


def _write_string(value: str, writer: StreamWriter) -> None:
    enc = value.encode('utf-8')
    _write_varint(len(enc), writer)
    writer.write(enc)


def _write_uuid(value: uuid.UUID, writer: StreamWriter) -> None:
    writer.write(value.bytes)


# Packet classes

class PingPacket(Packet):
    type = PacketType.PING


class OfflineAuthenticatePacket(Packet):
    type = PacketType.OFFLINE_AUTHENTICATE
    user_id: uuid.UUID
    nickname: str
    protocol_version: int

    def __init__(self,
            user_id: uuid.UUID = uuid.UUID(int=0),
            nickname: str = None,
            protocol_version: int = PROTOCOL_VERSION,
        ) -> None:
        self.user_id = user_id
        self.nickname = str(user_id) if nickname is None else nickname
        self.protocol_version = protocol_version

    async def read(self, reader: StreamReader) -> None:
        self.user_id = await _read_uuid(reader)
        self.nickname = await _read_string(reader)
        self.protocol_version = await _read_varint(reader)

    def write(self, writer: StreamWriter) -> None:
        _write_uuid(self.user_id, writer)
        _write_string(self.nickname, writer)
        _write_varint(self.protocol_version, writer)


class DisconnectPacket(Packet):
    type = PacketType.DISCONNECT
    reason: str

    def __init__(self, reason: str = '') -> None:
        self.reason = reason

    async def read(self, reader: StreamReader) -> None:
        self.reason = await _read_string(reader)

    def write(self, writer: StreamWriter) -> None:
        _write_string(self.reason, writer)


@autoslots
class ChunkPacket(Packet):
    type = PacketType.CHUNK
    chunk: WorldChunk # Can be None, but that makes Pyright go crazy in server_connection.py lol

    def __init__(self, chunk: Optional[WorldChunk] = None) -> None:
        self.chunk = chunk # type: ignore

    async def read(self, reader: StreamReader) -> None:
        abs_x = await _read_varint(reader)
        abs_y = await _read_varint(reader)
        x = await _read_varint(reader)
        y = await _read_varint(reader)
        data = await reader.readexactly(1024)
        self.chunk = WorldChunk.virtual_chunk(x, y, abs_x, abs_y, data)

    def write(self, writer: StreamWriter) -> None:
        if self.chunk is None:
            writer.write(bytes(1028))
            return
        _write_varint(self.chunk.abs_x, writer)
        _write_varint(self.chunk.abs_y, writer)
        _write_varint(self.chunk.x, writer)
        _write_varint(self.chunk.y, writer)
        writer.write(bytes(self.chunk.get_data()))


@autoslots
class UnloadChunkPacket(Packet):
    type = PacketType.CHUNK_UNLOAD
    x: int
    y: int

    def __init__(self, x: int = 0, y: int = 0) -> None:
        self.x = x
        self.y = y

    async def read(self, reader: StreamReader) -> None:
        self.x = await _read_varint(reader)
        self.y = await _read_varint(reader)

    def write(self, writer: StreamWriter) -> None:
        _write_varint(self.x, writer)
        _write_varint(self.y, writer)


@autoslots
class ChunkUpdatePacket(Packet):
    type = PacketType.CHUNK_UPDATE
    cx: int
    cy: int
    bx: int
    by: int
    block: BlockTypes

    def __init__(self, cx: int = 0, cy: int = 0, bx: int = 0, by: int = 0, block: BlockTypes = BlockTypes.AIR) -> None:
        self.cx = cx
        self.cy = cy
        self.bx = bx
        self.by = by
        self.block = block

    async def read(self, reader: StreamReader) -> None:
        self.cx = await _read_varint(reader)
        self.cy = await _read_varint(reader)
        block_info = await reader.readexactly(3)
        self.bx = block_info[0]
        self.by = block_info[1]
        self.block = BlockTypes(block_info[2])

    def write(self, writer: StreamWriter) -> None:
        _write_varint(self.cx, writer)
        _write_varint(self.cy, writer)
        writer.write(bytes((self.bx, self.by, self.block)))


@autoslots
class PlayerPositionPacket(Packet):
    type = PacketType.PLAYER_POS
    x: float
    y: float

    def __init__(self, x: float = 0, y: float = 0) -> None:
        self.x = x
        self.y = y

    async def read(self, reader: StreamReader) -> None:
        self.x = await _read_double(reader)
        self.y = await _read_double(reader)

    def write(self, writer: StreamWriter) -> None:
        _write_double(self.x, writer)
        _write_double(self.y, writer)


@autoslots
class AddVelocityPacket(Packet):
    type = PacketType.ADD_VELOCITY
    x: float
    y: float

    def __init__(self, x: float = 0, y: float = 0) -> None:
        self.x = x
        self.y = y

    async def read(self, reader: StreamReader) -> None:
        self.x = await _read_double(reader)
        self.y = await _read_double(reader)

    def write(self, writer: StreamWriter) -> None:
        _write_double(self.x, writer)
        _write_double(self.y, writer)


class ChatPacket(Packet):
    type = PacketType.CHAT
    message: str
    time: float

    def __init__(self, message: str = '', time: float = 0) -> None:
        self.message = message
        self.time = time

    async def read(self, reader: StreamReader) -> None:
        self.message = await _read_string(reader)
        self.time = await _read_double(reader)

    def write(self, writer: StreamWriter) -> None:
        _write_string(self.message, writer)
        _write_double(self.time, writer)


PACKET_CLASSES: list[type[Packet]] = [
    OfflineAuthenticatePacket,
    OfflineAuthenticatePacket,
    DisconnectPacket,
    PingPacket,
    ChunkPacket,
    UnloadChunkPacket,
    ChunkUpdatePacket,
    PlayerPositionPacket,
    PlayerPositionPacket,
    AddVelocityPacket,
    ChatPacket,
]
