from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from and_beyond.server.client import Client

Command = Callable[['Client', str], Awaitable[Any]]


async def help_command(client: 'Client', args: str) -> None:
    for help_line in (
        "Here's a list of the commands you can use:",
        " + /help  -- Show this help",
        " + /list  -- List the players online",
        " + /tps   -- Show the server's average TPS",
        " + /mspt  -- Show the server's average MSPT",
        " + /stats -- Show the some server stats",
    ):
        await client.send_chat(help_line)


async def list_command(client: 'Client', args: str) -> None:
    players = [
        c.player
        for c in client.server.clients
        if c.player is not None
    ]
    player_text = ', '.join(str(p) for p in players)
    await client.send_chat(f'There are {len(players)} player(s) online: {player_text}')


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
    'help': help_command,
    'list': list_command,
    'tps': tps_command,
    'mspt': mspt_command,
    'stats': stats_command,
}
