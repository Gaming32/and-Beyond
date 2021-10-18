import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from and_beyond.server.client import Client
from and_beyond.server.command import (ClientCommandSender,
                                       ConsoleCommandSender, evaluate_client)

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
    if sender.operator >= 1:
        help_lines.extend([
            " + /tp    -- Teleport a player",
        ])
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


async def tp_command(sender: 'AbstractCommandSender', args: str) -> None:
    if sender.operator < 1:
        await sender.no_permissions(1)
        return
    argv = args.split()
    if len(argv) == 0:
        await sender.reply('Usage:')
        if isinstance(sender, ConsoleCommandSender):
            await sender.reply('  /tp <from> <to>')
            await sender.reply('  /tp <from> <x> <y>')
        else:
            await sender.reply('  /tp [from] <to>')
            await sender.reply('  /tp [from] <x> <y>')
        return
    elif len(argv) == 1:
        if not isinstance(sender, ClientCommandSender):
            await sender.reply('Usage:')
            await sender.reply('  /tp <from> <to>')
            await sender.reply('  /tp <from> <x> <y>')
            return
        from_ = sender.client
        to = evaluate_client(argv[0], sender)
        if to is None:
            return await sender.reply('First argument must be player')
    elif len(argv) == 2:
        from_ = evaluate_client(argv[0], sender)
        if from_ is None:
            if isinstance(sender, ClientCommandSender):
                try:
                    from_ = float(argv[0])
                except ValueError:
                    return await sender.reply('First argument must be player or number')
            else:
                return await sender.reply('First argument must be player')
        if isinstance(from_, float):
            assert isinstance(sender, ClientCommandSender)
            x = from_
            try:
                y = float(argv[1])
            except ValueError:
                return await sender.reply('Second argument must be number')
            from_ = sender.client
            to = (x, y)
        else:
            to = evaluate_client(argv[1], sender)
            if to is None:
                return await sender.reply('Second argument must be player')
    else:
        from_ = evaluate_client(argv[0], sender)
        if from_ is None:
            return await sender.reply('First argument must be player')
        try:
            x = float(argv[1])
        except ValueError:
            return await sender.reply('Second argument must be number')
        try:
            y = float(argv[2])
        except ValueError:
            return await sender.reply('Third argument must be number')
        to = (x, y)
    from_ = from_.player
    if isinstance(to, Client):
        to = to.player
        from_.x = to.x
        from_.y = to.y
    else:
        from_.x, from_.y = to
    await from_.send_position()
    await sender.reply_broadcast(f'Teleported {from_} to {to}')


async def stop_command(sender: 'AbstractCommandSender', args: str) -> None:
    if sender.operator < 3:
        await sender.no_permissions(3)
        return
    await sender.reply_broadcast('Stopping server...')
    logging.info('%s stopped server with /stop.', sender)
    sender.server.running = False


COMMANDS: dict[str, Command] = {
    'help': help_command,
    'say': say_command,
    'list': list_command,
    'tps': tps_command,
    'mspt': mspt_command,
    'stats': stats_command,
    'tp': tp_command,
    'stop': stop_command,
}
