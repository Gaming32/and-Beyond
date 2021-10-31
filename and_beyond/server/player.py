import asyncio
import json
import logging
from asyncio.events import AbstractEventLoop
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import aiofiles
from and_beyond.packet import PlayerPositionPacket
from and_beyond.physics import PlayerPhysics
from and_beyond.utils import autoslots
from and_beyond.world import OfflinePlayer

if TYPE_CHECKING:
    from and_beyond.server.client import Client


@autoslots
class Player(OfflinePlayer):
    name: str
    client: 'Client'
    physics: PlayerPhysics

    def __init__(self, client: 'Client', name: str = None) -> None:
        assert client.uuid is not None
        assert client.server.world is not None
        super().__init__(name or str(client.uuid), client.uuid, client.server.world)
        self.client = client
        self.physics = PlayerPhysics(self)
        self.loaded_chunks = client.loaded_chunks # Reference to fulfill AbstractPlayer

    async def move(self, x: float, y: float) -> None:
        self.x += x
        self.y += y
        await self.send_position()

    async def set_position(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        await self.send_position()

    async def send_position(self, force: bool = False) -> None:
        assert self.client.uuid is not None
        packet = PlayerPositionPacket(self.client.uuid, self.x, self.y)
        if force:
            await self.client.server.send_to_all(packet)
        else:
            await self.client.server.send_to_all(packet, (int(packet.x) >> 4, int(packet.y) >> 4))
