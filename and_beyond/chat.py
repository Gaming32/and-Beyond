import time


class ChatMessage:
    message: str
    time: float

    def __init__(self, message: str, at: float = None) -> None:
        if at is None:
            at = time.time()
        self.message = message
        self.time = at
