import enum
from typing import BinaryIO, Optional, TypeVar, cast

_T_int = TypeVar('_T_int', bound=int)


class PipeCommandsToServer(enum.IntEnum):
    SHUTDOWN = 0
    PAUSE = 1
    UNPAUSE = 2
    OPEN_TO_LAN = 3


class PipeCommandsToClient(enum.IntEnum):
    pass


def write_pipe(pipe: BinaryIO, command: int, size: int = 2, signed: bool = False) -> None:
    pipe.write(command.to_bytes(size, 'little', signed=signed))


def read_pipe(pipe: BinaryIO, cls: type[_T_int] = int, size: int = 2, signed: bool = False) -> Optional[_T_int]:
    try:
        data = pipe.read(size)
    except OSError:
        return None
    if data is None:
        return None
    return cast(_T_int, cls.from_bytes(data, 'little', signed=signed))
