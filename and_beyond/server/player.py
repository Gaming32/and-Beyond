import json
from asyncio.events import AbstractEventLoop
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
from and_beyond.abstract_player import AbstractPlayer
from and_beyond.packet import PlayerPositionPacket, write_packet
from and_beyond.physics import PlayerPhysics
from and_beyond.utils import autoslots

if TYPE_CHECKING:
    from and_beyond.server.client import Client


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
        world = self.client.server.world
        spawn_x = world.meta['spawn_x']
        spawn_x = 0 if spawn_x is None else spawn_x
        spawn_y = world.meta['spawn_y']
        spawn_y = 0 if spawn_y is None else spawn_y
        if self.data_path.exists():
            async with aiofiles.open(self.data_path) as fp:
                raw_data = await fp.read()
            try:
                data: dict[str, Any] = await self.aloop.run_in_executor(None, json.loads, raw_data)
            except json.JSONDecodeError:
                pass
            else:
                self.x = data.get('x', spawn_x)
                self.y = data.get('y', spawn_y)
                self.physics.x_velocity = data.get('x_velocity', 0)
                self.physics.y_velocity = data.get('y_velocity', 0)
        else:
            self.x = spawn_x
            self.y = spawn_y
        packet = PlayerPositionPacket(self.x, self.y)
        await write_packet(packet, self.client.writer)

    async def save(self) -> None:
        data = {
            'x': self.x,
            'y': self.y,
            'x_velocity': self.physics.x_velocity,
            'y_velocity': self.physics.y_velocity,
        }
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
