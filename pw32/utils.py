import logging
import sys
from typing import TypeVar

T = TypeVar('T', bound=type)

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


def init_logger() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    logging.addLevelName(logging.WARN, 'WARN')
    logging.addLevelName(logging.CRITICAL, 'SEVERE')
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler('latest.log', 'w', encoding='utf-8'),
    ]
    handlers[0].setFormatter(ColoredFormatter(True))
    handlers[1].setFormatter(ColoredFormatter(False))
    for handler in handlers:
        root.addHandler(handler)
