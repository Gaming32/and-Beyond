from asyncio import StreamReader, StreamWriter
from pw32.packet import DisconnectPacket, write_packet
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pw32.server.main import AsyncServer


class Client:
    server: 'AsyncServer'
    reader: StreamReader
    writer: StreamWriter

    def __init__(self, server: 'AsyncServer', reader: StreamReader, writer: StreamWriter) -> None:
        self.server = server
        self.reader = reader
        self.writer = writer
    
    async def tick(self) -> None:
        pass

    async def disconnect(self, reason: str = '') -> None:
        packet = DisconnectPacket(reason)
        await write_packet(packet, self.writer)
        self.writer.close()
        await self.writer.wait_closed()
