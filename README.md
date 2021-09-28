# ...and BEYOND

...and BEYOND is an open-world sandbox, similar to Minecraft. It is my PyWeek 32 (Neverending) submission.

## Running

Simply run `run_game.py`! If you have an incorrect version of Python, it will tell you. If you don't have a dependency installed, it will prompt you to install it.

## Controls

Control | Action
------- | ------
A       | Move left
D       | Move right
Space   | Jump
Escape  | Pause
Left click | Break block
Right click | Place block
F3      | Open debug menu
1       | Select stone block
2       | Select dirt block
3       | Select grass block

## Command-line arguments

Argument | Action
-------- | ------
`--debug` | Run in debug mode (shows debug messages)

### Servers

Argument | Action
-------- | ------
`--world <name>` | Use the world called `<name>`
`--listen <[host]:[port]>` | Listen on the specified host and port (default host: `0.0.0.0`, default port: `7932`)
`--singleplayer <fd_in> <fd_out>` | **Internal use only**
