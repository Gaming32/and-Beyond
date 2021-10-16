import abc
from asyncio.streams import StreamReader, StreamWriter
from io import BytesIO
from typing import Callable, Sequence, Union

WriterMiddleware = Union['WriterMiddlewareABC', StreamWriter]
WriterMiddlewareFactory = Callable[[WriterMiddleware], WriterMiddleware]

ReaderMiddleware = Union['ReaderMiddlewareABC', StreamReader]
ReaderMiddlewareFactory = Callable[[ReaderMiddleware], ReaderMiddleware]


# Default implementation of methods is no-op, this is useful for subclasses that don't use all functionality
class WriterMiddlewareABC(abc.ABC):
    next: WriterMiddleware

    def __init__(self, next: WriterMiddleware) -> None:
        self.next = next

    def write(self, data: bytes) -> None:
        return self.next.write(data)

    async def drain(self) -> None:
        return await self.next.drain()


class ReaderMiddlewareABC(abc.ABC):
    next: ReaderMiddleware

    def __init__(self, next: ReaderMiddleware) -> None:
        self.next = next

    async def readline(self) -> bytes:
        return await self.next.readline()

    async def readuntil(self, separator: bytes = b'\n'):
        return await self.next.readuntil(separator)

    async def read(self, n: int = -1) -> bytes:
        return await self.next.read(n)

    async def readexactly(self, n: int) -> bytes:
        return await self.next.readexactly(n)


class BufferedWriterMiddleware(WriterMiddlewareABC):
    _buffer: BytesIO

    def __init__(self, next: WriterMiddleware) -> None:
        super().__init__(next)
        self._buffer = BytesIO()

    def write(self, data: bytes) -> None:
        self._buffer.write(data)

    async def drain(self) -> None:
        self.next.write(self._buffer.getvalue())
        self._buffer.seek(0)
        self._buffer.truncate(0)
        return await self.next.drain()


class _EncryptedWriterMiddleware(WriterMiddlewareABC):
    key: bytes
    _i: int
    _mod: int

    def __init__(self, next: WriterMiddleware, key: bytes) -> None:
        super().__init__(next)
        self.key = key
        self._i = 0
        self._mod = len(key) - 1

    def write(self, data: bytes) -> None:
        i = self._i
        self.next.write(bytes(
            ((b + self.key[(i + j) & self._mod]) & 255)
            for (j, b) in enumerate(data)
        ))
        self._i = (i + len(data)) & self._mod


def EncryptedWriterMiddleware(key: bytes) -> WriterMiddlewareFactory:
    def factory(next: WriterMiddleware) -> _EncryptedWriterMiddleware:
        return _EncryptedWriterMiddleware(next, key)
    return factory


class _EncryptedReaderMiddleware(ReaderMiddlewareABC):
    key: bytes
    _i: int
    _mod: int

    def __init__(self, next: ReaderMiddleware, key: bytes) -> None:
        super().__init__(next)
        self.key = key
        self._i = 0
        self._mod = len(key) - 1

    def _decrypt(self, data: bytes) -> bytes:
        i = self._i
        result = bytes(
            ((b - self.key[(i + j) & self._mod]) & 255)
            for (j, b) in enumerate(data)
        )
        self._i = (i + len(data)) & self._mod
        return result

    async def readline(self) -> bytes:
        return self._decrypt(await self.next.readline())

    async def readuntil(self, separator: bytes = b'\n'):
        return self._decrypt(await self.next.readuntil(separator))

    async def read(self, n: int = -1) -> bytes:
        return self._decrypt(await self.next.read(n))

    async def readexactly(self, n: int) -> bytes:
        return self._decrypt(await self.next.readexactly(n))


def EncryptedReaderMiddleware(key: bytes) -> ReaderMiddlewareFactory:
    def factory(next: ReaderMiddleware) -> _EncryptedReaderMiddleware:
        return _EncryptedReaderMiddleware(next, key)
    return factory


def create_writer_middlewares(middlewares: Sequence[WriterMiddlewareFactory], writer: WriterMiddleware) -> WriterMiddleware:
    for middleware in reversed(middlewares):
        writer = middleware(writer)
    return writer


def create_reader_middlewares(middlewares: Sequence[ReaderMiddlewareFactory], reader: ReaderMiddleware) -> ReaderMiddleware:
    for middleware in reversed(middlewares):
        reader = middleware(reader)
    return reader
