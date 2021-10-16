import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from and_beyond.server.command import AbstractCommandSender

Command = Callable[['AbstractCommandSender', str], Awaitable[Any]]


async def help_command(sender: 'AbstractCommandSender', args: str) -> None:
    help_lines = [
        "Here's a list of the commands you can use:",
        " + /help  -- Show this help",
        " + /say   -- Send a message",
        " + /list  -- List the players online",
        " + /tps   -- Show the server's average TPS",
        " + /mspt  -- Show the server's average MSPT",
        " + /stats -- Show the some server stats",
    ]
    if sender.operator >= 3:
        help_lines.extend([
            " + /stop  -- Stop the server",
        ])
    for help_line in help_lines:
        await sender.reply(help_line)


async def say_command(sender: 'AbstractCommandSender', args: str) -> None:
    await sender.server.send_chat(f'<{sender.name}> {args}', log=True)


async def list_command(sender: 'AbstractCommandSender', args: str) -> None:
    players = [
        c.player
        for c in sender.server.clients
        if c.player is not None
    ]
    player_text = ', '.join(str(p) for p in players)
    await sender.reply(f'There are {len(players)} player(s) online: {player_text}')


async def tps_command(sender: 'AbstractCommandSender', args: str) -> None:
    tps = sender.server.get_multi_tps_str()
    await sender.reply(tps)


async def mspt_command(sender: 'AbstractCommandSender', args: str) -> None:
    mspt = sender.server.get_multi_mspt_str()
    await sender.reply(mspt)


async def stats_command(sender: 'AbstractCommandSender', args: str) -> None:
    await tps_command(sender, args)
    await mspt_command(sender, args)


async def stop_command(sender: 'AbstractCommandSender', args: str) -> None:
    if sender.operator < 3:
        await sender.no_permissions(3)
        return
    await sender.reply('Stopping server...')
    logging.info('%s stopped server with /stop.', sender)
    sender.server.running = False


COMMANDS: dict[str, Command] = {
    'help': help_command,
    'say': say_command,
    'list': list_command,
    'tps': tps_command,
    'mspt': mspt_command,
    'stats': stats_command,
    'stop': stop_command,
}
