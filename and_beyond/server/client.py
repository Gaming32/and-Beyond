import asyncio
import logging
import math
import time
import uuid
from asyncio import IncompleteReadError, StreamReader, StreamWriter
from asyncio.events import AbstractEventLoop
from asyncio.tasks import Task, shield
from collections import deque
from typing import TYPE_CHECKING, Optional, TypeVar
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.serialization.base import load_der_public_key

from and_beyond.abstract_player import InventoryItem
from and_beyond.common import (KEY_LENGTH, MOVE_SPEED_CAP_SQ, NAMESPACE_AND_BEYOND, PROTOCOL_VERSION, USERNAME_REGEX,
                               VERSION_DISPLAY_NAME, VIEW_DISTANCE_BOX, get_version_name)
from and_beyond.middleware import (BufferedWriterMiddleware, EncryptedReaderMiddleware, EncryptedWriterMiddleware,
                                   ReaderMiddleware, WriterMiddleware, create_writer_middlewares)
from and_beyond.packet import (BasicAuthPacket, ChatPacket, ChunkPacket, ChunkUpdatePacket, ClientRequestPacket,
                               DisconnectPacket, InventoryPacket, InventorySelectPacket, InventoryUpdatePacket, Packet,
                               PingPacket, PlayerInfoPacket, PlayerPositionPacket, RemovePlayerPacket,
                               ServerInfoPacket, SimplePlayerPositionPacket, UnloadChunkPacket, read_packet,
                               read_packet_timeout, write_packet)
