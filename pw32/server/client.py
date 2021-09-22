import asyncio
import logging
import uuid
from asyncio import StreamReader, StreamWriter
from asyncio.events import AbstractEventLoop
from asyncio.exceptions import CancelledError
from typing import TYPE_CHECKING, Optional

from pw32.common import MAX_LOADED_CHUNKS, VIEW_DISTANCE, VIEW_DISTANCE_BOX
from pw32.packet import (AuthenticatePacket, ChunkPacket, DisconnectPacket,
                         read_packet, write_packet)
from pw32.utils import MaxSizedDict, spiral_loop, spiral_loop_async
from pw32.world import WorldChunk

if TYPE_CHECKING:
    from pw32.server.main import AsyncServer


class Client:
    server: 'AsyncServer'
    reader: StreamReader
    writer: StreamWriter
    aloop: AbstractEventLoop

    auth_uuid: Optional[uuid.UUID]
    load_chunks_task: asyncio.Task
    loaded_chunks: dict[tuple[int, int], WorldChunk]

    def __init__(self, server: 'AsyncServer', reader: StreamReader, writer: StreamWriter) -> None:
        self.server = server
        self.reader = reader
        self.writer = writer
        self.aloop = server.loop
        self.auth_uuid = None
        self.loaded_chunks = MaxSizedDict(max_size=MAX_LOADED_CHUNKS)

    async def start(self):
        try:
            auth_packet = await asyncio.wait_for(read_packet(self.reader), 3)
        except asyncio.TimeoutError:
            return await self.disconnect('Authentication timeout')
        if not isinstance(auth_packet, AuthenticatePacket):
            return await self.disconnect('Malformed authentication packet')
        self.auth_uuid = auth_packet.auth_id
        logging.info('Player logged in with UUID %s', self.auth_uuid)
        self.load_chunks_task = self.aloop.create_task(self.load_chunks_around_player())

    async def load_chunk(self, x, y):
        chunk = self.server.world.get_generated_chunk(x, y, self.server.world_generator)
        self.loaded_chunks[(x, y)] = chunk
        packet = ChunkPacket(chunk)
        await write_packet(packet, self.writer)

    async def load_chunks_around_player(self):
        async def load_chunk_rel(x, y):
            await asyncio.sleep(0) # Why do I have to do this? I *do* have to for some reason
            if (x, y) in self.loaded_chunks:
                return
            await self.load_chunk(cx + x, cy + y)
        x = 0
        y = 0
        cx = x >> 4
        cy = y >> 4
        await spiral_loop_async(VIEW_DISTANCE_BOX, VIEW_DISTANCE_BOX, load_chunk_rel)

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
        self.load_chunks_task.cancel()
        logging.info('Player %s disconnected for reason: %s', self, reason)
