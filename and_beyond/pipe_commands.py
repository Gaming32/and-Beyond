import enum


class PipeCommandsToServer(enum.IntEnum):
    SHUTDOWN = 0
    PAUSE = 1
    UNPAUSE = 2


class PipeCommandsToClient(enum.IntEnum):
    pass
