import asyncio
import itertools
import logging
import os
import random
import sys
import threading
import time
from asyncio.base_events import Server
from asyncio.events import AbstractEventLoop
from asyncio.streams import StreamReader, StreamWriter
from collections import deque
from fractions import Fraction
from typing import Any, BinaryIO, Optional
from uuid import UUID

import colorama

import and_beyond.server.builtin_commands  # pyright: ignore [reportUnusedImport]
from and_beyond import blocks
from and_beyond.blocks import Block
from and_beyond.common import AUTH_SERVER, PORT, RANDOM_TICK_RATE
from and_beyond.http_auth import AuthClient
from and_beyond.http_errors import InsecureAuth
from and_beyond.packet import ChunkUpdatePacket, Packet, write_packet
from and_beyond.pipe_commands import PipeCommandsToServer, read_pipe
from and_beyond.server.client import Client
from and_beyond.server.commands import DEFAULT_COMMANDS, AbstractCommandSender, CommandDict, ConsoleCommandSender
from and_beyond.server.consts import GC_TIME_SECONDS
from and_beyond.server.world_gen.core import WorldGenerator
from and_beyond.text import MaybeText, translatable_text
from and_beyond.utils import ainput, autoslots, get_opt, init_logger, mean, shuffled
from and_beyond.world import World, WorldChunk

if sys.platform == 'win32':
    import msvcrt


