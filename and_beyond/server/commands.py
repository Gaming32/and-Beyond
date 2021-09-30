from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from and_beyond.server.client import Client

Command = Callable[['Client', str], Awaitable[Any]]


async def tps_command(client: 'Client', args: str) -> None:
    tps = client.server.get_multi_tps_str()
    await client.send_chat(tps)


async def mspt_command(client: 'Client', args: str) -> None:
    mspt = client.server.get_multi_mspt_str()
    await client.send_chat(mspt)


async def stats_command(client: 'Client', args: str) -> None:
    await tps_command(client, args)
    await mspt_command(client, args)


COMMANDS: dict[str, Command] = {
    'tps': tps_command,
    'mspt': mspt_command,
    'stats': stats_command,
}
