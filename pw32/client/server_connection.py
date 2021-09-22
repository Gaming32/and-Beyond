import asyncio
from asyncio.exceptions import CancelledError
import logging
from pw32.world import WorldChunk
import socket
import threading
from typing import Optional
import uuid
from asyncio.streams import StreamReader, StreamWriter

import janus
from pw32.client import globals
from pw32.common import PORT
from pw32.packet import AuthenticatePacket, ChunkPacket, Packet, PacketType, read_packet, write_packet


class ServerConnection:
    reader: StreamReader
    writer: StreamWriter
    thread: threading.Thread
    aio_loop: asyncio.AbstractEventLoop

    running: bool
    outgoing_queue: janus.Queue[Packet]
    send_packets_task: Optional[asyncio.Task]

    def __init__(self) -> None:
        self.running = False
        self.send_packets_task = None

    def start(self, server: str) -> None:
        logging.debug('Starting connection thread...')
        self.thread = threading.Thread(name='ConnectionThread', target=self.start_thread, args=(server,))
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    def start_thread(self, server: str) -> None:
        self.running = True
        self.aio_loop = asyncio.new_event_loop()
        try:
            self.aio_loop.run_until_complete(self.main(server))
        finally:
            self.aio_loop.run_until_complete(self.shutdown())

    async def main(self, server: str) -> None:
        logging.info('Connecting to server %s...', server)
        while True:
            try:
                self.reader, self.writer = await asyncio.open_connection(server, PORT)
            except ConnectionRefusedError: # Linux
                await asyncio.sleep(0)
            else:
                break
        logging.debug('Authenticating with server...')
        auth = AuthenticatePacket(uuid.UUID(int=23984)) # Why not? This will be more rigorous in the future
        await write_packet(auth, self.writer)
        logging.info('Connected to server')
        self.send_packets_task = self.aio_loop.create_task(self.send_outgoing_packets())
        while self.running:
            packet = await read_packet(self.reader)
            if isinstance(packet, ChunkPacket):
                # The chunk is never None when recieved from the network
                chunk: WorldChunk = packet.chunk # type: ignore
                logging.debug('Recieved chunk (%i, %i)', chunk.abs_x, chunk.abs_y)
                globals.loaded_chunks[(chunk.abs_x, chunk.abs_y)] = chunk

    async def send_outgoing_packets(self) -> None:
        self.outgoing_queue = janus.Queue()
        try:
            while self.running:
                await write_packet(await self.outgoing_queue.async_q.get(), self.writer)
        except CancelledError:
            while not self.outgoing_queue.async_q.empty():
                await write_packet(await self.outgoing_queue.async_q.get(), self.writer)
            self.outgoing_queue.close()
            raise

    async def shutdown(self) -> None:
        globals.loaded_chunks.clear()
        if self.send_packets_task is not None:
            self.send_packets_task.cancel()
        self.writer.close()
        await self.writer.wait_closed()