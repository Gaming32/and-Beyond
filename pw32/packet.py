import abc
import enum
import uuid
from asyncio import StreamReader
from asyncio.streams import StreamWriter
from typing import TypeVar

T = TypeVar('T', bound=int)


class PacketType(enum.IntEnum):
    AUTHENTICATE = 0
    DISCONNECT = 1


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


async def _read_string(reader: StreamReader) -> str:
    return (await reader.read(await _read_ushort(reader))).decode('utf-8')


async def _read_uuid(reader: StreamReader) -> uuid.UUID:
    return uuid.UUID(bytes=await reader.read(16))


def _write_ushort(value: int, writer: StreamWriter) -> None:
    writer.write(value.to_bytes(2, 'little', signed=False))


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


PACKET_CLASSES: list[type[Packet]] = [
    AuthenticatePacket,
    DisconnectPacket,
]
