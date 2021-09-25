import logging
import sys
from collections.abc import Collection
from typing import (Any, Awaitable, Callable, Coroutine, Generator, Generic, MutableSequence, Optional,
                    Sequence, TypeVar, Union)

T = TypeVar('T', bound=type)
E = TypeVar('E')

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


class ColoredFormatter(logging.Formatter):
    use_color: bool

    def __init__(self, use_color: bool = True):
        super().__init__(FORMAT, DATA_FORMAT)
        self.use_color = use_color

    def format(self, record: logging.LogRecord):
        levelname = record.levelname
        message = super().format(record)
        if self.use_color and levelname in COLORS:
            message = COLOR_SEQ % COLORS[levelname] + message + RESET_SEQ
        return message


def autoslots(cls: T) -> T:
    slots = set(cls.__slots__) if hasattr(cls, '__slots__') else set()
    slots.update(cls.__annotations__.keys())
    cls.__slots__ = slots
    return cls


@autoslots
class View(Generic[E]):
    c: Sequence[E]
    start: int
    end: Optional[int]

    def __init__(self, c: Sequence[E], start: int, end: Optional[int] = None) -> None:
        self.c = c
        self.start = start
        self.end = end

    def _index_error(self, i: int):
        raise IndexError(f'{i} out of bounds for View({self.c}, {self.start}, {self.end})')

    def _get_index(self, i: Union[int, slice]) -> Union[int, slice]:
        if isinstance(i, slice):
            start = self._get_index(i.start)
            stop = None if slice.stop is None else self._get_index(i.stop)
            return slice(start, i.step, stop)
        end = len(self.c) if self.end is None else self.end
        if i < 0:
            index = end + i
        else:
            index = self.start + i
        if index < self.start or index >= end:
            self._index_error(i)
        return index

    def __getitem__(self, i: Union[int, slice]) -> Union[E, Sequence[E]]:
        return self.c[self._get_index(i)]


@autoslots
class MutableView(View[E], Generic[E]):
    c: MutableSequence[E]

    def __init__(self, c: MutableSequence[E], start: int, end: Optional[int] = None) -> None:
        self.c = c
        self.start = start
        self.end = end

    def __setitem__(self, i: Union[int, slice], v: E) -> None:
        # Why does Pyright hate me?
        self.c[self._get_index(i)] = v # type: ignore


@autoslots
class MaxSizedDict(dict):
    max_size: int

    def __init__(self, *args, max_size: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.max_size = max_size

    def __setitem__(self, k, v) -> None:
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


def spiral_loop_gen(w: int, h: int, cb: Callable[[int, int], E]) -> Generator[E, None, None]:
    x = y = 0
    dx = 0
    dy = -1
    for i in range(max(w, h)**2):
        if (-w/2 < x <= w/2) and (-h/2 < y <= h/2):
            yield cb(x, y)
        if x == y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
            dx, dy = -dy, dx
        x, y = x+dx, y+dy


async def spiral_loop_async(w: int, h: int, cb: Callable[[int, int], Awaitable[Any]]):
    x = y = 0
    dx = 0
    dy = -1
    for i in range(max(w, h)**2):
        if (-w/2 < x <= w/2) and (-h/2 < y <= h/2):
            await cb(x, y)
        if x == y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
            dx, dy = -dy, dx
        x, y = x+dx, y+dy


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