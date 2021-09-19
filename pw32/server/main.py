import asyncio
import logging
import os
from pw32.pipe_commands import PipeCommands
import sys
import threading
from typing import BinaryIO

if sys.platform == 'win32':
    import msvcrt

import colorama
from pw32.utils import init_logger


async def _main():
    loop = asyncio.get_running_loop()

    try:
        singleplayer_fd = int(sys.argv[sys.argv.index('--singleplayer') + 1])
    except (ValueError, IndexError):
        logging.debug('Server running in multiplayer mode')
        singleplayer_pipe: BinaryIO = None # type: ignore # Pyright hates me for this, I know
        singleplayer = False
    else:
        logging.debug('Server running in singleplayer mode (fd/handle: %i)', singleplayer_fd)
        if sys.platform == 'win32':
            singleplayer_fd = msvcrt.open_osfhandle(singleplayer_fd, os.O_RDONLY)
        singleplayer_pipe = os.fdopen(singleplayer_fd, 'rb')
        singleplayer = True
    
    running = True
    while running:
        try:
            if singleplayer:
                command = await loop.run_in_executor(None, singleplayer_pipe.read, 2)
                command = PipeCommands.from_bytes(command, 'little')
                if command == PipeCommands.SHUTDOWN:
                    running = False
        except KeyboardInterrupt:
            running = False
    
    logging.info('Shutting down...')
    if singleplayer:
        singleplayer_pipe.close()


def main():
    threading.current_thread().name = 'ServerThread'
    init_logger()
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    with colorama.colorama_text():
        logging.info('Starting server...')
        asyncio.run(_main())
        logging.info('Server closed')


if __name__ == '__main__':
    main()
