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
from typing import BinaryIO, Optional

from and_beyond.common import PORT
from and_beyond.packet import ChunkUpdatePacket, write_packet
from and_beyond.pipe_commands import PipeCommandsToClient, PipeCommandsToServer
from and_beyond.server.client import Client
from and_beyond.server.consts import GC_TIME_SECONDS
from and_beyond.server.world_gen.core import WorldGenerator
from and_beyond.world import BlockTypes, World, WorldChunk

if sys.platform == 'win32':
    import msvcrt

import colorama
from and_beyond.utils import autoslots, init_logger


@autoslots
class AsyncServer:
    loop: AbstractEventLoop
    singleplayer_pipe_in: Optional[BinaryIO]
    singleplayer_pipe_out: Optional[BinaryIO]
    multiplayer: bool
    running: bool
    paused: bool
    has_been_shutdown: bool
    gc_task: asyncio.Task

    host: str
    port: int
    async_server: Server
    clients: list[Client]

    last_spt: float
    world: World
    world_generator: WorldGenerator

    def __init__(self) -> None:
        self.loop = None # type: ignore
        self.singleplayer_pipe_in = None
        self.singleplayer_pipe_out = None
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
            except BaseException as e:
                if isinstance(e, Exception):
                    logging.critical('Server crashed hard with exception', exc_info=True)
                elif isinstance(e, KeyboardInterrupt):
                    logging.info('Closing due to keyboard interrupt.')
                else:
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
            command = PipeCommandsToServer.from_bytes(command, 'little')
            if command == PipeCommandsToServer.SHUTDOWN:
                self.running = False
            elif command == PipeCommandsToServer.PAUSE:
                if not self.multiplayer:
                    self.paused = True
            elif command == PipeCommandsToServer.UNPAUSE:
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
            singleplayer_fd_in = int(sys.argv[sys.argv.index('--singleplayer') + 1])
            singleplayer_fd_out = int(sys.argv[sys.argv.index('--singleplayer') + 2])
        except (ValueError, IndexError):
            logging.debug('Server running in multiplayer mode')
            self.singleplayer_pipe_in = None
            self.multiplayer = True
            host = '0.0.0.0'
            port = PORT
        else:
            logging.debug('Server running in singleplayer mode (fd/handle: %i (in), %i (out))', singleplayer_fd_in, singleplayer_fd_out)
            if sys.platform == 'win32':
                singleplayer_fd_in = msvcrt.open_osfhandle(singleplayer_fd_in, os.O_RDONLY)
                singleplayer_fd_out = msvcrt.open_osfhandle(singleplayer_fd_out, os.O_WRONLY)
            else:
                os.set_blocking(singleplayer_fd_in, True)
            self.singleplayer_pipe_in = os.fdopen(singleplayer_fd_in, 'rb', closefd=False)
            self.singleplayer_pipe_out = os.fdopen(singleplayer_fd_out, 'wb', closefd=False)
            self.loop.create_task(self.receive_singleplayer_commands(self.singleplayer_pipe_in))
            self.multiplayer = False
            host = '127.0.0.1'
            port = None

        try:
            world_name = sys.argv[sys.argv.index('--world') + 1]
        except (ValueError, IndexError):
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

        await self.listen(host, port)
        if self.singleplayer_pipe_out is not None:
            self.singleplayer_pipe_out.write(
                self.port.to_bytes(2, 'little', signed=False)
            )
            self.singleplayer_pipe_out.flush()

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

    async def listen(self, host: str, port: Optional[int] = None) -> None:
        self.async_server = await asyncio.start_server(self.client_connected, host, port)
        self.host, self.port = self.async_server.sockets[0].getsockname()
        logging.info('Listening on %s:%i', host, self.port)

    async def client_connected(self, reader: StreamReader, writer: StreamWriter) -> None:
        client = Client(self, reader, writer)
        if self.clients:
            self.clients.insert(random.randrange(len(self.clients)), client)
        else:
            self.clients.append(client)
        await client.start()

    async def tick(self) -> None:
        if self.clients:
            for client in self.clients:
                await client.tick()
        else:
            await asyncio.sleep(0)

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
        try:
            self.gc_task.cancel()
        except AttributeError:
            pass
        logging.debug('Kicking clients...')
        await asyncio.gather(*(client.disconnect('Server closed') for client in self.clients))
        logging.debug('Closing server...')
        self.async_server.close()
        logging.info('Server closed')
        logging.debug('Closing singleplayer pipes...')
        if self.singleplayer_pipe_in is not None:
            self.singleplayer_pipe_in.close()
        if self.singleplayer_pipe_out is not None:
            self.singleplayer_pipe_out.close()
        logging.info('Saving world...')
        section_count = len(self.world.open_sections)
        start = time.perf_counter()
        await self.world.close()
        end = time.perf_counter()
        logging.info('World saved (with %i open section(s)) in %f seconds', section_count, end - start)
        await self.async_server.wait_closed()

    async def set_tile_type_global(self, chunk: WorldChunk, x: int, y: int, type: BlockTypes, exclude_player: Client = None):
        chunk.set_tile_type(x, y, type)
        cpos = (chunk.abs_x, chunk.abs_y)
        packet = ChunkUpdatePacket(chunk.abs_x, chunk.abs_y, x, y, type)
        tasks: list[asyncio.Task] = []
        for player in self.clients:
            if player == exclude_player:
                continue
            if cpos in player.loaded_chunks:
                tasks.append(self.loop.create_task(write_packet(packet, player.writer)))
        await asyncio.gather(*tasks)

    def get_tps(self) -> int:
        return int(1 / self.last_spt)

    def get_tps_str(self) -> str:
        tps = self.get_tps()
        return f'>20.0' if tps > 20.0 else f'{tps:.1f}'

    def __repr__(self) -> str:
        return f'<AsyncServer{" SINGLEPLAYER" * (not self.multiplayer)} bind={self.host}:{self.port} world={str(self.world)!r} tps={self.get_tps_str()}>'


def main():
    threading.current_thread().name = 'ServerThread'
    init_logger('server.log')
    AsyncServer().start()


if __name__ == '__main__':
    main()
