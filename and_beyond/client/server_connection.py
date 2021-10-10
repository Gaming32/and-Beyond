import asyncio
import logging
import math
import threading
import time
import uuid
from asyncio.exceptions import CancelledError
from asyncio.streams import StreamReader, StreamWriter
from typing import Optional

import janus
import pygame
import pygame.event
from and_beyond.client import globals
from and_beyond.client.chat import ClientChatMessage
from and_beyond.client.consts import (SERVER_CONNECT_EVENT,
                                      SERVER_DISCONNECT_EVENT)
from and_beyond.client.globals import GameStatus
from and_beyond.client.world import ClientChunk
from and_beyond.common import PORT, PROTOCOL_VERSION
from and_beyond.middleware import (BufferedWriterMiddleware, ReaderMiddleware,
                                   WriterMiddleware)
from and_beyond.packet import (ChatPacket, ChunkPacket, ChunkUpdatePacket,
                               DisconnectPacket, OfflineAuthenticatePacket,
                               Packet, PingPacket, PlayerPositionPacket,
                               UnloadChunkPacket, read_packet, write_packet)


class ServerConnection:
    _reader: StreamReader
    _writer: StreamWriter
    reader: Optional[ReaderMiddleware]
    writer: Optional[WriterMiddleware]
    thread: threading.Thread
    aio_loop: asyncio.AbstractEventLoop

    running: bool
    outgoing_queue: Optional[janus.Queue[Packet]]
    send_packets_task: Optional[asyncio.Task]

    disconnect_reason: Optional[str]
    _should_post_event: bool

    def __init__(self) -> None:
        self.reader = None
        self.writer = None
        self.running = False
        self.outgoing_queue = None
        self.send_packets_task = None
        self.disconnect_reason = None
        self._should_post_event = True

    def start(self, server: str, port: int = PORT) -> None:
        logging.debug('Starting connection thread...')
        self.thread = threading.Thread(name='ConnectionThread', target=self.start_thread, args=(server, port))
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        self._should_post_event = False

    def start_thread(self, server: str, port: int = PORT) -> None:
        self.running = True
        self.aio_loop = asyncio.new_event_loop()
        try:
            self.aio_loop.run_until_complete(self.main(server, port))
        finally:
            self.aio_loop.run_until_complete(self.shutdown())

    async def main(self, server: str, port: int = PORT) -> None:
        logging.info('Connecting to server %s:%i...', server, port)
        globals.connecting_status = (
            'Connecting to server'
            + (f' {server}' + (f':{port}' if port != PORT else '') if server != 'localhost' else '')
        )
        try:
            self._reader, self._writer = await asyncio.open_connection(server, port)
        except OSError as e:
            self.disconnect_reason = f'Failed to connect:\n{e}'
            logging.error('Failed to connect to server %s', server, exc_info=True)
            return
        self.reader = self._reader
        self.writer = BufferedWriterMiddleware(self._writer)
        logging.debug('Authenticating with server...')
        globals.connecting_status = 'Authenticating'
        auth = OfflineAuthenticatePacket(
            uuid.UUID(int=0),
            globals.config.config['nickname'],
            PROTOCOL_VERSION # Explicit > implicit
        )
        await write_packet(auth, self.writer)
        logging.info('Connected to server')
        globals.connecting_status = 'Connected'
        globals.game_status = GameStatus.IN_GAME
        pygame.event.post(pygame.event.Event(SERVER_CONNECT_EVENT))
        globals.local_world.load()
        self.send_packets_task = self.aio_loop.create_task(self.send_outgoing_packets())
        time_since_ping = 0
        it_start = time.perf_counter()
        while self.running:
            it_end = time.perf_counter()
            time_since_ping += it_end - it_start
            if time_since_ping > 10: # Server hasn't responded for 10 seconds, it's probably down
                self.disconnect_reason = 'The server stopped responding'
                self.running = False
                break
            it_start = time.perf_counter()
            try:
                packet = await read_packet(self.reader)
            except ConnectionError as e:
                self.disconnect_reason = f'Connection lost ({e})'
                self.running = False
                break
            await asyncio.sleep(0)
            if isinstance(packet, ChunkPacket):
                # The chunk is never None when recieved from the network
                chunk = packet.chunk
                client_chunk = ClientChunk(chunk)
                globals.local_world.loaded_chunks[(chunk.abs_x, chunk.abs_y)] = client_chunk
            elif isinstance(packet, UnloadChunkPacket):
                globals.local_world.loaded_chunks.pop((packet.x, packet.y), None)
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
            elif isinstance(packet, DisconnectPacket):
                logging.info('Disconnected from server: %s', packet.reason)
                self.disconnect_reason = packet.reason
                self.running = False
            elif isinstance(packet, PingPacket):
                time_since_ping = 0
            elif isinstance(packet, ChatPacket):
                logging.info('CHAT: %s', packet.message)
                globals.chat_client.add_message(ClientChatMessage(packet.message, packet.time))

    async def send_outgoing_packets(self) -> None:
        self.outgoing_queue = janus.Queue()
        try:
            while self.running:
                if self.writer is None:
                    await asyncio.sleep(0)
                    continue
                await write_packet(await self.outgoing_queue.async_q.get(), self.writer)
        except CancelledError:
            while not self.outgoing_queue.async_q.empty():
                if self.writer is None:
                    await asyncio.sleep(0)
                    break
                try:
                    await write_packet(await self.outgoing_queue.async_q.get(), self.writer)
                except ConnectionError:
                    await asyncio.sleep(0)
                    break
            self.outgoing_queue.close()
            raise

    async def shutdown(self) -> None:
        if self.disconnect_reason is None:
            logging.info('Disconnecting from server...')
        else:
            logging.info('Disconnected from server: %s', self.disconnect_reason)
        if self.send_packets_task is not None:
            self.send_packets_task.cancel()
        if self.writer is not None:
            self.writer.close()
        if self.outgoing_queue is not None:
            self.outgoing_queue.close()
        globals.local_world.unload()
        globals.player.x = globals.player.render_x = math.inf
        globals.player.y = globals.player.render_y = math.inf
        if self.writer is not None:
            try:
                await self.writer.wait_closed()
            except ConnectionError:
                pass
        self.writer = None
        if self._should_post_event:
            try:
                pygame.event.post(pygame.event.Event(SERVER_DISCONNECT_EVENT, reason=self.disconnect_reason))
            except pygame.error: # When the close button (on the window) is used, the event system has been shutdown already
                pass
        globals.game_connection = None

    def write_packet_sync(self, packet: Packet) -> None:
        if self.outgoing_queue is not None:
            try:
                self.outgoing_queue.sync_q.put(packet)
            except RuntimeError:
                pass
