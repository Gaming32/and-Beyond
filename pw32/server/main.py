import asyncio
import logging
import os
import signal
import sys
import threading
from typing import Any, BinaryIO, Optional

from pw32.pipe_commands import PipeCommands

if sys.platform == 'win32':
    import msvcrt

import colorama
from pw32.utils import init_logger


class AsyncServer:
    loop: asyncio.AbstractEventLoop
    singleplayer_pipe: Optional[BinaryIO]
    running: bool
    has_been_shutdown: bool

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
        else:
            logging.debug('Server running in singleplayer mode (fd/handle: %i)', singleplayer_fd)
            if sys.platform == 'win32':
                singleplayer_fd = msvcrt.open_osfhandle(singleplayer_fd, os.O_RDONLY)
            self.singleplayer_pipe = os.fdopen(singleplayer_fd, 'rb')
            self.loop.create_task(self.receive_singleplayer_commands(self.singleplayer_pipe))

        logging.info('Server started')
        self.running = True
        while self.running:
            await asyncio.sleep(0.01)

    async def shutdown(self) -> None:
        logging.info('Shutting down...')
        if self.singleplayer_pipe is not None:
            self.singleplayer_pipe.close()


def main():
    threading.current_thread().name = 'ServerThread'
    init_logger()
    AsyncServer().start()


if __name__ == '__main__':
    main()
