from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Static, ProgressBar
import pygame
from textual.timer import Timer
import mutagen


class TimeProgressBar(ProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pos_percentage = -1

    def on_click(self, event):
        widget_region = self.region  # A Region object
        x_position = widget_region.x  # X-coordinate of the widget
        width = self.size.width
        if event.x < (width - 7) - x_position:
            self.pos_percentage = (event.x - x_position) * 100 / (width - 7)
            self.advance(self.pos_percentage)


class PlayerProgressBar(Horizontal):
    """Custom ProgressBar to display time information."""

    def __init__(self, audio_file, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_file = audio_file
        self.is_paused = False
        self.song_length = 0  # Length of the song in seconds
        self.timer: Timer | None = None
        self.elapsed_time = 0
        pygame.mixer.init()
        self.time_display = Static("0:00 / 0:00", id="time-display")
        self.progressbar = TimeProgressBar(
            total=100, show_eta=False, show_percentage=False
        )
        if self.is_mounted:
            self.mount(self.progressbar)
            self.mount(self.time_display)  # Add the Static widget as a child
        self.show_eta = False
        self.show_percentage = False

    def update_time(self, current_seconds, total_seconds):
        """Update the time display."""
        current_time = f"{int(current_seconds // 60)}:{int(current_seconds % 60):02}"
        total_time = f"{int(total_seconds // 60)}:{int(total_seconds % 60):02}"
        self.time_display.update(f" {current_time} / {total_time}")
        self.mount(self.progressbar)
        self.mount(self.time_display)

    def render(self):
        """Render the progress bar with time information."""
        # progress_text = f"{self.current_time} / {self.total_time}"
        super().render()
        return ""

    def play_audio(self):
        if self.is_paused:
            # Resume playback if paused
            pygame.mixer.music.unpause()
            self.is_paused = False
            # self.query_one("#title").update("Resumed...")
        elif not pygame.mixer.music.get_busy():
            # Start playback if not playing
            pygame.mixer.music.load(self.audio_file)
            pygame.mixer.music.play()
            self.song_length = self.get_song_length()
            self.start_progress_timer()
            # self.query_one("#title").update("Playing...")

    def pause_audio(self):
        if pygame.mixer.music.get_busy() and not self.is_paused:
            # Pause playback
            pygame.mixer.music.pause()
            self.is_paused = True
            # self.query_one("#title").update("Paused...")
            self.stop_progress_timer()

    def stop_audio(self):
        if pygame.mixer.music.get_busy() or self.is_paused:
            # Stop playback
            pygame.mixer.music.stop()
            self.is_paused = False
            # self.query_one("#title").update("Stopped...")
            self.stop_progress_timer()
            self.reset_progress_bar()

    def get_song_length(self):
        """Get the song length in seconds."""
        audio = mutagen.File(self.audio_file)
        if audio and hasattr(audio.info, "length"):
            return audio.info.length  # Length in seconds
        else:
            self.query_one("#title").update("Could not determine song length")
            return 0

    def start_progress_timer(self):
        """Start the timer to update progress."""
        if self.timer:
            self.timer.stop()
        self.timer = self.progressbar.set_interval(1, self.update_progress)

    def stop_progress_timer(self):
        """Stop the progress update timer."""
        if self.timer:
            self.timer.stop()

    def reset_progress_bar(self):
        """Reset the progress bar to 0."""
        self.progress = 0
        self.elapsed_time = 0
        self.update_time(0, self.song_length)

    def update_progress(self):
        """Update the progress bar based on the current playback position."""
        if pygame.mixer.music.get_busy():
            self.elapsed_time += 1
            current_pos = (
                pygame.mixer.music.get_pos() / 1000
            )  # Current position in seconds
            progress_percentage = (
                (current_pos / self.song_length) * 100 if self.song_length > 0 else 0
            )
            self.progressbar.advance(progress_percentage)
            self.update_time(self.elapsed_time, self.song_length)
            if progress_percentage >= 100:
                self.stop_progress_timer()

    def on_click(self, event):
        if self.song_length > 0:
            # Calculate the clicked position as a percentage
            if (
                self.progressbar.pos_percentage > 0
                and self.progressbar.pos_percentage < 100
            ):
                percentage = self.progressbar.pos_percentage

                new_pos_seconds = (percentage / 100) * self.song_length
                self.elapsed_time = new_pos_seconds
                pygame.mixer.music.set_pos(new_pos_seconds)
                # self.query_one("#title").update(f"Seeked to {int(new_pos_seconds)} seconds")
                self.progressbar.progress = percentage
                self.update_progress()
                self.update_time(new_pos_seconds, self.song_length)


class AudioPlayerApp(App):
    CSS = """
    Screen {
        align: center middle;
    }
    Button {
        margin: 1;
    }
    TimeProgressBar {
        width: 20%;
        height: 3; /* Thicker progress bar */
        margin-top: 1;
    }
    """

    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file

    def compose(self) -> ComposeResult:
        yield Static("Audio Player", id="title")
        yield Vertical(
            Button("Play", id="play"),
            Button("Pause", id="pause"),
            Button("Stop", id="stop"),
            id="controls",
        )
        yield PlayerProgressBar(id="progress", audio_file=self.audio_file)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        progressbar = self.query_one("#progress")

        if button_id == "play":
            progressbar.play_audio()
        elif button_id == "pause":
            progressbar.pause_audio()
        elif button_id == "stop":
            progressbar.stop_audio()


if __name__ == "__main__":
    audio_file_path = (
        "/mnt/c/temp/test.flac"  # Replace with the path to your audio file
    )
    app = AudioPlayerApp(audio_file_path)
    app.run()
