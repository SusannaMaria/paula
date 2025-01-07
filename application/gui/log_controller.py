"""
    Title: Music Collection Manager
    Description: A Python application to manage and enhance a personal music collection.
    Author: Susanna
    License: MIT License
    Created: 2025

    Copyright (c) 2025 Susanna Maria Hepp

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
"""

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
