import asyncio
import logging
import random
import sys
from asyncio.events import AbstractEventLoop
from typing import Any, Awaitable, Callable, Generator, Generic, Iterable, Optional, Sequence, TypeVar, Union, overload

_T = TypeVar('_T')
_KT = TypeVar('_KT')
_KV = TypeVar('_KV')

RESET_SEQ = '\033[0m'
COLOR_SEQ = '\033[%sm'

COLORS = {
    'WARN': '33',
    'DEBUG': '36',
    'SEVERE': '41;37',
    'ERROR': '31'
}

FORMAT = '[%(asctime)s] [%(threadName)s/%(levelname)s] [%(filename)s:%(lineno)i]: %(message)s'
DATA_FORMAT = '%H:%M:%S'

DEBUG = '--debug' in sys.argv


@overload
def mean(values: Sequence[float]) -> float: ...

@overload
def mean(values: Iterable[float]) -> float: ...

def mean(values) -> float:
    if hasattr(values, '__len__'):
        return sum(values) / len(values)
    i = 0
    s = 0.0
    v: float
    for (i, v) in enumerate(values):
        s += v
    return s / (i + 1)


class copy_signature(Generic[_T]):
    def __init__(self, target: _T) -> None: ...
    def __call__(self, wrapped: Callable[..., Any]) -> _T: ...


def no_op(return_val: _T) -> Callable[..., _T]:
    return (lambda *args, **kwargs: return_val)

NO_OP = no_op(None)


class ColoredFormatter(logging.Formatter):
    use_color: bool

    def __init__(self, use_color: bool = True) -> None:
        super().__init__(FORMAT, DATA_FORMAT)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        message = super().format(record)
        if self.use_color and levelname in COLORS:
            message = COLOR_SEQ % COLORS[levelname] + message + RESET_SEQ
        return message


def get_opt(opt: str, offset: int = 1) -> str:
    return sys.argv[sys.argv.index(opt) + offset]


class MaxSizedDict(dict[_KT, _KV], Generic[_KT, _KV]):
    max_size: int

    def __init__(self, *args, max_size: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.max_size = max_size

    def __setitem__(self, k: _KT, v: _KV) -> None:
        super().__setitem__(k, v)
        if self.max_size > 0 and len(self) > self.max_size:
            del self[next(iter(self))]


def spiral_loop(w: int, h: int, cb: Callable[[int, int], Any]) -> None:
    x = y = 0
    dx = 0
    dy = -1
    for i in range(max(w, h)**2):
        if (-w/2 < x <= w/2) and (-h/2 < y <= h/2):
            cb(x, y)
        if x == y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
            dx, dy = -dy, dx
        x, y = x+dx, y+dy


def spiral_loop_gen(w: int, h: int, cb: Callable[[int, int], _T]) -> Generator[_T, None, None]:
    x = y = 0
    dx = 0
    dy = -1
    for i in range(max(w, h)**2):
        if (-w/2 < x <= w/2) and (-h/2 < y <= h/2):
            yield cb(x, y)
        if x == y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
            dx, dy = -dy, dx
        x, y = x+dx, y+dy


async def spiral_loop_async(w: int, h: int, cb: Callable[[int, int], Awaitable[Any]]) -> None:
    x = y = 0
    dx = 0
    dy = -1
    for i in range(max(w, h)**2):
        if (-w/2 < x <= w/2) and (-h/2 < y <= h/2):
            await cb(x, y)
        if x == y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
            dx, dy = -dy, dx
        x, y = x+dx, y+dy


async def ainput(prompt: str = '', loop: Optional[AbstractEventLoop] = None) -> str:
    if loop is None:
        loop = asyncio.get_running_loop()
    if prompt:
        sys.stdout.write(prompt)
    return await loop.run_in_executor(None, sys.stdin.readline)


def copy_obj_to_class(obj: Any, to: Union[type[_T], _T]) -> _T:
    if hasattr(obj, '__slots__'):
        copy_attrs = set(obj.__slots__)
    else:
        copy_attrs = set(obj.__dict__)
    if hasattr(to, '__slots__'):
        copy_attrs.intersection_update(to.__slots__) # type: ignore
    if isinstance(to, type):
        to = to.__new__(to) # type: ignore
    for attr in copy_attrs:
        setattr(to, attr, getattr(obj, attr))
    return to # type: ignore


def shuffled(it: Iterable[_T]) -> list[_T]:
    l = list(it)
    random.shuffle(l)
    return l


def init_logger(log_file: str) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    logging.addLevelName(logging.WARN, 'WARN')
    logging.addLevelName(logging.CRITICAL, 'SEVERE')
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_file, 'w', encoding='utf-8'),
    ]
    handlers[0].setFormatter(ColoredFormatter(True))
    handlers[1].setFormatter(ColoredFormatter(False))
    for handler in handlers:
        root.addHandler(handler)
