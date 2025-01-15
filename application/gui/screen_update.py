from textual.message import Message


class ScreenUpdate(Message):
    def __init__(
        self,
        total: int = None,
        progress: int = None,
        loss: float = None,
        status: str = None,
    ):
        self.total = total
        self.progress = progress
        self.loss = loss
        self.status = status
        super().__init__()


class TrainComplete(Message):
    def __init__(self, message: str):
        self.message = message
        super().__init__()
