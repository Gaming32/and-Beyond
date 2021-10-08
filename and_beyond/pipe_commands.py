import enum
from typing import BinaryIO, TypeVar

_T_int = TypeVar('_T_int', bound=int)


class PipeCommandsToServer(enum.IntEnum):
    SHUTDOWN = 0
    PAUSE = 1
    UNPAUSE = 2
    OPEN_TO_LAN = 3


class PipeCommandsToClient(enum.IntEnum):
    pass


def write_pipe(pipe: BinaryIO, command: int, size: int = 2, signed: bool = False):
    pipe.write(command.to_bytes(size, 'little', signed=signed))


def read_pipe(pipe: BinaryIO, cls: type[_T_int] = int, size: int = 2, signed: bool = False) -> _T_int:
    return cls.from_bytes(pipe.read(size), 'little', signed=signed) # type: ignore
