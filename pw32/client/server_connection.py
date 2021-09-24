import asyncio
import logging
import socket
import threading
import uuid
from asyncio.exceptions import CancelledError
from asyncio.streams import StreamReader, StreamWriter
from typing import Optional

import janus
from pw32.client import globals
from pw32.client.globals import GameStatus
from pw32.client.world import ClientChunk
from pw32.common import PORT
from pw32.packet import (AuthenticatePacket, ChunkPacket, ChunkUpdatePacket,
                         Packet, PacketType, PlayerPositionPacket, UnloadChunkPacket, read_packet, write_packet)
from pw32.world import WorldChunk


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
        globals.connecting_status = 'Connecting to server' + (f' {server}' if server != 'localhost' else '')
        while True:
            try:
                self.reader, self.writer = await asyncio.open_connection(server, PORT)
            except ConnectionError: # Linux and when debugging :)
                await asyncio.sleep(0)
            else:
                break
        logging.debug('Authenticating with server...')
        globals.connecting_status = 'Authenticating'
        auth = AuthenticatePacket(uuid.UUID(int=23984)) # Why not? This will be more rigorous in the future
        await write_packet(auth, self.writer)
        logging.info('Connected to server')
        globals.connecting_status = 'Connected'
        globals.game_status = GameStatus.IN_GAME
        globals.local_world.load()
        self.send_packets_task = self.aio_loop.create_task(self.send_outgoing_packets())
        while self.running:
            packet = await read_packet(self.reader)
            if isinstance(packet, ChunkPacket):
                # The chunk is never None when recieved from the network
                chunk = packet.chunk
                client_chunk = ClientChunk(chunk)
                globals.local_world.loaded_chunks[(chunk.abs_x, chunk.abs_y)] = client_chunk
            elif isinstance(packet, UnloadChunkPacket):
                # The chunk is never None when recieved from the network
                globals.local_world.loaded_chunks.pop((packet.x, packet.y))
            elif isinstance(packet, ChunkUpdatePacket):
                world = globals.local_world
                chunk_pos = (packet.cx, packet.cy)
                if chunk_pos in world.loaded_chunks:
                    chunk = world.loaded_chunks[chunk_pos]
                    chunk.set_tile_type(packet.bx, packet.by, packet.block)
                    chunk.dirty = True
            elif isinstance(packet, PlayerPositionPacket):
                # globals.player.last_x = globals.player.render_x = globals.player.x
                # globals.player.last_y = globals.player.render_y = globals.player.y
                globals.player.x = packet.x
                globals.player.y = packet.y

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
        globals.local_world.unload()
        if self.send_packets_task is not None:
            self.send_packets_task.cancel()
        self.writer.close()
        await self.writer.wait_closed()

    def write_packet_sync(self, packet: Packet) -> None:
        if hasattr(self, 'outgoing_queue') and not self.outgoing_queue.closed:
            self.outgoing_queue.sync_q.put(packet) # Black hole for packets sent when not connected
