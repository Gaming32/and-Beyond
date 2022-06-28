import abc
import asyncio
import logging
import time
from json.decoder import JSONDecodeError
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional
from uuid import UUID
from and_beyond.text import MaybeText

from and_beyond.world import OfflinePlayer

if TYPE_CHECKING:
    from and_beyond.server.client import Client
    from and_beyond.server.main import AsyncServer

CommandCallable = Callable[['AbstractCommandSender', str], Awaitable[Any]]


class AbstractCommandSender(abc.ABC):
    name: str
    server: 'AsyncServer'
    operator: int

    @abc.abstractmethod
    async def reply(self, message: MaybeText) -> None:
        pass

    async def reply_broadcast(self, message: MaybeText) -> None:
        await self.reply(message)
        logging_message = f'[{self}: {message}]'
        logging.info(logging_message)
        at = time.time()
        check = self.client if isinstance(self, ClientCommandSender) else None
        await asyncio.gather(*(
            self.server.loop.create_task(client.send_chat(logging_message, at))
            for client in self.server.clients
            if (client.ready
                and client is not check
                and client.player is not None
                and client.player.operator_level > 0)
        ))

    async def no_permissions(self, min_level: int) -> None:
        await self.reply('You do not have the permissions for that command.')
        await self.reply(f'It requires a minimum permission level of {min_level},')
        await self.reply(f'but you only have a permission level of {self.operator}.')

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<CommandSender name={self.name!r}>'


class ConsoleCommandSender(AbstractCommandSender):
    name = 'CONSOLE'
    operator = 4

    def __init__(self, server: 'AsyncServer') -> None:
        self.server = server

    async def reply(self, message: str) -> None:
        print(message) # Wow so complicated


class ClientCommandSender(AbstractCommandSender):
    client: 'Client'

    def __init__(self, client: 'Client') -> None:
        self.server = client.server
        self.client = client

    @property
    def name(self) -> str:
        if self.client.nickname is None:
            # Use client's IP address instead
            return self.client._writer.get_extra_info('peername')[0]
        return self.client.nickname

    @property
    def operator(self) -> int:
        if self.client.player is None:
            return 0
        return self.client.player.operator_level

    async def reply(self, message: MaybeText) -> None:
        return await self.client.send_chat(message)


class Command(abc.ABC):
    name: str
    description: Optional[str]
    permission: int

    def __init__(self, name: str, description: Optional[str] = None, permission: int = 0) -> None:
        self.name = name
        self.description = description
        self.permission = permission

    @abc.abstractmethod
    async def call(self, sender: AbstractCommandSender, args: str) -> Any:
        raise NotImplementedError

    async def validate_permission(self, sender: AbstractCommandSender) -> bool:
        if sender.operator < self.permission:
            await sender.no_permissions(self.permission)
            return False
        return True


class WrapperCommand(Command):
    func: CommandCallable

    def __init__(self, func: CommandCallable, name: str, description: Optional[str] = None, permission: int = 0) -> None:
        super().__init__(name, description=description, permission=permission)
        self.func = func

    async def call(self, sender: AbstractCommandSender, args: str) -> Any:
        if not await self.validate_permission(sender):
            return
        return await self.func(sender, args)


def function_command(
        name: str,
        description: Optional[str] = None,
        permission: int = 0
    ) -> Callable[[CommandCallable], Command]:
    def decorator(fn: CommandCallable) -> Command:
        command = WrapperCommand(fn, name, description, permission)
        COMMANDS[name] = command
        return command
    return decorator


def evaluate_client(arg: str, sender: AbstractCommandSender) -> Optional['Client']:
    server = sender.server
    if arg in server.clients_by_name:
        return server.clients_by_name[arg]
    try:
        uuid = UUID(arg)
    except ValueError:
        return None
    if uuid in server.clients_by_uuid:
        return server.clients_by_uuid[uuid]
    return None


async def evaluate_offline_player(arg: str, sender: AbstractCommandSender) -> Optional[OfflinePlayer]:
    server = sender.server
    if arg in server.clients_by_name:
        return server.clients_by_name[arg].player
    world = server.world
    assert world is not None
    try:
        uuid = UUID(arg)
    except ValueError:
        pass
    else:
        if uuid in server.clients_by_uuid:
            return server.clients_by_uuid[uuid].player
        player = world.get_player_by_uuid(uuid)
        try:
            await player.ainit()
        except (FileNotFoundError, JSONDecodeError):
            pass
        else:
            return player
    try:
        player = world.get_player_by_name(arg)
    except KeyError:
        return None
    try:
        await player.ainit()
    except (FileNotFoundError, JSONDecodeError):
        return None
    return player


COMMANDS: dict[str, Command] = {}
