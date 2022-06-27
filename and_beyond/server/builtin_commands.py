import sys

import humanize

from and_beyond.server.client import Client
from and_beyond.server.commands import (COMMANDS, AbstractCommandSender, ClientCommandSender, ConsoleCommandSender,
                                        evaluate_client, evaluate_offline_player, function_command)

if sys.platform != 'win32':
    import resource


@function_command('help', 'Show this help', 0)
async def help_command(sender: AbstractCommandSender, args: str) -> None:
    max_name_width = max(len(c) for c in COMMANDS)
    await sender.reply("Here's a list of the commands you can use:")
    for (name, command) in COMMANDS.items():
        if sender.operator >= command.permission and command.description is not None:
            await sender.reply(f' + /{name:{max_name_width}} -- {command.description}')


@function_command('say', 'Send a message', 0)
async def say_command(sender: AbstractCommandSender, args: str) -> None:
    await sender.server.send_chat(f'<{sender.name}> {args}', log=True)


@function_command('list', 'List the players online', 0)
async def list_command(sender: AbstractCommandSender, args: str) -> None:
    players = [
        c.player
        for c in sender.server.clients
        if c.player is not None
    ]
    player_text = ', '.join(str(p) for p in players)
    await sender.reply(f'There are {len(players)} player(s) online: {player_text}')


@function_command('tps', "Show the server's average TPS", 0)
async def tps_command(sender: AbstractCommandSender, args: str) -> None:
    tps = sender.server.get_multi_tps_str()
    await sender.reply(tps)


@function_command('mspt', "Show the server's average MSPT", 0)
async def mspt_command(sender: AbstractCommandSender, args: str) -> None:
    mspt = sender.server.get_multi_mspt_str()
    await sender.reply(mspt)


@function_command('stats', 'Show some server stats', 0)
async def stats_command(sender: AbstractCommandSender, args: str) -> None:
    await tps_command.call(sender, args)
    await mspt_command.call(sender, args)
    if sys.platform != 'win32':
        memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        await sender.reply(
            f'Memory usage: '
            f'{humanize.naturalsize(memory_usage * 1024, gnu=True)} '
            f'({memory_usage}K)'
        )


@function_command('tp', 'Teleport a player', 1)
async def tp_command(sender: AbstractCommandSender, args: str) -> None:
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
    if isinstance(to, Client):
        assert to.player is not None
        to = to.player
        await from_.set_position_safe(to.x, to.y, True)
    else:
        await from_.set_position_safe(*to, True)
    from_.load_chunks_around_player_task()
    assert from_.player is not None
    await sender.reply_broadcast(f'Teleported {from_.player} to {to}')


@function_command('kick', 'Forcefully disconnect a player', 2)
async def kick_command(sender: AbstractCommandSender, args: str) -> None:
    argv = args.split(None, 1)
    if len(argv) == 0:
        await sender.reply('Usage:')
        await sender.reply(f'  /kick <player> [reason]')
        return None
    client = evaluate_client(argv[0], sender)
    if client is None:
        await sender.reply('First argument must be player')
        return None
    reason = (len(argv) > 1 and argv[1]) or f'Kicked by operator'
    await client.disconnect(reason)
    await sender.reply_broadcast(f'Kicked {client.player} for reason "{reason}"')


@function_command('ban', 'Bans a player', 2)
async def ban_command(sender: AbstractCommandSender, args: str) -> None:
    argv = args.split(None, 1)
    if len(argv) == 0:
        await sender.reply('Usage:')
        await sender.reply(f'  /ban <player> [reason]')
        return None
    reason = (len(argv) > 1 and argv[1]) or f'Banned by operator'
    client = evaluate_client(argv[0], sender)
    if client is None:
        player = await evaluate_offline_player(argv[0], sender)
        if player is None:
            await sender.reply('First argument must be player')
            return
        player.banned = reason
        await player.save()
    else:
        player = client.player
        if player is not None:
            player.banned = reason
        await client.disconnect(reason)
    await sender.reply_broadcast(f'Banned {player} for reason "{reason}"')


@function_command('unban', 'Removes a ban from a player', 2)
async def unban_command(sender: AbstractCommandSender, args: str) -> None:
    player = await evaluate_offline_player(args, sender)
    if player is None:
        await sender.reply('First argument must be player')
        return None
    player.banned = None
    await player.save()
    await sender.reply_broadcast(f'{player} unbanned')


@function_command('op', 'Sets a players operator level', 3)
async def op_command(sender: AbstractCommandSender, args: str) -> None:
    argv = args.split(None, 1)
    if len(argv) == 0:
        await sender.reply('Usage:')
        await sender.reply(f'  /op <player> [level]')
        return None
    if len(argv) > 1:
        try:
            level = int(argv[1])
        except ValueError:
            await sender.reply('Second argument must be integer')
            return
    else:
        level = min(sender.operator, 2)
    if level > sender.operator:
        await sender.reply("Can't set a player's operator level to be greater than your own.")
        return
    client = evaluate_client(argv[0], sender)
    if client is None:
        player = await evaluate_offline_player(argv[0], sender)
        if player is None:
            await sender.reply('First argument must be player')
            return
        player.operator_level = level
        await player.save()
    else:
        player = client.player
        if player is not None:
            player.operator_level = level
    await sender.reply_broadcast(f"Set {player}'s operator level to {level}")


@function_command('deop', 'Sets a players operator level to 0', 3)
async def deop_command(sender: AbstractCommandSender, args: str) -> None:
    argv = args.split(None, 1)
    if len(argv) == 0:
        await sender.reply('Usage:')
        await sender.reply(f'  /deop <player>')
        return None
    await op_command.call(sender, f'{argv[0]} 0')


@function_command('stop', 'Stop the server', 4)
async def stop_command(sender: AbstractCommandSender, args: str) -> None:
    await sender.reply_broadcast('Stopping server...')
    sender.server.running = False
