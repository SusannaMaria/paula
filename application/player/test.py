from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Static, ProgressBar
import pygame
from textual.timer import Timer
import mutagen
from textual_slider import Slider
from textual import on


class PlayerProgressBar(Horizontal):
    """Custom ProgressBar to display time information."""

    MUSIC_END_EVENT = pygame.USEREVENT + 1

    def __init__(self, audio_file, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_file = audio_file
        self.is_paused = False
        self.song_length = 0  # Length of the song in seconds
        self.timer: Timer | None = None
        self.elapsed_time = 0
        pygame.mixer.init()
        self.time_display = Static("0:00 / 0:00", id="time-display")
        self.slider_progress = Slider(min=0, max=100, value=0, id="slider-progress")
        if self.is_mounted:
            self.mount(self.slider_progress)
            self.mount(self.time_display)  # Add the Static widget as a child

    def update_time(self, current_seconds, total_seconds):
        """Update the time display."""
        current_time = f"{int(current_seconds // 60)}:{int(current_seconds % 60):02}"
        total_time = f"{int(total_seconds // 60)}:{int(total_seconds % 60):02}"
        self.time_display.update(f" {current_time} / {total_time}")
        self.mount(self.slider_progress)
        self.mount(self.time_display)

    def render(self):
        """Render the progress bar with time information."""
        # progress_text = f"{self.current_time} / {self.total_time}"
        super().render()
        return ""

    def play_audio(self):

        pb_p = self.app.query_one("#button-play")
        pb_s = self.app.query_one("#button-stop")

        if "play" in pb_p.label:
            # Start playback if not playing
            pygame.mixer.music.set_endevent(self.MUSIC_END_EVENT)
            pygame.mixer.music.load(self.audio_file)
            pygame.mixer.music.play()
            self.song_length = self.get_song_length()
            self.start_progress_timer()
            self.mount(self.slider_progress)
            self.mount(self.time_display)
            pb_p.label = "pause"
            pb_s.disabled = False
            self.is_paused = False

        elif "pause" in pb_p.label:
            pygame.mixer.music.pause()
            self.is_paused = True
            pb_p.label = "resume"
        elif "resume" in pb_p.label:
            pygame.mixer.music.unpause()
            self.is_paused = False
            pb_p.label = "pause"

    def stop_audio(self):
        # if pygame.mixer.music.get_busy() or self.is_paused:
        # Stop playback
        pygame.mixer.music.stop()
        self.is_paused = False
        self.stop_progress_timer()
        self.reset_progress_bar()
        self.slider_progress.remove()
        self.time_display.remove()
        pb = self.app.query_one("#button-play")
        pb.disabled = False
        pb.label = "play"
        pb = self.app.query_one("#button-stop")
        pb.disabled = True
        self.slider_progress.value = 0

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
            self.elapsed_time = 0
        self.timer = self.slider_progress.set_interval(1, self.update_progress)

    def stop_progress_timer(self):
        """Stop the progress update timer."""
        if self.timer:
            self.elapsed_time = 0
            self.timer.stop()

    def reset_progress_bar(self):
        """Reset the progress bar to 0."""
        self.progress = 0
        self.elapsed_time = 0
        self.update_time(0, self.song_length)

    @on(Slider.Changed, "#slider-progress")
    def on_slider_changed_normal_amp(self, event: Slider.Changed) -> None:
        if pygame.mixer.music.get_busy() or self.is_paused:
            percentage = event.value

            new_pos_seconds = (percentage / 100) * self.song_length
            self.elapsed_time = new_pos_seconds
            pygame.mixer.music.set_pos(new_pos_seconds)
            if self.is_paused:
                self.update_time(new_pos_seconds, self.song_length)

    def update_progress(self):
        """Update the progress bar based on the current playback position."""
        if pygame.mixer.music.get_busy() and not self.is_paused:
            self.elapsed_time += 1
            progress_percentage = (
                (self.elapsed_time / self.song_length) * 100
                if self.song_length > 0
                else 0
            )
            self.slider_progress.value = progress_percentage
            self.update_time(self.elapsed_time, self.song_length)

        for event in pygame.event.get():
            if event.type == self.MUSIC_END_EVENT:
                self.stop_audio()
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
            Button.success("play", id="button-play"),
            Button.error("stop", id="button-stop"),
            id="controls",
        )
        yield PlayerProgressBar(id="progress", audio_file=self.audio_file)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        progressbar = self.query_one("#progress")

        if button_id == "button-play":
            progressbar.play_audio()
        elif button_id == "button-stop":
            progressbar.stop_audio()


if __name__ == "__main__":
    pygame.init()
    audio_file_path = (
        "/mnt/c/temp/test.flac"  # Replace with the path to your audio file
    )
    app = AudioPlayerApp(audio_file_path)
    app.run()
