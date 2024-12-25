from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import ProgressBar, Static
from pygame import mixer
import time
import threading


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
