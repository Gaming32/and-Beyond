import abc
import enum
import struct
import uuid
from asyncio import StreamReader
from asyncio.streams import StreamWriter
from typing import Optional, TypeVar

from pw32.utils import autoslots
from pw32.world import BlockTypes, WorldChunk

T = TypeVar('T', bound=int)
_D = struct.Struct('<d')


class PacketType(enum.IntEnum):
    AUTHENTICATE = 0
    DISCONNECT = 1
    CHUNK = 2
    CHUNK_UPDATE = 3
    # PLAYER_INFO = 4 # Reserved for future use
    PLAYER_POS = 5


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
    _write_ushort(packet.type, writer)
    packet.write(writer)
    await writer.drain()


async def _read_ushort(reader: StreamReader, factory: type[T] = int) -> T:
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
    return (await reader.readexactly(await _read_ushort(reader))).decode('utf-8')


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
    _write_ushort(len(enc), writer)
    writer.write(enc)


def _write_uuid(value: uuid.UUID, writer: StreamWriter) -> None:
    writer.write(value.bytes)


# Packet classes

class AuthenticatePacket(Packet):
    type = PacketType.AUTHENTICATE
    auth_id: uuid.UUID

    def __init__(self, auth_id: uuid.UUID = uuid.UUID(int=0)) -> None:
        self.auth_id = auth_id

    async def read(self, reader: StreamReader) -> None:
        self.auth_id = await _read_uuid(reader)

    def write(self, writer: StreamWriter) -> None:
        _write_uuid(self.auth_id, writer)


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


PACKET_CLASSES: list[type[Packet]] = [
    AuthenticatePacket,
    DisconnectPacket,
    ChunkPacket,
    ChunkUpdatePacket,
    PlayerPositionPacket,
    PlayerPositionPacket,
]
