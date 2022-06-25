import time
from typing import Optional


class ChatMessage:
    message: str
    time: float

    def __init__(self, message: str, at: Optional[float] = None) -> None:
        if at is None:
            at = time.time()
        self.message = message
        self.time = at
