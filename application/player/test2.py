import pyglet
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Static, ProgressBar
from textual.timer import Timer
import sounddevice as sd


class AudioPlayerWithDeviceControl:
    def __init__(self, audio_file):
        self.audio_file = audio_file
        self.player = pyglet.media.Player()
        self.source = pyglet.media.load(audio_file)
        self.player.queue(self.source)

    def list_devices(self):
        """List all available audio devices."""
        devices = sd.query_devices()
        for idx, device in enumerate(devices):
            print(f"{idx}: {device['name']}")

    def play(self):
        """Play the audio file."""
        print(
            f"Playing on default device: {sd.query_devices(sd.default.device, 'output')['name']}"
        )
        self.player.play()

    def switch_device(self, device_index):
        """Switch to a specific audio device."""
        devices = sd.query_devices()
        print(devices)
        if 0 <= device_index < len(devices):
            sd.default.device = device_index
            print(f"Switched to device: {devices[device_index]['name']}")
        else:
            print("Invalid device index")


class AudioPlayerApp(App):
    CSS = """
    Screen {
        align: center middle;
    }
    Button {
        margin: 1;
    }
    ProgressBar {
        width: 80%;
        height: 2; /* Thicker progress bar */
        margin-top: 1;
    }
    """

    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file
        self.player = pyglet.media.Player()
        self.source = pyglet.media.load(audio_file)
        self.player.queue(self.source)
        self.player.volume = 0.5  # Set initial volume to 50%
        self.timer: Timer | None = None
        self.total_duration = self.source.duration  # Duration of the audio in seconds

    def compose(self) -> ComposeResult:
        yield Static("Audio Player", id="title")
        yield Vertical(
            Button("Play", id="play"),
            Button("Pause", id="pause"),
            Button("Stop", id="stop"),
            Button("Volume Up", id="volume_up"),
            Button("Volume Down", id="volume_down"),
            id="controls",
        )
        yield ProgressBar(total=100, id="progress")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "play":
            self.play_audio()
        elif button_id == "pause":
            self.pause_audio()
        elif button_id == "stop":
            self.stop_audio()
        elif button_id == "volume_up":
            self.change_volume(0.1)
        elif button_id == "volume_down":
            self.change_volume(-0.1)

    def play_audio(self):
        """Play or resume the audio."""
        if not self.player.playing:
            self.player.play()
            self.query_one("#title").update(
                f"Playing... Volume: {int(self.player.volume * 100)}%"
            )
            self.start_progress_timer()

    def pause_audio(self):
        """Pause the audio."""
        if self.player.playing:
            self.player.pause()
            self.query_one("#title").update("Paused...")
            self.stop_progress_timer()

    def stop_audio(self):
        """Stop the audio."""
        if self.player.playing or self.player.time > 0:
            self.player.pause()
            self.player.seek(0)  # Reset to the beginning
            self.query_one("#title").update("Stopped...")
            self.stop_progress_timer()
            self.reset_progress_bar()

    def change_volume(self, delta):
        """Change the volume by the given delta."""
        new_volume = self.player.volume + delta
        self.player.volume = max(
            0.0, min(1.0, new_volume)
        )  # Clamp volume between 0.0 and 1.0
        self.query_one("#title").update(f"Volume: {int(self.player.volume * 100)}%")

    def start_progress_timer(self):
        """Start a timer to update the progress bar."""
        if self.timer:
            self.timer.stop()
        self.timer = self.set_interval(0.5, self.update_progress)

    def stop_progress_timer(self):
        """Stop the progress update timer."""
        if self.timer:
            self.timer.stop()

    def reset_progress_bar(self):
        """Reset the progress bar to 0."""
        progress_bar = self.query_one("#progress")
        progress_bar.progress = 0

    def update_progress(self):
        """Update the progress bar based on the current playback position."""
        current_time = self.player.time  # Current playback time in seconds
        progress_percentage = (current_time / self.total_duration) * 100
        progress_bar = self.query_one("#progress")
        progress_bar.progress = progress_percentage
        self.query_one("#title").update(
            f"Playing: {int(current_time // 60)}:{int(current_time % 60):02} / "
            f"{int(self.total_duration // 60)}:{int(self.total_duration % 60):02} | "
            f"Volume: {int(self.player.volume * 100)}%"
        )
        if current_time >= self.total_duration:
            self.stop_audio()  # Stop playback when the song ends


if __name__ == "__main__":
    audio_file_path = "/mnt/c/temp/test.flac"  # Replace with your FLAC file path

    device_control = AudioPlayerWithDeviceControl(audio_file_path)

    # List all available devices
    print("Available audio devices:")
    device_control.list_devices()

    # Switch to a specific device (e.g., index 1)
    device_index = int(input("Enter device index to use: "))
    device_control.switch_device(device_index)
    app = AudioPlayerApp(audio_file_path)
    app.run()
