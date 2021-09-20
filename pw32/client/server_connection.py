import asyncio
from asyncio.streams import StreamReader, StreamWriter
import logging
from pw32.common import PORT
import socket
import threading
import uuid

from pw32.packet import AuthenticatePacket, write_packet


class ServerConnection:
    reader: StreamReader
    writer: StreamWriter
    thread: threading.Thread
    aio_loop: asyncio.AbstractEventLoop

    running: bool

    def __init__(self) -> None:
        self.running = False

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
        self.reader, self.writer = await asyncio.open_connection(server, PORT)
        logging.debug('Authenticating with server...')
        auth = AuthenticatePacket(uuid.UUID(int=23984)) # Why not? This will be more rigorous in the future
        await write_packet(auth, self.writer)
        logging.info('Connected to server')
    
    async def shutdown(self) -> None:
        pass