@autoslots
class AsyncServer:
    random_tick_rate: Fraction
    commands: CommandDict

    loop: AbstractEventLoop
    singleplayer_pipe_in: Optional[BinaryIO]
    singleplayer_pipe_out: Optional[BinaryIO]
    multiplayer: bool
    running: bool
    paused: bool
    has_been_shutdown: bool
    gc_task: Optional[asyncio.Task[None]]
    all_loaded_chunks: dict[tuple[int, int], 'WorldChunk']

    host: str
    port: int
    async_server: Optional[Server]
    clients: list[Client]
    clients_by_uuid: dict[UUID, Client]
    clients_by_name: dict[str, Client]

    last_tps_values: deque[float]
    last_mspt_values: deque[float]
    auth_client: Optional[AuthClient]
    command_sender: ConsoleCommandSender

    last_spt: float
    world: Optional[World]
    world_generator: WorldGenerator

    pipe_commands_task: Optional[asyncio.Task[None]]
    console_commands_task: Optional[asyncio.Task[None]]

    def __init__(self) -> None:
        self.random_tick_rate = Fraction(RANDOM_TICK_RATE)
        self.commands = DEFAULT_COMMANDS.copy()
        self.singleplayer_pipe_in = None
        self.singleplayer_pipe_out = None
        self.multiplayer = True
        self.running = False
        self.paused = False
        self.has_been_shutdown = False
        self.gc_task = None
        self.all_loaded_chunks = {}
        self.async_server = None
        self.world = None
        self.clients = []
        self.clients_by_uuid = {}
        self.clients_by_name = {}
        self.last_spt = 0
        self.last_tps_values = deque(maxlen=600)
        self.last_mspt_values = deque(maxlen=600)
        self.command_sender = ConsoleCommandSender(self)
        self.pipe_commands_task = None
        self.console_commands_task = None

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

    async def read_console_commands(self) -> None:
        while not self.running:
            await asyncio.sleep(0)
        while self.running:
            command = (await ainput()).strip()
            if not command:
                continue
            if command[0] == '/':
                command = command[1:]
            await self.run_command(command, self.command_sender)

    async def receive_singleplayer_commands(self, pipe: BinaryIO) -> None:
        while not self.running:
            await asyncio.sleep(0)
        assert self.async_server is not None
        while self.running:
            command = await self.loop.run_in_executor(None, pipe.read, 2)
            command = PipeCommandsToServer.from_bytes(command, 'little')
            if command == PipeCommandsToServer.SHUTDOWN:
                self.running = False
            elif command == PipeCommandsToServer.PAUSE:
                if not self.multiplayer:
                    self.paused = True
            elif command == PipeCommandsToServer.UNPAUSE:
                self.paused = False
            elif command == PipeCommandsToServer.OPEN_TO_LAN:
                self.async_server.close()
                port = read_pipe(pipe)
                assert port is not None
                await self.async_server.wait_closed()
                await self.listen('0.0.0.0', port)
                self.multiplayer = True
                self.paused = False
                await self.send_chat(f'Opened to LAN on port {self.port}')

    async def set_block(self, cx: int, cy: int, bx: int, by: int, block: Block) -> None:
        assert self.world is not None
        tasks: list[asyncio.Task[None]] = []
        chunk = self.world.get_chunk(cx, cy)
        chunk.set_tile_type(bx, by, block)
        chunk_pos = (cx, cy)
        packet = ChunkUpdatePacket(cx, cy, bx, by, block, chunk.get_packed_lighting(bx, by))
        for client in self.clients:
            if chunk_pos in client.loaded_chunks:
                tasks.append(self.loop.create_task(write_packet(packet, client.writer)))
        await asyncio.gather(*tasks)

    async def main(self) -> None:
        try:
            singleplayer_pos = sys.argv.index('--singleplayer')
            singleplayer_fd_in = int(sys.argv[singleplayer_pos + 1])
            singleplayer_fd_out = int(sys.argv[singleplayer_pos + 2])
        except (ValueError, IndexError):
            logging.debug('Server running in multiplayer mode')
            self.singleplayer_pipe_in = None
            self.multiplayer = True
            host = '0.0.0.0'
            port = PORT
            self.console_commands_task = self.loop.create_task(
                self.read_console_commands()
            )
        else:
            logging.debug('Server running in singleplayer mode (fd/handle: %i (in), %i (out))', singleplayer_fd_in, singleplayer_fd_out)
            if sys.platform == 'win32':
                singleplayer_fd_in = msvcrt.open_osfhandle(singleplayer_fd_in, os.O_RDONLY)
                singleplayer_fd_out = msvcrt.open_osfhandle(singleplayer_fd_out, os.O_WRONLY)
            else:
                os.set_blocking(singleplayer_fd_in, True)
            self.singleplayer_pipe_in = os.fdopen(singleplayer_fd_in, 'rb', closefd=False)
            self.singleplayer_pipe_out = os.fdopen(singleplayer_fd_out, 'wb', closefd=False)
            self.pipe_commands_task = self.loop.create_task(
                self.receive_singleplayer_commands(self.singleplayer_pipe_in)
            )
            self.multiplayer = False
            host = '127.0.0.1'
            port = None

        try:
            listen_addr = get_opt('--listen')
        except (ValueError, IndexError):
            pass
        else:
            try:
                host_arg, port_arg = listen_addr.rsplit(':', 1)
            except ValueError:
                logging.critical('Invalid --listen argument: %s', listen_addr)
                return
            else:
                if host_arg:
                    host = host_arg
                if port_arg:
                    try:
                        port = int(port_arg)
                    except ValueError:
                        logging.critical('Port not integer: %s', port_arg)
                        return

        if '--offline-mode' in sys.argv:
            self.auth_client = None
            logging.warning(
                '**WARNING** Offline mode is enabled. Hackers will be able to log in as anybody they choose.'
            )
        else:
            try:
                auth_server = get_opt('--auth-server')
            except (ValueError, IndexError):
                auth_server = AUTH_SERVER
            if '://' not in auth_server:
                auth_server = 'http://' + auth_server
            allow_insecure_auth = '--insecure-auth' in sys.argv
            self.auth_client = AuthClient(auth_server, allow_insecure_auth)
            try:
                await self.auth_client.ping()
            except Exception as e:
                if isinstance(e, InsecureAuth):
                    logging.critical('Requested auth server is insecure (uses HTTP '
                                    'instead of HTTPS). You can bypass this with '
                                    'the --insecure-auth command-line switch.')
                    return
                logging.warn('Failed to ping the auth server', exc_info=True)

        try:
            world_name = get_opt('--world')
        except (ValueError, IndexError):
            world_name = 'world'
        logging.info('Loading world "%s"', world_name)

        self.world = World(world_name, auto_optimize=True)
        await self.world.ainit('--no-optimize' not in sys.argv)
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
        self.running = '--no-op' not in sys.argv
        if not self.running:
            logging.info('Running in no-op mode')
        logging.debug('Setting up backup section GC')
        self.gc_task = self.loop.create_task(self.section_gc())
        time_since_last_second = 0
        while self.running:
            if not self.multiplayer:
                while self.paused and self.running:
                    await asyncio.sleep(0)
            start = time.perf_counter()
            await self.tick()
            end = time.perf_counter()
            self.last_spt = end - start
            await asyncio.sleep(0.05 - self.last_spt)
            time_since_last_second += max(self.last_spt, 0.05)
            if self.last_spt > 1:
                logging.warn('Is the server overloaded? Running %f seconds behind (%i ticks)', self.last_spt, self.last_spt // 0.05)
            if time_since_last_second > 1:
                time_since_last_second -= 1
                self.last_tps_values.append(1 / self.last_spt)
                self.last_mspt_values.append(self.last_spt * 1000)

    async def listen(self, host: str, port: Optional[int] = None) -> None:
        logging.debug('Trying to listen on %s:%s', host, port)
        try:
            self.async_server = await asyncio.start_server(self.client_connected, host, port)
        except Exception:
            logging.critical('Failed to listen on %s:%s', host, port, exc_info=True)
            raise SystemExit # This feels more proper than sys.exit(), since we know that it won't exit right away anyway
        else:
            self.host, self.port, *_ = self.async_server.sockets[0].getsockname()
            logging.info('Listening on %s:%i', self.host, self.port)

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
            await self.random_tick()
        else:
            await asyncio.sleep(0)

    async def random_tick(self) -> None:
        chunk_rate = self.random_tick_rate.denominator
        block_rate = self.random_tick_rate.numerator
        if chunk_rate == 1:
            for chunk in list(self.all_loaded_chunks.values()):
                for i in range(block_rate):
                    await self.random_tick_chunk(chunk, random.randrange(16), random.randrange(16))
        else:
            chunk_rate -= 1
            i = 0
            for chunk in shuffled(self.all_loaded_chunks.values()):
                if i == 0:
                    for j in range(block_rate):
                        await self.random_tick_chunk(chunk, random.randrange(16), random.randrange(16))
                i += 1
                if i > chunk_rate:
                    i = 0

    async def random_tick_chunk(self, chunk: WorldChunk, x: int, y: int) -> None:
        block = chunk.get_tile_type(x, y)
        if block == blocks.GRASS:
            block_above = self.get_block_rel_chunk(chunk, x, y + 1)
            if block_above is None:
                return
            if block_above.bounding_box is not None:
                # Reset to dirt
                await self.set_tile_type_global(chunk, x, y, blocks.DIRT)
            else:
                # Spread
                for dir in (-1, 1):
                    chunk_off, x_off, _ = self.get_block_rel_pos(chunk, x + dir, y)
                    if chunk_off is not None:
                        chunk_above, _, y_above = self.get_block_rel_pos(chunk_off, x_off, y + 1)
                        block_above = self.get_block_rel_chunk(chunk_above, x_off, y_above)
                        if (
                            chunk_off.get_tile_type(x_off, y) == blocks.DIRT
                            and (block_above is None or block_above.bounding_box is None)
                        ):
                            await self.set_tile_type_global(chunk_off, x_off, y, block)
                        elif block_above == blocks.DIRT:
                            chunk_above_2, _, y_above_2 = self.get_block_rel_pos(chunk_above, x_off, y_above + 1)
                            block_above_2 = self.get_block_rel_chunk(chunk_above_2, x_off, y_above_2)
                            if block_above_2 is None or block_above_2.bounding_box is None:
                                await self.set_block_rel_chunk_global(chunk_above, x_off, y_above, block)

    async def section_gc(self) -> None:
        while not self.running:
            await asyncio.sleep(0)
        assert self.world is not None
        while self.running:
            await asyncio.sleep(GC_TIME_SECONDS)
            logging.debug('Running backup section GC')
            start = time.perf_counter()
            chunks: set[tuple[int, int]] = set()
            for client in self.clients:
                if not client.ready:
                    continue
                chunks.update(client.loaded_chunks)
            for chunk in set(self.all_loaded_chunks) - chunks:
                self.all_loaded_chunks.pop(chunk, None)
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
        if self.console_commands_task is not None:
            self.console_commands_task.cancel()
        if self.gc_task is not None:
            logging.debug('Cancelling backup GC task...')
            self.gc_task.cancel()
        logging.debug('Kicking clients...')
        await asyncio.gather(*(client.disconnect('Server closed') for client in self.clients))
        if self.async_server is not None:
            logging.debug('Closing server...')
            self.async_server.close()
        if self.auth_client is not None:
            logging.debug('Closing auth client...')
            await self.auth_client.close()
        logging.debug('Closing singleplayer pipes...')
        if self.singleplayer_pipe_in is not None:
            self.singleplayer_pipe_in.close()
        if self.singleplayer_pipe_out is not None:
            self.singleplayer_pipe_out.close()
        if self.pipe_commands_task is not None:
            self.pipe_commands_task.cancel()
        if self.world is not None:
            logging.info('Saving world...')
            section_count = len(self.world.open_sections)
            start = time.perf_counter()
            await self.world.close()
            end = time.perf_counter()
            logging.info('World saved (with %i open section(s)) in %f seconds', section_count, end - start)
        if self.async_server is not None:
            await self.async_server.wait_closed()

    def get_block_rel_pos(self, chunk: Optional[WorldChunk], x: int, y: int) -> tuple[Optional[WorldChunk], int, int]:
        if 0 <= x < 16 and 0 <= y < 16:
            return chunk, x, y
        if x > 15 or x < 0:
            x2 = x >> 4
            x -= x2 << 4
        else:
            x2 = 0
        if y > 15 or y < 0:
            y2 = y >> 4
            y -= y2 << 4
        else:
            y2 = 0
        if chunk is not None:
            chunk = self.all_loaded_chunks.get((chunk.abs_x + x2, chunk.abs_y + y2))
        return chunk, x, y

    def get_block_rel_chunk(self, chunk: Optional[WorldChunk], x: int, y: int) -> Optional[Block]:
        chunk, x, y = self.get_block_rel_pos(chunk, x, y)
        if chunk is None:
            return None
        return chunk.get_tile_type(x, y)

    def set_block_rel_chunk(self, chunk: Optional[WorldChunk], x: int, y: int, block: Block) -> bool:
        chunk, x, y = self.get_block_rel_pos(chunk, x, y)
        if chunk is None:
            return False
        chunk.set_tile_type(x, y, block)
        return True

    async def set_block_rel_chunk_global(self, chunk: Optional[WorldChunk], x: int, y: int, block: Block) -> bool:
        chunk, x, y = self.get_block_rel_pos(chunk, x, y)
        if chunk is None:
            return False
        await self.set_tile_type_global(chunk, x, y, block)
        return True

    async def set_tile_type_global(self,
        chunk: WorldChunk,
        x: int, y: int,
        type: Block,
        exclude_player: Optional[Client] = None
    ) -> None:
        chunk.set_tile_type(x, y, type)
        cpos = (chunk.abs_x, chunk.abs_y)
        packet = ChunkUpdatePacket(
            chunk.abs_x, chunk.abs_y,
            x, y,
            type,
            chunk.get_packed_lighting(x, y)
        )
        await self.send_to_all(packet, cpos, exclude_player)

    async def send_to_all(self,
        packet: Packet,
        cpos_only: Optional[tuple[int, int]] = None,
        exclude_player: Optional[Client] = None
    ) -> tuple[None, ...]:
        tasks: list[asyncio.Task[None]] = []
        for client in self.clients:
            if client is exclude_player:
                continue
            if cpos_only is None or cpos_only in client.loaded_chunks:
                tasks.append(self.loop.create_task(write_packet(packet, client.writer)))
        return await asyncio.gather(*tasks)

    async def run_command(self, cmd: str, sender: AbstractCommandSender) -> Any:
        name, *rest = cmd.split(' ', 1)
        if name in self.commands:
            command = self.commands[name]
            await command.call(sender, rest[0] if rest else '')
        else:
            message = translatable_text('server.unknown_command').with_format_params(name)
            if not isinstance(sender, ConsoleCommandSender):
                logging.info('<%s> %s', sender, message)
            await sender.reply(message)

    def get_tps(self, time: int = 60) -> float:
        return mean(itertools.islice(self.last_tps_values, max(len(self.last_tps_values) - time, 0), None))

    def get_tps_str(self, time: int = 60) -> str:
        tps = self.get_tps(time)
        return f'>20.0' if tps > 20.0 else f'{tps:.1f}'

    def get_multi_tps_str(self) -> str:
        results = []
        for time in (60, 300, 600):
            results.append(self.get_tps_str(time))
        return f'TPS from last 1m, 5m, 10m: ' + ', '.join(results)

    def get_mspt(self, time: int = 60) -> float:
        return mean(itertools.islice(self.last_mspt_values, max(len(self.last_mspt_values) - time, 0), None))

    def get_mspt_str(self, time: int = 60) -> str:
        mspt = self.get_mspt(time)
        return f'{mspt:.2f}'

    def get_multi_mspt_str(self) -> str:
        results = []
        for time in (60, 300, 600):
            results.append(self.get_mspt_str(time))
        return f'MSPT from last 1m, 5m, 10m: ' + ', '.join(results)

    def __repr__(self) -> str:
        return f'<AsyncServer{" SINGLEPLAYER" * (not self.multiplayer)} bind={self.host}:{self.port} world={str(self.world)!r} tps={self.get_tps_str()}>'

    async def send_chat(self, message: MaybeText, at: Optional[float] = None, log: bool = False) -> None:
        if log:
            logging.info('CHAT: %s', message)
        if at is None:
            at = time.time()
        await asyncio.gather(*(
            self.loop.create_task(client.send_chat(message, at))
            for client in self.clients
            if client.ready
        ))


def main() -> None:
    threading.current_thread().name = 'ServerThread'
    init_logger('server.log')
    AsyncServer().start()


if __name__ == '__main__':
    main()
