import asyncio
import logging
import time
import uuid
from asyncio import StreamReader, StreamWriter
from asyncio.events import AbstractEventLoop
from asyncio.exceptions import CancelledError
from typing import TYPE_CHECKING, Optional

from and_beyond.common import (MAX_LOADED_CHUNKS, MOVE_SPEED_CAP_SQ, VIEW_DISTANCE,
                         VIEW_DISTANCE_BOX)
from and_beyond.packet import (AddVelocityPacket, AuthenticatePacket, ChunkPacket,
                         ChunkUpdatePacket, DisconnectPacket, Packet,
                         PlayerPositionPacket, UnloadChunkPacket, read_packet,
                         write_packet)
from and_beyond.server.player import Player
from and_beyond.utils import spiral_loop_async, spiral_loop_gen
from and_beyond.world import BlockTypes, WorldChunk

if TYPE_CHECKING:
    from and_beyond.server.main import AsyncServer


class Client:
    server: 'AsyncServer'
    reader: StreamReader
    writer: StreamWriter
    aloop: AbstractEventLoop
    packet_queue: asyncio.Queue[Packet]
    ready: bool
    disconnecting: bool

    auth_uuid: Optional[uuid.UUID]
    packet_task: asyncio.Task
    loaded_chunks: dict[tuple[int, int], WorldChunk]

    player: Player

    def __init__(self, server: 'AsyncServer', reader: StreamReader, writer: StreamWriter) -> None:
        self.server = server
        self.reader = reader
        self.writer = writer
        self.aloop = server.loop
        self.auth_uuid = None
        self.loaded_chunks = {}

    async def start(self) -> None:
        self.ready = False
        try:
            auth_packet = await asyncio.wait_for(read_packet(self.reader), 3)
        except asyncio.TimeoutError:
            return await self.disconnect('Authentication timeout')
        if not isinstance(auth_packet, AuthenticatePacket):
            return await self.disconnect('Malformed authentication packet')
        self.auth_uuid = auth_packet.auth_id
        logging.info('Player logged in with UUID %s', self.auth_uuid)
        self.disconnecting = False
        self.packet_queue = asyncio.Queue()
        self.packet_task = self.aloop.create_task(self.packet_tick())
        self.player = Player(self)
        await self.player.ainit()
        await self.load_chunks_around_player()
        self.ready = True

    async def load_chunk(self, x: int, y: int) -> None:
        chunk = self.server.world.get_generated_chunk(x, y, self.server.world_generator)
        self.loaded_chunks[(x, y)] = chunk
        packet = ChunkPacket(chunk)
        await write_packet(packet, self.writer)

    async def unload_chunk(self, x: int, y: int) -> None:
        self.loaded_chunks.pop((x, y))
        packet = UnloadChunkPacket(x, y)
        await write_packet(packet, self.writer)

    async def load_chunks_around_player(self) -> None:
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
        await asyncio.gather(*
            spiral_loop_gen(
                VIEW_DISTANCE_BOX,
                VIEW_DISTANCE_BOX,
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

    async def packet_tick(self) -> None:
        while self.server.running:
            try:
                packet = await read_packet(self.reader)
            except asyncio.IncompleteReadError:
                await self.disconnect(f'{self} left the game', False)
                return
            await self.packet_queue.put(packet)

    async def tick(self) -> None:
        if not self.ready:
            return
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
                            chunk.set_tile_type(packet.bx, packet.by, packet.block)
                        else:
                            # logging.warn("Player %s can't reach block %i, %i, yet they tried to update it.", self, abs_x, abs_y)
                            packet.block = chunk.get_tile_type(packet.bx, packet.by)
                            await write_packet(packet, self.writer)
                elif isinstance(packet, PlayerPositionPacket):
                    logging.warn('Player %s used illegal packet: PLAYER_POSITION (this packet is deprecated and a security hole)', self)
                    await self.disconnect('Used illegal packet: PLAYER_POSITION (this packet is deprecated and a security hole)')
                    continue
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
                        logging.warn('Player %s moved too quickly! %f, %f', self, new_x, new_y)
                        await self.player.send_position()
                    else:
                        self.player.physics.x_velocity = new_x
                        self.player.physics.y_velocity = new_y
                else:
                    logging.warn('Client %s sent invalid packet: %s', self, packet.type.name)
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
        if self.disconnecting:
            logging.debug('Already disconnecting %s', self)
            return
        self.disconnecting = True
        logging.debug('Disconnecting player %s', self)
        if kick:
            packet = DisconnectPacket(reason)
            try:
                await write_packet(packet, self.writer)
            except ConnectionError:
                logging.debug('Player was already disconnected')
        self.writer.close()
        await self.writer.wait_closed()
        try:
            self.server.clients.remove(self)
        except ValueError:
            pass
        start = time.perf_counter()
        await self.player.save()
        end = time.perf_counter()
        logging.debug('Player %s data saved in %f seconds', self, end - start)
        logging.info('Player %s disconnected for reason: %s', self, reason)
        self.packet_task.cancel() # Must happen last, as this could cancel this method (if it was called from packet_tick)
