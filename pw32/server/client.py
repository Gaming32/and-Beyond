import asyncio
import logging
import uuid
from asyncio import StreamReader, StreamWriter
from typing import TYPE_CHECKING, Optional

from pw32.packet import (AuthenticatePacket, DisconnectPacket, read_packet,
                         write_packet)

if TYPE_CHECKING:
    from pw32.server.main import AsyncServer


class Client:
    server: 'AsyncServer'
    reader: StreamReader
    writer: StreamWriter
    auth_uuid: Optional[uuid.UUID]

    def __init__(self, server: 'AsyncServer', reader: StreamReader, writer: StreamWriter) -> None:
        self.server = server
        self.reader = reader
        self.writer = writer
        self.auth_uuid = None

    async def start(self):
        try:
            auth_packet = await asyncio.wait_for(read_packet(self.reader), 3)
        except asyncio.TimeoutError:
            return await self.disconnect('Authentication timeout')
        if not isinstance(auth_packet, AuthenticatePacket):
            return await self.disconnect('Malformed authentication packet')
        self.auth_uuid = auth_packet.auth_id
        logging.info('Player logged in with UUID %s', self.auth_uuid)

    async def tick(self) -> None:
        pass

    async def disconnect(self, reason: str = '') -> None:
        logging.debug('Disconnecting player %s', self)
        packet = DisconnectPacket(reason)
        await write_packet(packet, self.writer)
        self.writer.close()
        await self.writer.wait_closed()
        try:
            self.server.clients.remove(self)
        except ValueError:
            pass
        logging.info('Player %s disconnected for reason: %s', self, reason)
