import time
from typing import Optional

from and_beyond.text import MaybeText, Text, maybe_text_to_text


class ChatMessage:
    message: Text
    time: float

    def __init__(self, message: MaybeText, at: Optional[float] = None) -> None:
        if at is None:
            at = time.time()
        self.message = maybe_text_to_text(message)
        self.time = at
