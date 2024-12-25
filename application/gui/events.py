from textual.message import Message
from textual.widget import Widget


class CustomClickEvent(Message):
    def __init__(
        self, sender: Widget, description: str, genre: str, lower: float, upper: float
    ) -> None:
        super().__init__()  # Call parent class constructor
        self.sender = sender
        self.description = description
        self.lower = lower
        self.upper = upper
        self.genre = genre
