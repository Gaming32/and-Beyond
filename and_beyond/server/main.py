import asyncio
import logging
import os
import random
import sys
import threading
import time
from asyncio.base_events import Server
from asyncio.events import AbstractEventLoop
from asyncio.streams import StreamReader, StreamWriter
from typing import Any, BinaryIO, Optional

from and_beyond.common import PORT
from and_beyond.packet import ChunkUpdatePacket, read_packet, write_packet
from and_beyond.pipe_commands import PipeCommands
from and_beyond.server.client import Client
from and_beyond.server.consts import GC_TIME_SECONDS
from and_beyond.server.world_gen.core import WorldGenerator
from and_beyond.world import BlockTypes, World

if sys.platform == 'win32':
    import msvcrt

import colorama
from and_beyond.utils import autoslots, init_logger


@autoslots
class AsyncServer:
    loop: AbstractEventLoop
    singleplayer_pipe: Optional[BinaryIO]
    multiplayer: bool
    running: bool
    paused: bool
    has_been_shutdown: bool
    gc_task: asyncio.Task

    async_server: Server
    clients: list[Client]

    last_spt: float
    world: World
    world_generator: WorldGenerator

    def __init__(self) -> None:
        self.loop = None # type: ignore
        self.singleplayer_pipe = None
        self.multiplayer = True
        self.running = False
        self.paused = False
        self.has_been_shutdown = False
        self.async_server = None # type: ignore
        self.clients = []
        self.last_spt = 0

    def start(self) -> None:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        with colorama.colorama_text():
            logging.info('Starting server...')
            self.loop = asyncio.get_event_loop()
            try:
                self.loop.run_until_complete(self.main())
            except KeyboardInterrupt:
                raise
            finally:
                self.loop.run_until_complete(self.shutdown())
            logging.info('Server closed')

    def quit(self) -> None:
        self.running = False

    async def receive_singleplayer_commands(self, singleplayer_pipe: BinaryIO):
        while not self.running:
            await asyncio.sleep(0)
        while self.running:
            command = await self.loop.run_in_executor(None, singleplayer_pipe.read, 2)
            command = PipeCommands.from_bytes(command, 'little')
            if command == PipeCommands.SHUTDOWN:
                self.running = False
            elif command == PipeCommands.PAUSE:
                if not self.multiplayer:
                    self.paused = True
            elif command == PipeCommands.UNPAUSE:
                if not self.multiplayer:
                    self.paused = False

    async def set_block(self, cx: int, cy: int, bx: int, by: int, block: BlockTypes) -> None:
        tasks: list[asyncio.Task] = []
        self.world.get_chunk(cx, cy).set_tile_type(bx, by, block)
        chunk_pos = (cx, cy)
        packet = ChunkUpdatePacket(cx, cy, bx, by, block)
        for client in self.clients:
            if chunk_pos in client.loaded_chunks:
                tasks.append(self.loop.create_task(write_packet(packet, client.writer)))
        await asyncio.gather(*tasks)

    async def main(self):
        self.loop = asyncio.get_running_loop()

        try:
            singleplayer_fd = int(sys.argv[sys.argv.index('--singleplayer') + 1])
        except (ValueError, IndexError):
            logging.debug('Server running in multiplayer mode')
            self.singleplayer_pipe = None
            self.multiplayer = True
            host = '0.0.0.0'
        else:
            logging.debug('Server running in singleplayer mode (fd/handle: %i)', singleplayer_fd)
            if sys.platform == 'win32':
                singleplayer_fd = msvcrt.open_osfhandle(singleplayer_fd, os.O_RDONLY)
            else:
                os.set_blocking(singleplayer_fd, True)
            self.singleplayer_pipe = os.fdopen(singleplayer_fd, 'rb', closefd=False)
            self.loop.create_task(self.receive_singleplayer_commands(self.singleplayer_pipe))
            self.multiplayer = False
            host = '127.0.0.1'

        try:
            world_name = sys.argv[sys.argv.index('--world') + 1]
        except IndexError:
            world_name = 'world'
        logging.info('Loading world "%s"', world_name)

        self.world = World(world_name)
        await self.world.ainit()
        self.world_generator = WorldGenerator(self.world.meta['seed'])
        logging.info('Locating spawn location for world...')
        start = time.perf_counter()
        spawn_x, spawn_y = self.world.find_spawn(self.world_generator)
        end = time.perf_counter()
        logging.info('Found spawn location (%i, %i) in %f seconds', spawn_x, spawn_y, end - start)

        await self.listen(host)

        logging.info('Server started')
        self.running = True
        logging.debug('Setting up section GC')
        self.gc_task = self.loop.create_task(self.section_gc())
        while self.running:
            if not self.multiplayer:
                while self.paused and self.running:
                    await asyncio.sleep(0)
            start = time.perf_counter()
            await self.tick()
            end = time.perf_counter()
            self.last_spt = end - start
            await asyncio.sleep(0.05 - self.last_spt)
            if self.last_spt > 1:
                logging.warn('Is the server overloaded? Running %f seconds behind (%i ticks)', self.last_spt, self.last_spt // 0.05)

    async def listen(self, host: str) -> None:
        self.async_server = await asyncio.start_server(self.client_connected, host, PORT)
        self.loop.create_task(self.async_server.start_serving())
        logging.info('Listening on %s:%i', host, PORT)

    async def client_connected(self, reader: StreamReader, writer: StreamWriter) -> None:
        client = Client(self, reader, writer)
        if self.clients:
            self.clients.insert(random.randrange(len(self.clients)), client)
        else:
            self.clients.append(client)
        await client.start()

    async def tick(self) -> None:
        for client in self.clients:
            await client.tick()

    async def section_gc(self):
        while self.running:
            await asyncio.sleep(GC_TIME_SECONDS)
            logging.debug('Starting section GC')
            start = time.perf_counter()
            chunks: set[tuple[int, int]] = set()
            for client in self.clients:
                chunks.update(client.loaded_chunks)
            sections: set[tuple[int, int]] = set()
            for (cx, cy) in chunks:
                sections.add((cx >> 4, cy >> 4))
            to_close = set(self.world.open_sections).difference(sections)
            for (sx, sy) in to_close:
                self.world.get_section(sx, sy).close()
            end = time.perf_counter()
            logging.debug('Successfully closed %i section(s) in %f seconds', len(to_close), end - start)

    async def shutdown(self) -> None:
        logging.info('Shutting down...')
        logging.debug('Cancelling GC task...')
        self.gc_task.cancel()
        logging.debug('Kicking clients...')
        await asyncio.gather(*(client.disconnect('Server closed') for client in self.clients))
        logging.debug('Closing server...')
        self.async_server.close()
        logging.info('Server closed')
        if self.singleplayer_pipe is not None:
            logging.debug('Closing singleplayer pipe...')
            self.singleplayer_pipe.close()
        logging.info('Saving world...')
        section_count = len(self.world.open_sections)
        start = time.perf_counter()
        await self.world.close()
        end = time.perf_counter()
        logging.info('World saved (with %i open section(s)) in %f seconds', section_count, end - start)
        await self.async_server.wait_closed()


def main():
    threading.current_thread().name = 'ServerThread'
    init_logger('server.log')
    AsyncServer().start()


if __name__ == '__main__':
    main()
