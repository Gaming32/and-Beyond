import json
from asyncio.events import AbstractEventLoop
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
from pw32.abstract_player import AbstractPlayer
from pw32.common import REACH_DISTANCE_SQ
from pw32.packet import PlayerPositionPacket, write_packet
from pw32.physics import PlayerPhysics
from pw32.utils import autoslots

if TYPE_CHECKING:
    from pw32.server.client import Client


@autoslots
class Player(AbstractPlayer):
    data_path: Path
    client: 'Client'
    physics: PlayerPhysics

    aloop: AbstractEventLoop

    def __init__(self, client: 'Client') -> None:
        world = client.server.world
        self.data_path = world.players_path / f'{client.auth_uuid}.json'
        self.client = client
        self.physics = PlayerPhysics(self)
        self.loaded_chunks = client.loaded_chunks # Reference to fulfill AbstractPlayer

    async def ainit(self) -> None:
        self.aloop = self.client.aloop
        if self.data_path.exists():
            async with aiofiles.open(self.data_path) as fp:
                raw_data = await fp.read()
            try:
                data = await self.aloop.run_in_executor(None, json.loads, raw_data)
            except json.JSONDecodeError:
                pass
            else:
                self.x = data['x']
                self.y = data['y']
        else:
            world = self.client.server.world
            x = world.meta['spawn_x']
            y = world.meta['spawn_y']
            self.x = 0 if x is None else x
            self.y = 0 if y is None else y
        packet = PlayerPositionPacket(self.x, self.y)
        await write_packet(packet, self.client.writer)

    async def save(self) -> None:
        data = {'x': self.x, 'y': self.y}
        raw_data = await self.aloop.run_in_executor(None, json.dumps, data)
        async with aiofiles.open(self.data_path, 'w') as fp:
            await fp.write(raw_data)

    async def move(self, x: float, y: float) -> None:
        self.x += x
        self.y += y
        await self.send_position()

    async def set_position(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        await self.send_position()

    async def send_position(self) -> None:
        packet = PlayerPositionPacket(self.x, self.y)
        await write_packet(packet, self.client.writer)
