import asyncio
import binascii
import logging
import time
from asyncio import StreamReader, StreamWriter
from asyncio.events import AbstractEventLoop
from asyncio.tasks import shield
from typing import TYPE_CHECKING, Optional, TypeVar
from uuid import UUID

from and_beyond.common import (KEY_LENGTH, MOVE_SPEED_CAP_SQ, PROTOCOL_VERSION,
                               VERSION_DISPLAY_NAME, VIEW_DISTANCE_BOX,
                               get_version_name)
from and_beyond.middleware import (BufferedWriterMiddleware,
                                   EncryptedReaderMiddleware,
                                   EncryptedWriterMiddleware, ReaderMiddleware,
                                   WriterMiddleware, create_writer_middlewares)
from and_beyond.packet import (AddVelocityPacket, BasicAuthPacket, ChatPacket,
                               ChunkPacket, ChunkUpdatePacket,
                               ClientRequestPacket, DisconnectPacket, Packet,
                               PingPacket, PlayerInfoPacket,
                               PlayerPositionPacket, ServerInfoPacket,
                               UnloadChunkPacket, read_packet,
                               read_packet_timeout, write_packet)
from and_beyond.server.commands import COMMANDS
from and_beyond.server.player import Player
from and_beyond.utils import spiral_loop_async, spiral_loop_gen
from and_beyond.world import BlockTypes, WorldChunk
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.serialization.base import \
    load_der_public_key

if TYPE_CHECKING:
    from and_beyond.server.main import AsyncServer

_T_Packet = TypeVar('_T_Packet', bound=Packet)


