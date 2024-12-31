from textual.widget import Widget


class LogController:
    """Centralized log controller to manage log messages."""

    def __init__(self) -> None:
        self.messages = []
        self.log_widget = None

    def set_log_widget(self, log_widget: Widget) -> None:
        """Set the active log widget to update."""
        self.log_widget = log_widget
        self.refresh_log_widget()

    def write(self, message: str) -> None:
        """Add a message to the log and update the widget."""
        self.messages.append(message)
        if self.log_widget:
            self.log_widget.write(message)

    def refresh_log_widget(self) -> None:
        """Refresh the current log widget with all messages."""
        if self.log_widget:
            self.log_widget.clear()
            for message in self.messages:
                self.log_widget.write(f"{message}\n")
