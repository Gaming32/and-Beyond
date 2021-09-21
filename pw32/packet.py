import abc
import enum
import uuid
from asyncio import StreamReader
from asyncio.streams import StreamWriter
from typing import Optional, TypeVar

from pw32.world import WorldChunk
from pw32.utils import autoslots

T = TypeVar('T', bound=int)


class PacketType(enum.IntEnum):
    AUTHENTICATE = 0
    DISCONNECT = 1
    CHUNK = 2


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
    return factory.from_bytes(await reader.read(2), 'little', signed=False) # type: ignore


async def _read_varint(reader: StreamReader) -> int:
    result = 0
    offset = 0
    while True:
        b = (await reader.read(1))[0]
        result |= (b & 0b01111111) << offset
        if not (b & 0b10000000):
            return result
        offset += 7


async def _read_string(reader: StreamReader) -> str:
    return (await reader.read(await _read_ushort(reader))).decode('utf-8')


async def _read_uuid(reader: StreamReader) -> uuid.UUID:
    return uuid.UUID(bytes=await reader.read(16))


def _write_ushort(value: int, writer: StreamWriter) -> None:
    writer.write(value.to_bytes(2, 'little', signed=False))


def _write_varint(value: int, writer: StreamWriter) -> None:
    while True:
        if not (value & 0xFFFFFF80):
            writer.write(bytes((value,)))
            return
        writer.write(bytes((value & 0x7F | 0x80,)))
        value >>= 7


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
    chunk: Optional[WorldChunk]

    def __init__(self, chunk: Optional[WorldChunk] = None) -> None:
        self.chunk = chunk

    async def read(self, reader: StreamReader) -> None:
        abs_x = await _read_varint(reader)
        abs_y = await _read_varint(reader)
        x = await _read_varint(reader)
        y = await _read_varint(reader)
        data = await reader.read(1024)
        self.chunk = WorldChunk.virtual_chunk(x, y, abs_x, abs_y, data)

    def write(self, writer: StreamWriter) -> None:
        if self.chunk is None:
            writer.write(bytes(1028))
            return
        _write_varint(self.chunk.abs_x, writer)
        _write_varint(self.chunk.abs_y, writer)
        _write_varint(self.chunk.x, writer)
        _write_varint(self.chunk.y, writer)
        writer.write(self.chunk.get_data())


PACKET_CLASSES: list[type[Packet]] = [
    AuthenticatePacket,
    DisconnectPacket,
    ChunkPacket,
]