class Client:
    server: 'AsyncServer'
    _reader: StreamReader
    _writer: StreamWriter
    reader: ReaderMiddleware
    writer: WriterMiddleware
    aloop: AbstractEventLoop
    packet_queue: asyncio.Queue[Packet]
    ready: bool
    disconnecting: bool

    uuid: Optional[UUID]
    ping_task: Optional[asyncio.Task]
    packet_task: Optional[asyncio.Task]
    load_chunks_task: Optional[asyncio.Task]
    loaded_chunks: dict[tuple[int, int], WorldChunk]

    player: Player
    nickname: str

    def __init__(self, server: 'AsyncServer', reader: StreamReader, writer: StreamWriter) -> None:
        self.server = server
        self._reader = reader
        self._writer = writer
        self.reader = reader
        self.writer = BufferedWriterMiddleware(writer)
        self.aloop = server.loop
        self.uuid = None
        self.ping_task = None
        self.packet_task = None
        self.load_chunks_task = None
        self.loaded_chunks = {}
        self.player = None # type: ignore (A single ignore is easier than convincing the type checker that this is almost never null)

    async def start(self) -> None:
        self.ready = False
        self.disconnecting = False
        if not await self.handshake():
            return
        assert self.uuid is not None
        logging.info('Player logged in with UUID %s', self.uuid)
        self.packet_queue = asyncio.Queue()
        self.ping_task = self.aloop.create_task(self.periodic_ping())
        self.packet_task = self.aloop.create_task(self.packet_tick())
        self.player = Player(self, self.nickname)
        await self.player.ainit()
        for client in self.server.clients:
            if client is not self and client.ready:
                assert client.uuid is not None
                packet = PlayerInfoPacket(client.uuid, client.nickname)
                await write_packet(packet, self.writer)
        packet = PlayerInfoPacket(self.uuid, self.nickname)
        await self.server.send_to_all(packet, exclude_player=self)
        await self.load_chunks_around_player(9)
        self.load_chunks_task = self.aloop.create_task(self.load_chunks_around_player())
        self.ready = True
        self.server.skip_gc = False
        logging.info('%s joined the game', self.player)
        if self.uuid.int != 0 or self.server.multiplayer: # Don't show in singleplayer
            await self.server.send_chat(f'{self.player} joined the game')

    async def handshake(self) -> bool:
        async def read_and_verify(should_be: type[_T_Packet]) -> Optional[_T_Packet]:
            try:
                packet = await read_packet_timeout(self.reader, 7)
            except TimeoutError:
                await self.disconnect('Client handshake timeout')
                return None
            if not isinstance(packet, should_be):
                await self.disconnect(f'Client packet of type {packet.type!s} should be of type {should_be.type!s}')
                return None
            return packet
        if (packet := await read_and_verify(ClientRequestPacket)) is None:
            return False
        if packet.protocol_version != PROTOCOL_VERSION:
            await self.disconnect(f'This server is on version {VERSION_DISPLAY_NAME} '
                                  f'(requires minimum {get_version_name(PROTOCOL_VERSION)} to join), '
                                  f'but you connected with {get_version_name(packet.protocol_version)}')
            return False
        is_localhost = self._writer.get_extra_info('peername')[0] in ('localhost', '127.0.0.1', '::1')
        auth_client = self.server.auth_client
        offline = auth_client is None
        if not offline:
            assert auth_client is not None
            if not self.server.multiplayer and is_localhost and len(self.server.clients) == 1:
                logging.debug('Singleplayer server running in offline mode')
                offline = True
            else:
                try:
                    await auth_client.ping()
                except Exception:
                    logging.warn('Failed to ping the auth server, will use offline mode for this connection.', exc_info=True)
                    offline = True
        server_key = ec.generate_private_key(ec.SECP384R1())
        packet = ServerInfoPacket(offline, server_key.public_key().public_bytes(
            Encoding.DER,
            PublicFormat.SubjectPublicKeyInfo,
        ))
        await write_packet(packet, self.writer)
        if (packet := await read_and_verify(BasicAuthPacket)) is None:
            return False
        client_token = packet.token
        if offline:
            if is_localhost:
                logging.debug('localhost connection not encrypted')
            else:
                if not await self.encrypt_connection(server_key, client_token):
                    return False
            if (packet := await read_and_verify(PlayerInfoPacket)) is None:
                return False
            self.uuid = packet.uuid
            self.nickname = packet.name
        else:
            assert auth_client is not None
            client_token = binascii.b2a_hex(client_token).decode('ascii')
            try:
                session = await auth_client.sessions.retrieve(client_token)
            except Exception as e:
                logging.error('Failed to retrieve client session', exc_info=True)
                await self.disconnect(f'Failed to retrieve client session: {e}')
                return False
            if is_localhost:
                logging.debug('localhost connection not encrypted')
            else:
                if not await self.encrypt_connection(server_key, session.public_key):
                    return False
            self.uuid = session.user.uuid
            self.nickname = session.user.username
            packet = PlayerInfoPacket(self.uuid, self.nickname)
            await write_packet(packet, self.writer)
        return True

    async def encrypt_connection(self,
            server_key: ec.EllipticCurvePrivateKey,
            key_bytes: bytes,
        ) -> bool:
        assert self._reader is not None
        assert self._writer is not None
        logging.debug('Encrypting connection...')
        client_public_key = load_der_public_key(key_bytes)
        if not isinstance(client_public_key, ec.EllipticCurvePublicKey):
            await self.disconnect('Client key not EllipticCurvePublicKey')
            return False
        shared_key = server_key.exchange(
            ec.ECDH(),
            client_public_key,
        )
        derived_key = HKDF(hashes.SHA256(), KEY_LENGTH, None, None).derive(shared_key)
        self.writer = create_writer_middlewares(
            [BufferedWriterMiddleware, EncryptedWriterMiddleware(derived_key)],
            self._writer
        )
        self.reader = EncryptedReaderMiddleware(derived_key)(self._reader)
        return True

    async def load_chunk(self, x: int, y: int) -> None:
        chunk = self.server.world.get_generated_chunk(x, y, self.server.world_generator)
        self.loaded_chunks[(x, y)] = chunk
        packet = ChunkPacket(chunk)
        await write_packet(packet, self.writer)

    async def unload_chunk(self, x: int, y: int) -> None:
        self.loaded_chunks.pop((x, y), None)
        packet = UnloadChunkPacket(x, y)
        await write_packet(packet, self.writer)

    async def load_chunks_around_player(self, diameter: int = VIEW_DISTANCE_BOX) -> None:
        async def load_chunk_rel(x, y):
            await asyncio.sleep(0) # Why do I have to do this? I *do* have to for some reason
            x += cx
            y += cy
            loaded.add((x, y))
            if (x, y) in self.loaded_chunks:
                return
            await self.load_chunk(x, y)
        loaded: set[tuple[int, int]] = set()
        cx = int(self.player.x) >> 4
        cy = int(self.player.y) >> 4
        await spiral_loop_async(
            diameter,
            diameter,
            load_chunk_rel
        ) # bpo-29930
        # await asyncio.gather(*
        #     spiral_loop_gen(
        #         diameter,
        #         diameter,
        #         (
        #             lambda x, y:
        #                 self.aloop.create_task(load_chunk_rel(x, y))
        #         )
        #     )
        # )
        to_unload = set(self.loaded_chunks).difference(loaded)
        tasks = []
        for (cx, cy) in to_unload:
            tasks.append(self.aloop.create_task(self.unload_chunk(cx, cy)))
        if tasks:
            await asyncio.gather(*tasks)

    async def periodic_ping(self) -> None:
        while self.server.running:
            await asyncio.sleep(1)
            try:
                await write_packet(PingPacket(), self.writer)
            except ConnectionError:
                logging.debug('Client failed ping, removing player from list of connected players')
                await self.disconnect(f'{self.player} left the game', False)
                return

    async def packet_tick(self) -> None:
        while self.server.running:
            try:
                packet = await read_packet(self.reader)
            except (asyncio.IncompleteReadError, ConnectionError):
                await self.disconnect(f'{self.player} left the game', False)
                return
            await self.packet_queue.put(packet)

    async def tick(self) -> None:
        if not self.ready:
            return
        assert self.uuid is not None
        while True:
            try:
                packet = self.packet_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                if isinstance(packet, ChunkUpdatePacket):
                    chunk_pos = (packet.cx, packet.cy)
                    if chunk_pos in self.loaded_chunks:
                        abs_x = (packet.cx << 4) + packet.bx
                        abs_y = (packet.cy << 4) + packet.by
                        chunk = self.loaded_chunks[chunk_pos]
                        if self.player.can_reach(abs_x, abs_y, packet.block != BlockTypes.AIR):
                            await self.server.set_tile_type_global(chunk, packet.bx, packet.by, packet.block, self)
                        else:
                            # logging.warn("Player %s can't reach block %i, %i, yet they tried to update it.", self, abs_x, abs_y)
                            packet.block = chunk.get_tile_type(packet.bx, packet.by)
                            await write_packet(packet, self.writer)
                elif isinstance(packet, PlayerPositionPacket):
                    logging.warn('Player %s used illegal packet: PLAYER_POSITION (this packet is deprecated and a security hole)', self)
                    await self.disconnect('Used illegal packet: PLAYER_POSITION (this packet is deprecated and a security hole)')
                    return
                    prev_x = self.player.x
                    prev_y = self.player.y
                    rel_x = packet.x - prev_x
                    rel_y = packet.y - prev_y
                    dist = rel_x * rel_x + rel_y * rel_y
                    if dist > MOVE_SPEED_CAP_SQ:
                        packet.x = prev_x
                        packet.y = prev_y
                        logging.warn('Player %s moved too quickly! %f, %f', self, rel_x, rel_y)
                        await write_packet(packet, self.writer)
                    else:
                        self.player.x = packet.x
                        self.player.y = packet.y
                elif isinstance(packet, AddVelocityPacket):
                    if packet.y > 0 and self.player.physics.air_time >= 2:
                        # logging.warn('Player %s tried to mid-air jump. This is not allowed.')
                        packet.y = 0
                    prev_x = self.player.physics.x_velocity
                    prev_y = self.player.physics.y_velocity
                    new_x = prev_x + packet.x
                    new_y = prev_y + packet.y
                    vel = new_x * new_x + new_y * new_y
                    if vel > MOVE_SPEED_CAP_SQ:
                        packet.x = prev_x
                        packet.y = prev_y
                        logging.warn('Player %s moved too quickly! %f, %f', self, new_x, new_y)
                        packet = PlayerPositionPacket(self.uuid, self.player.x, self.player.y)
                        self.player.physics.x_velocity = 0
                        self.player.physics.y_velocity = 0
                        await write_packet(packet, self.writer)
                    else:
                        self.player.physics.x_velocity = new_x
                        self.player.physics.y_velocity = new_y
                elif isinstance(packet, ChatPacket):
                    if packet.message[0] == '/':
                        name, *rest = packet.message[1:].split(' ', 1)
                        if name in COMMANDS:
                            command = COMMANDS[name]
                            await command(self, rest[0] if rest else '')
                        else:
                            logging.info('<%s> No command named "%s"', self.player, name)
                            await self.send_chat(f'No command named "{name}"')
                    else:
                        packet.message = f'<{self.player}> {packet.message}'
                        logging.info('CHAT: %s', packet.message)
                        await asyncio.gather(*(
                            write_packet(packet, client.writer)
                            for client in self.server.clients
                        ))
                else:
                    logging.warn('Client %s sent illegal packet: %s', self, packet.type.name)
                    await self.disconnect(f'Packet type not legal for C->S: {packet.type.name}')
                    return
        physics = self.player.physics
        old_cx = int(self.player.x) >> 4
        old_cy = int(self.player.y) >> 4
        physics.tick(0.05)
        if physics.dirty:
            await self.player.send_position()
            cx = int(self.player.x) >> 4
            cy = int(self.player.y) >> 4
            if cx != old_cx or cy != old_cy:
                await self.load_chunks_around_player()

    async def disconnect(self, reason: str = '', kick: bool = True) -> None:
        # Shield is necessary, as this shutdown method *must* be called.
        # It used to cancel in the middle of this method, preventing player
        # data from being saved.
        await shield(self._disconnect(reason, kick))

    async def _disconnect(self, reason: str, kick: bool) -> None:
        if self.disconnecting:
            logging.debug('Already disconnecting %s', self)
            return
        self.disconnecting = True
        logging.debug('Disconnecting Client %s for reason "%s"', self, reason)
        try:
            self.server.clients.remove(self)
        except ValueError:
            pass
        if self.packet_task is not None:
            self.packet_task.cancel()
        if self.ping_task is not None:
            self.ping_task.cancel()
        if self.load_chunks_task is not None:
            self.load_chunks_task.cancel()
        if kick:
            packet = DisconnectPacket(reason)
            try:
                await write_packet(packet, self.writer)
            except ConnectionError:
                logging.debug('Client was already disconnected')
        self._writer.close()
        if self.player is not None:
            start = time.perf_counter()
            await self.player.save()
            end = time.perf_counter()
            logging.debug('Player %s data saved in %f seconds', self, end - start)
        await self._writer.wait_closed()
        logging.info('Client %s disconnected for reason: %s', self, reason)
        if self.player is not None:
            logging.info('%s left the game', self.player)
            await self.server.send_chat(f'{self.player} left the game')

    def __repr__(self) -> str:
        peername = self._writer.get_extra_info('peername')
        return f'<Client host={peername[0]}:{peername[1]} player={self.player!r} server={self.server!r}>'

    async def send_chat(self, message: str, at: float = None) -> None:
        if at is None:
            at = time.time()
        packet = ChatPacket(message, at)
        await write_packet(packet, self.writer)
