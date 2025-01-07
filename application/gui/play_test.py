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

import threading
import time

from pygame import mixer
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import ProgressBar, Static


class AudioPlayerApp(App):
    CSS = """
    Screen {
        align: center middle;
    }

    Container {
        width: 60%;
    }

    ProgressBar {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(self, audio_file: str):
        super().__init__()
        self.audio_file = audio_file
        self.audio_length = 0
        self.is_playing = False
        self.progress_bar = None

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Playing Audio File", id="title"),
            ProgressBar(total=100, show_percentage=True, id="progress"),
        )

    def on_mount(self) -> None:
        self.progress_bar = self.query_one("#progress", ProgressBar)

        # Start audio playback in a separate thread
        playback_thread = threading.Thread(target=self.play_audio, daemon=True)
        playback_thread.start()

        # Start updating the progress bar
        self.set_interval(0.5, self.update_progress)

    def play_audio(self):
        """Play the audio file and initialize the mixer."""
        mixer.init()
        mixer.music.load(self.audio_file)
        mixer.music.play()
        self.audio_length = mixer.Sound(self.audio_file).get_length()
        self.is_playing = True

        # Wait for the audio to finish
        time.sleep(self.audio_length)
        self.is_playing = False

    def update_progress(self):
        """Update the progress bar based on playback progress."""
        if self.is_playing:
            current_position = mixer.music.get_pos() / 1000  # Convert to seconds
            percentage = (current_position / self.audio_length) * 100
            self.progress_bar.progress = percentage
        else:
            self.progress_bar.progress = 100  # Ensure bar is full when playback ends


# Run the application
if __name__ == "__main__":
    audio_file_path = r"c:\temp\test2.flac"
    app = AudioPlayerApp(audio_file_path)
    app.run()