from and_beyond.server.commands import ClientCommandSender
from and_beyond.server.player import Player
from and_beyond.text import EMPTY_TEXT, MaybeText, Text, plain_text, translatable_text
from and_beyond.utils import mean, spiral_loop_gen
from and_beyond.world import WorldChunk

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
    ping_task: Optional[asyncio.Task[None]]
    packet_task: Optional[asyncio.Task[None]]
    send_players_task: Optional[asyncio.Task[None]]
    load_chunks_task: Optional[asyncio.Task[None]]
    loaded_chunks: dict[tuple[int, int], WorldChunk]

    player: Optional[Player]
    nickname: Optional[str]
    command_sender: ClientCommandSender
    new_x: float
    new_y: float
    grounded_time: float
    air_time: float
    last_y_velocities: deque[float]

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
        self.send_players_task = None
        self.load_chunks_task = None
        self.loaded_chunks = {}
        self.player = None
        self.nickname = None
        self.command_sender = ClientCommandSender(self)
        self.grounded_time = 0
        self.air_time = 0
        self.last_y_velocities = deque((), 4)

    async def start(self) -> None:
        self.ready = False
        self.disconnecting = False
        if not await self.handshake():
            return
        assert self.uuid is not None
        assert self.nickname is not None
        logging.info('Player logged in with UUID %s', self.uuid)
        # for client in self.server.clients:
        #     if client is self:
        #         continue
        #     if client.uuid == self.uuid:
        #         await client.disconnect('You logged in from elsewhere.')
        #     elif client.nickname == self.nickname:
        #         await self.disconnect('That name is taken.')
        #         return
        if (client := self.server.clients_by_uuid.get(self.uuid)) is not None:
            await client.disconnect(translatable_text('server.second_login'))
        elif self.nickname in self.server.clients_by_name:
            await self.disconnect(translatable_text('connect.server.name_taken'))
            return
        self.player = Player(self, self.nickname)
        await self.player.ainit()
        if self.server.multiplayer and self.player.banned is not None:
            await self.disconnect(self.player.banned)
            return
        self.new_x = self.player.x
        self.new_y = self.player.y
        for client in self.server.clients:
            if client is not self and client.ready:
                assert client.uuid is not None
                assert client.nickname is not None
                packet = PlayerInfoPacket(client.uuid, client.nickname)
                await self.send_or_remove(packet)
        packet = PlayerInfoPacket(self.uuid, self.nickname)
        await self.server.send_to_all(packet, exclude_player=self)
        await self.load_chunks_around_player(9)
        await self.send_or_remove(InventoryPacket(self.player.inventory))
        await self.set_position_safe()
        self.send_players_task = self.aloop.create_task(self.send_player_positions())
        self.load_chunks_around_player_task()
        self.packet_queue = asyncio.Queue()
        self.ping_task = self.aloop.create_task(self.periodic_ping())
        self.packet_task = self.aloop.create_task(self.packet_tick())
        self.server.clients_by_uuid[self.uuid] = self
        self.server.clients_by_name[self.nickname] = self
        self.ready = True
        # self.server.skip_gc = False
        message = translatable_text('server.joined_game', str(self.player))
        logging.info(message)
        if self.uuid.int != 0 or self.server.multiplayer: # Don't show in singleplayer
            await self.server.send_chat(message)

    async def handshake(self) -> bool:
        async def read_and_verify(should_be: type[_T_Packet]) -> Optional[_T_Packet]:
            try:
                packet = await read_packet_timeout(self.reader, 7)
            except TimeoutError:
                await self.disconnect(translatable_text('connect.server.handshake_timeout'))
                return None
            except IncompleteReadError:
                await self.disconnect(translatable_text('connect.server.client_disconnected'), kick=False)
                return None
            if not isinstance(packet, should_be):
                await self.disconnect(translatable_text(
                    'connect.server.incorrect_packet',
                    was_type=str(packet.type),
                    should_be_type=str(should_be.type)
                ))
                return None
            return packet
        if (packet := await read_and_verify(ClientRequestPacket)) is None:
            return False
        if packet.protocol_version != PROTOCOL_VERSION:
            await self.disconnect(translatable_text(
                'connect.server.unsupported_version',
                version_display_name=VERSION_DISPLAY_NAME,
                min_version=get_version_name(PROTOCOL_VERSION),
                actual_version=get_version_name(packet.protocol_version)
            ))
            return False
        is_localhost = self._writer.get_extra_info('peername')[0] in ('localhost', '127.0.0.1', '::1')
        auth_client = self.server.auth_client
        offline = auth_client is None
        enforce_hybrid = False
        is_singleplayer = False
        if not offline:
            assert auth_client is not None
            if is_singleplayer := (not self.server.multiplayer and is_localhost and len(self.server.clients) == 1):
                logging.debug('Singleplayer server running in offline mode')
                offline = True
            else:
                try:
                    await auth_client.ping()
                except Exception:
                    logging.warn(
                        'Failed to ping the auth server, will use hybrid mode for this connection.', exc_info=True
                    )
                    offline = True
                    enforce_hybrid = True
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
            assert self.server.world is not None
            if (new_uuid := self.server.world._players_by_name.get(self.nickname)) is not None:
                if packet.uuid.int != 0 and new_uuid != packet.uuid:
                    await self.disconnect(translatable_text('connect.server.uuid_validate_failure'))
                    return False
                self.uuid = new_uuid
            elif packet.uuid.int == 0:
                if not is_singleplayer:
                    self.uuid = uuid.uuid3(NAMESPACE_AND_BEYOND, self.nickname)
            else:
                self.uuid = packet.uuid
            if enforce_hybrid:
                if new_uuid is None:
                    await self.disconnect(translatable_text('connect.server.hybrid_login_failure'))
                    return False
            if self.nickname in self.server.clients_by_name or self.uuid in self.server.clients_by_uuid:
                await self.disconnect(translatable_text('connect.server.name_taken'))
                return False
            # Prevent people with illegal nicknames from joining
            if not USERNAME_REGEX.fullmatch(packet.name):
                await self.disconnect(translatable_text('connect.server.invalid_username'))
                return False
        else:
            assert auth_client is not None
            client_token = client_token.hex()
            try:
                session = await auth_client.sessions.retrieve(client_token)
            except Exception as e:
                logging.error('Failed to retrieve client session', exc_info=True)
                await self.disconnect(translatable_text('connect.server.session_retrieve_failure', str(e)))
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
            await self.disconnect(translatable_text('connect.server.wrong_key_type', 'EllipticCurvePublicKey'))
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
        assert self.server.world is not None
        if (x, y) in self.server.all_loaded_chunks:
            chunk = self.server.all_loaded_chunks[(x, y)]
        else:
            chunk = self.server.world.get_generated_chunk(x, y, self.server.world_generator)
        self.loaded_chunks[(x, y)] = chunk
        self.server.all_loaded_chunks[(x, y)] = chunk
        chunk.mark_loaded()
        await self.send_or_remove(ChunkPacket(chunk))

    async def unload_chunk(self, x: int, y: int, server_only: bool = False) -> None:
        c = self.loaded_chunks.pop((x, y), None)
        if c is not None:
            if c.mark_unloaded() <= 0:
                self.server.all_loaded_chunks.pop((x, y), None)
                if c.section is not None:
                    c.section.cached_chunks.pop((c.x, c.y), None)
                    if c.section.mark_unloaded() <= 0:
                        logging.debug('Closing section (%i, %i) because its reference count reached 0', x >> 4, y >> 4)
                        start = time.perf_counter()
                        c.section.close()
                        end = time.perf_counter()
                        logging.debug('Closed section (%i, %i) in %f seconds', x >> 4, y >> 4, end - start)
        if not server_only:
            await self.send_or_remove(UnloadChunkPacket(x, y))

    async def load_chunks_around_player(self, diameter: int = VIEW_DISTANCE_BOX) -> None:
        assert self.player is not None
        async def load_chunk_rel(x: int, y: int) -> None:
            await asyncio.sleep(0)
            x += cx
            y += cy
            loaded.add((x, y))
            if (x, y) in self.loaded_chunks:
                return
            await self.load_chunk(x, y)
        loaded: set[tuple[int, int]] = set()
        cx = int(self.player.x) >> 4
        cy = int(self.player.y) >> 4
        await asyncio.gather(*
            spiral_loop_gen(
                diameter,
                diameter,
                (
                    lambda x, y:
                        self.aloop.create_task(load_chunk_rel(x, y))
                )
            )
        )
        to_unload = set(self.loaded_chunks).difference(loaded)
        tasks = []
        for (cx, cy) in to_unload:
            tasks.append(self.aloop.create_task(self.unload_chunk(cx, cy)))
        if tasks:
            await asyncio.gather(*tasks)

    async def send_player_positions(self) -> None:
        assert self.uuid is not None
        assert self.player is not None
        for client in self.server.clients:
            if client is not self and client.ready:
                assert client.uuid is not None
                assert client.player is not None
                cx = int(client.player.x) >> 4
                cy = int(client.player.y) >> 4
                if (cx, cy) in self.loaded_chunks:
                    await self.send_or_remove(PlayerPositionPacket(client.uuid, client.player.x, client.player.y))
                cx = int(self.player.x) >> 4
                cy = int(self.player.y) >> 4
                if (cx, cy) in client.loaded_chunks:
                    await self.send_or_remove(PlayerPositionPacket(self.uuid, self.player.x, self.player.y))

    async def periodic_ping(self) -> None:
        while self.server.running:
            await asyncio.sleep(1)
            try:
                await write_packet(PingPacket(), self.writer)
            except ConnectionError:
                logging.debug('Client failed ping, removing player from list of connected players')
                await self.disconnect(translatable_text('server.left_game', str(self.player)), False)
                return

    async def packet_tick(self) -> None:
        while not self.ready:
            await asyncio.sleep(0)
        while self.server.running and self.ready:
            try:
                packet = await read_packet(self.reader)
            except (asyncio.IncompleteReadError, ConnectionError):
                await self.disconnect(translatable_text('server.left_game', str(self.player)), False)
                return
            if isinstance(packet, SimplePlayerPositionPacket):
                if packet.x != math.inf and packet.y != math.inf:
                    try:
                        int(packet.x ** 2)
                        int(packet.y ** 2)
                    except (ValueError, OverflowError) as e:
                        await self.disconnect(plain_text(str(e)))
                        break
                    self.new_x = packet.x
                    self.new_y = packet.y
            else:
                await self.packet_queue.put(packet)

    async def tick(self) -> None:
        if not self.ready:
            return
        assert self.uuid is not None
        assert self.player is not None
        packets_remaining = 20 # Don't receive more than 20 packets in one tick
        while packets_remaining:
            packets_remaining -= 1
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
                        if self.player.can_reach(abs_x, abs_y, packet.block.bounding_box):
                            await self.server.set_tile_type_global(chunk, packet.bx, packet.by, packet.block, self)
                        else:
                            # logging.warn("Player %s can't reach block %i, %i, yet they tried to update it.", self, abs_x, abs_y)
                            packet.block = chunk.get_tile_type(packet.bx, packet.by)
                            packet.packed_lighting = chunk.get_packed_lighting(packet.bx, packet.by)
                            await self.send_or_remove(packet)
                elif isinstance(packet, ChatPacket):
                    message = packet.message
                    if not message.localized and message.value[0] == '/':
                        await self.server.run_command(message.value[1:], self.command_sender)
                    else:
                        await self.server.send_chat(f'<{self.player}> {message}', log=True)
                elif isinstance(packet, InventoryUpdatePacket):
                    if packet.item is None:
                        self.player.inventory.items[packet.slot] = None
                    else:
                        self.player.inventory.items[packet.slot] = InventoryItem(packet.item, packet.count)
                elif isinstance(packet, InventorySelectPacket):
                    self.player.inventory.selected = packet.slot
                else:
                    logging.warn('Client %s sent illegal packet: %s', self, packet.type.name)
                    await self.disconnect(translatable_text('server.illegal_packet', packet.type.name))
                    return
        distance_x = self.new_x - self.player.x
        distance_y = self.new_y - self.player.y
        distance_sq = distance_x ** 2 + distance_y ** 2
        if distance_x ** 2 + distance_y ** 2 > MOVE_SPEED_CAP_SQ:
            self.new_y = self.player.y
            self.new_x = self.player.x
            logging.warn('Player %s moved too quickly! %f, %f', self, distance_x, distance_y)
            await self.set_position_safe()
        else:
            old_cx = int(self.player.x) >> 4
            old_cy = int(self.player.y) >> 4
            distance = math.sqrt(distance_sq)
            collided = False
            if distance > 0.01:
                step_count = math.ceil(distance)
                if step_count > 0:
                    # Move in steps to detect collisions
                    step_x = distance_x / step_count
                    step_y = distance_y / step_count
                    assert self.server.world is not None
                    self.player.x += step_x
                    self.player.y += step_y
                    for step in range(step_count - 1):
                        self.player.x += step_x
                        if self.player.physics.offset_bb.expand(-0.2).collides_with_world(self.server.world):
                            collided = True
                            break
                        self.player.y += step_y
                        if self.player.physics.offset_bb.expand(-0.2).collides_with_world(self.server.world):
                            collided = True
                            break
            if collided:
                await self.set_position_safe()
            else:
                self.player.x = self.new_x
                self.player.y = self.new_y
            cx = int(self.player.x) >> 4
            cy = int(self.player.y) >> 4
            if cx != old_cx or cy != old_cy:
                self.load_chunks_around_player_task()
            if distance:
                packet = PlayerPositionPacket(self.uuid, self.player.x, self.player.y)
                await self.server.send_to_all(packet, (cx, cy), self)
        if self.player.physics.offset_bb.expand(1).collides_with_world(self.player.world):
            self.grounded_time += 0.05
            self.air_time = 0
        else:
            self.grounded_time = 0
            self.air_time += 0.05
        self.last_y_velocities.append(distance_y)
        if self.air_time > 5 and 4 > mean(self.last_y_velocities) > -0.25:
            await self.disconnect(translatable_text('server.fly_hacking'))

    async def set_position_safe(self, x: Optional[float] = None, y: Optional[float] = None, include_others: bool = False) -> None:
        assert self.player is not None
        if x is None:
            x = self.player.x
        else:
            self.player.x = x
        if y is None:
            y = self.player.y
        else:
            self.player.y = y
        packet = SimplePlayerPositionPacket(x, y)
        await self.send_or_remove(packet)
        if include_others:
            assert self.uuid is not None
            packet = PlayerPositionPacket(self.uuid, self.player.x, self.player.y)
            await self.server.send_to_all(packet, (int(x) >> 4, int(y) >> 4), self)

    def load_chunks_around_player_task(self) -> Task[None]:
        self.load_chunks_task = self.aloop.create_task(self.load_chunks_around_player())
        return self.load_chunks_task

    async def send_or_remove(self, packet: Packet) -> None:
        try:
            await write_packet(packet, self.writer)
        except ConnectionError:
            await self.disconnect(translatable_text('server.left_game', str(self.player)), kick=False)

    async def disconnect(self, reason: Text = EMPTY_TEXT, kick: bool = True) -> None:
        # Shield is necessary, as this shutdown method *must* be called.
        # It used to cancel in the middle of this method, preventing player
        # data from being saved.
        await shield(self._disconnect(reason, kick))

    async def _disconnect(self, reason: Text, kick: bool) -> None:
        if self.disconnecting:
            logging.debug('Already disconnecting %s', self)
            return
        self.ready = False
        self.disconnecting = True
        logging.debug('Disconnecting Client %s for reason "%s"', self, reason)
        try:
            self.server.clients.remove(self)
        except ValueError:
            pass
        if self.uuid is not None:
            self.server.clients_by_uuid.pop(self.uuid, None)
        if self.nickname is not None:
            self.server.clients_by_name.pop(self.nickname, None)
        if self.packet_task is not None:
            self.packet_task.cancel()
        if self.ping_task is not None:
            self.ping_task.cancel()
        if self.load_chunks_task is not None:
            self.load_chunks_task.cancel()
        if self.send_players_task is not None:
            self.send_players_task.cancel()
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
        for (cx, cy) in list(self.loaded_chunks.keys()):
            await self.unload_chunk(cx, cy, True)
        try:
            await self._writer.wait_closed()
        except ConnectionError:
            pass
        if self.uuid is not None:
            logging.debug('Sending removal packets to remaining players')
            packet = RemovePlayerPacket(self.uuid)
            for client in self.server.clients:
                if client.ready:
                    await write_packet(packet, client.writer)
        logging.info('Client %s disconnected for reason: %s', self, reason)
        if self.player is not None:
            message = translatable_text('server.left_game', str(self.player))
            logging.info(message)
            await self.server.send_chat(message)

    def __repr__(self) -> str:
        peername = self._writer.get_extra_info('peername')
        return f'<Client host={peername[0]}:{peername[1]} player={self.player!r} server={self.server!r}>'

    async def send_chat(self, message: MaybeText, at: Optional[float] = None) -> None:
        if at is None:
            at = time.time()
        await self.send_or_remove(ChatPacket(message, at))
