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

from pw32.common import PORT
from pw32.pipe_commands import PipeCommands
from pw32.server.client import Client

if sys.platform == 'win32':
    import msvcrt

import colorama
from pw32.utils import init_logger


class AsyncServer:
    loop: AbstractEventLoop
    singleplayer_pipe: Optional[BinaryIO]
    multiplayer: bool
    running: bool
    has_been_shutdown: bool

    async_server: Server
    clients: list[Client]

    last_spt: float

    def start(self) -> None:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        with colorama.colorama_text():
            logging.info('Starting server...')
            self.loop = asyncio.get_event_loop()
            try:
                self.loop.run_until_complete(self.main())
            except KeyboardInterrupt:
                pass
            finally:
                self.loop.run_until_complete(self.shutdown())
            logging.info('Server closed')

    def quit(self) -> None:
        self.running = False

    async def receive_singleplayer_commands(self, singleplayer_pipe: BinaryIO):
        command = await self.loop.run_in_executor(None, singleplayer_pipe.read, 2)
        command = PipeCommands.from_bytes(command, 'little')
        if command == PipeCommands.SHUTDOWN:
            self.running = False

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

        await self.listen(host)

        logging.info('Server started')
        self.running = True
        while self.running:
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
        self.clients.insert(random.randrange(len(self.clients)), client)

    async def tick(self) -> None:
        for client in self.clients:
            await client.tick()

    async def shutdown(self) -> None:
        logging.info('Shutting down...')
        asyncio.gather(*(client.disconnect('Server closed') for client in self.clients))
        self.async_server.close()
        if self.singleplayer_pipe is not None:
            self.singleplayer_pipe.close()
        await self.async_server.wait_closed()


def main():
    threading.current_thread().name = 'ServerThread'
    init_logger()
    AsyncServer().start()


if __name__ == '__main__':
    main()
