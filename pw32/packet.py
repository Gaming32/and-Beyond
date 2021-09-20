import abc
from asyncio.streams import StreamWriter
import enum
from asyncio import StreamReader
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


def _write_ushort(value: int, writer: StreamWriter) -> None:
    writer.write(value.to_bytes(2, 'little', signed=False))


def _write_string(value: str, writer: StreamWriter) -> None:
    enc = value.encode('utf-8')
    _write_ushort(len(enc), writer)
    writer.write(enc)


# Packet classes

class AuthenticatePacket(Packet):
    type = PacketType.AUTHENTICATE


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
