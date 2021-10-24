import asyncio
import logging
import math
import threading
import time
from asyncio.exceptions import CancelledError, TimeoutError
from asyncio.streams import StreamReader, StreamWriter
from typing import Optional, TypeVar
from uuid import UUID

import janus
import pygame
import pygame.event
from and_beyond.client import globals
from and_beyond.client.chat import ClientChatMessage
from and_beyond.client.consts import (SERVER_CONNECT_EVENT,
                                      SERVER_DISCONNECT_EVENT)
from and_beyond.client.globals import GameStatus
from and_beyond.client.player import ClientPlayer
from and_beyond.client.world import ClientChunk
from and_beyond.common import KEY_LENGTH, PORT, PROTOCOL_VERSION
from and_beyond.http_auth import AuthClient
from and_beyond.http_errors import Unauthorized
from and_beyond.middleware import (BufferedWriterMiddleware,
                                   EncryptedReaderMiddleware,
                                   EncryptedWriterMiddleware, ReaderMiddleware,
                                   WriterMiddleware, create_writer_middlewares)
from and_beyond.packet import (BasicAuthPacket, ChatPacket, ChunkPacket,
                               ChunkUpdatePacket, ClientRequestPacket,
                               DisconnectPacket, Packet, PingPacket,
                               PlayerInfoPacket, PlayerPositionPacket,
                               RemovePlayerPacket, ServerInfoPacket,
                               UnloadChunkPacket, read_packet,
                               read_packet_timeout, write_packet)
from and_beyond.utils import DEBUG
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.serialization.base import \
    load_der_public_key

_T_Packet = TypeVar('_T_Packet', bound=Packet)


