# ...and BEYOND

...and BEYOND is an open-world sandbox, similar to Minecraft. It is my PyWeek 32 (Neverending) submission. It also currently has a public multiplayer testing server at `mc.jemnetworks.com`.

## Running

Simply run `run_game.py`! If you have an incorrect version of Python, it will tell you. If you don't have a dependency installed, it will prompt you to install it.

## Controls

Control     | Action
----------- | ---------------------------
A           | Move left
D           | Move right
Space       | Jump
Escape      | Pause
Left click  | Break block
Right click | Place block
T           | Open chat
/           | Open chat with `/` pretyped
1           | Select stone block
2           | Select dirt block
3           | Select grass block
4           | Select wood block
5           | Select planks block
6           | Select leaves block
F3          | Open debug menu

## Command-line arguments

Argument                  | Action
--------------------------| ----------------------------------------------------------------
`--auth-server <address>` | Use the specified authentication server instead of the default
`--insecure-auth`         | Allow the auth server to be insecure (use HTTP instead of HTTPS)
`--debug`                 | Run in debug mode (shows debug messages)

### Servers

Argument                          | Action
--------------------------------- | -------------------------------------------------------------------------------------
`--world <name>`                  | Use the world called `<name>`
`--listen <[host]:[port]>`        | Listen on the specified host and port (default host: `0.0.0.0`, default port: `7932`)
`--singleplayer <fd_in> <fd_out>` | **Internal use only**