class ServerConnection:
    _reader: Optional[StreamReader]
    _writer: Optional[StreamWriter]
    reader: ReaderMiddleware
    writer: WriterMiddleware
    thread: threading.Thread
    aio_loop: asyncio.AbstractEventLoop

    running: bool
    outgoing_queue: Optional[janus.Queue[Packet]]
    send_packets_task: Optional[asyncio.Task]
    uuid: UUID

    disconnect_reason: Optional[str]
    _should_post_event: bool

    def __init__(self) -> None:
        self._reader = None
        self._writer = None
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
        globals.connecting_status = 'Handshaking'
        if not await self.handshake():
            return
        logging.info('Connected to server')
        globals.connecting_status = 'Connected'
        globals.game_status = GameStatus.IN_GAME
        pygame.event.post(pygame.event.Event(SERVER_CONNECT_EVENT))
        globals.all_players[self.uuid] = globals.player
        globals.local_world.load()
        self.send_packets_task = self.aio_loop.create_task(self.send_outgoing_packets())
        time_since_ping = 0
        it_start = time.perf_counter()
        while self.running:
            it_end = time.perf_counter()
            time_since_ping += it_end - it_start
            if time_since_ping > 10: # Server hasn't responded for 10 seconds, it's probably down
                if DEBUG:
                    logging.warn("Server hasn't sent a ping in 10 seconds. Is it down?")
                else:
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
                assert packet.chunk is not None
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
            elif isinstance(packet, PlayerPositionPacket):
                # globals.player.last_x = globals.player.render_x = globals.player.x
                # globals.player.last_y = globals.player.render_y = globals.player.y
                # globals.player.x = packet.x
                # globals.player.y = packet.y
                player = globals.all_players.get(packet.player)
                if player is not None:
                    player.x = packet.x
                    player.y = packet.y
            elif isinstance(packet, PlayerInfoPacket):
                new_player = ClientPlayer(packet.name)
                globals.all_players[packet.uuid] = new_player
            elif isinstance(packet, RemovePlayerPacket):
                globals.all_players.pop(packet.player, None)
            elif isinstance(packet, DisconnectPacket):
                logging.info('Disconnected from server: %s', packet.reason)
                self.disconnect_reason = packet.reason
                self.running = False
            elif isinstance(packet, PingPacket):
                time_since_ping = 0
            elif isinstance(packet, ChatPacket):
                logging.info('CHAT: %s', packet.message)
                globals.chat_client.add_message(ClientChatMessage(packet.message, packet.time))

    async def handshake(self) -> bool:
        assert self._reader is not None
        assert self._writer is not None
        async def read_and_verify(should_be: type[_T_Packet]) -> Optional[_T_Packet]:
            try:
                packet = await read_packet_timeout(self.reader, 7)
            except TimeoutError:
                self.disconnect_reason = 'Server handshake timeout'
                return None
            if isinstance(packet, DisconnectPacket):
                self.disconnect_reason = packet.reason
                return None
            if not isinstance(packet, should_be):
                self.disconnect_reason = f'Server packet of type {packet.type!s} should be of type {should_be.type!s}'
                return None
            return packet
        packet = ClientRequestPacket(PROTOCOL_VERSION) # Explicit > implicit
        await write_packet(packet, self.writer)
        client_key = ec.generate_private_key(ec.SECP384R1())
        key_bytes = client_key.public_key().public_bytes(
            Encoding.DER,
            PublicFormat.SubjectPublicKeyInfo,
        )
        if (packet := await read_and_verify(ServerInfoPacket)) is None:
            return False
        server_public_key = load_der_public_key(packet.public_key)
        is_localhost = self._writer.get_extra_info('peername')[0] in ('localhost', '127.0.0.1', '::1')
        if not isinstance(server_public_key, ec.EllipticCurvePublicKey):
            self.disconnect_reason = 'Server key not EllipticCurvePublicKey'
            return False
        if packet.offline:
            if globals.singleplayer_pipe_out is None:
                use_uuid = globals.config.uuid
                if use_uuid is None:
                    self.disconnect_reason = 'You must have logged in at some point to play multiplayer'
                    return False
            else:
                use_uuid = UUID(int=0) # Singleplayer
            packet = BasicAuthPacket(key_bytes)
            await write_packet(packet, self.writer)
            if is_localhost:
                logging.debug('localhost connection not encrypted')
            else:
                self.encrypt_connection(client_key, server_public_key)
            packet = PlayerInfoPacket(
                use_uuid,
                globals.config.config['username'],
            )
            await write_packet(packet, self.writer)
            self.uuid = use_uuid
        else:
            async with AuthClient(globals.auth_server, globals.allow_insecure_auth) as auth:
                if (error := await auth.verify_connection()) is not None:
                    self.disconnect_reason = error
                    return False
                token = globals.config.config['auth_token']
                if token is None:
                    self.disconnect_reason = 'You must be logged in to play multiplayer in online mode'
                    return False
                try:
                    profile = await auth.auth.get_profile(token)
                except Exception as e:
                    logging.warn('Failed to fetch profile', exc_info=True)
                    if isinstance(e, Unauthorized):
                        self.disconnect_reason = 'You must be logged in to play multiplayer in online mode'
                    else:
                        self.disconnect_reason = f'Failed to fetch profile: {e}'
                    return False
                sess_token, session = await auth.sessions.create(profile, key_bytes)
                packet = BasicAuthPacket(bytes.fromhex(sess_token))
            await write_packet(packet, self.writer)
            if is_localhost:
                logging.debug('localhost connection not encrypted')
            else:
                self.encrypt_connection(client_key, server_public_key)
            if (packet := await read_and_verify(PlayerInfoPacket)) is None:
                return False
            self.uuid = packet.uuid
        return True

    def encrypt_connection(self,
            client_key: ec.EllipticCurvePrivateKey,
            server_public_key: ec.EllipticCurvePublicKey
        ) -> None:
        assert self._reader is not None
        assert self._writer is not None
        logging.debug('Encrypting connection...')
        shared_key = client_key.exchange(
            ec.ECDH(),
            server_public_key,
        )
        derived_key = HKDF(hashes.SHA256(), KEY_LENGTH, None, None).derive(shared_key)
        self.writer = create_writer_middlewares(
            [BufferedWriterMiddleware, EncryptedWriterMiddleware(derived_key)],
            self._writer
        )
        self.reader = EncryptedReaderMiddleware(derived_key)(self._reader)

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
        if self._writer is not None:
            self._writer.close()
        if self.outgoing_queue is not None:
            self.outgoing_queue.close()
        globals.local_world.unload()
        globals.player.x = globals.player.render_x = math.inf
        globals.player.y = globals.player.render_y = math.inf
        if self._writer is not None:
            try:
                await self._writer.wait_closed()
            except ConnectionError:
                pass
        self._writer = None
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
