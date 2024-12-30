import asyncio
import math
import threading
import time
from typing import List
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Static, ProgressBar, Sparkline
import pygame
from textual.timer import Timer
import mutagen
from textual_slider import Slider
from textual import on
from pydub import AudioSegment
from statistics import mean


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
        self.task_running = False
        self.visu = False
        self.task_thread = threading.Thread(target=self.parallel_task, daemon=True)
        pygame.mixer.init()
        self.visu_sparkline = Sparkline(id="visu-sparkline", summary_function=max)
        self.time_display = Static("0:00 / 0:00", id="time-display")
        self.slider_progress = Slider(min=0, max=100, value=0, id="slider-progress")
        self.update_components = True
        self.task_ref = None
        self.vertical_container = Vertical()
        self.horizontal_container = Horizontal()
        self.task_visu = None

    async def parallel_task(self):
        """The background task."""
        audio = AudioSegment.from_file(self.audio_file)
        data = audio.get_array_of_samples()[0::2]
        frame_rate = audio.frame_rate
        max_amp = audio.max_possible_amplitude
        width = 60
        fps = 30
        height = 32
        sync = True
        length, point_interval, last_frame_length, interval, divisor = (
            calc_data_for_visualization(data, frame_rate, max_amp, width, fps, height)
        )
        skipped_frames = 0
        audio_start = time.time()

        for i, f in enumerate(
            graph_frames_from_audio(data, point_interval, width, divisor)
        ):
            if not self.task_running:
                break
            # await self.pause_event.wait()
            self.visu_sparkline.data = f
            # print_frame(f, height, print_char)
            frame_length = (
                last_frame_length if i == length - 1 else 1
            )  # 1 denotes full frame
            end_time = audio_start + (
                (i + 1 * frame_length) * interval
            )  # time at which we should print next frame
            sleep_for = end_time - time.time()
            if sync and sleep_for > 0:

                await asyncio.sleep(sleep_for)
                # time.sleep(sleep_for)  # sleep till next frame
            else:
                skipped_frames += 1

    def update_time(self, current_seconds, total_seconds):
        """Update the time display."""
        current_time = f"{int(current_seconds // 60)}:{int(current_seconds % 60):02}"
        total_time = f"{int(total_seconds // 60)}:{int(total_seconds % 60):02}"
        self.time_display.update(f" {current_time} / {total_time}")

        if self.update_components:
            self.mount(self.vertical_container)
            self.vertical_container.mount(self.visu_sparkline)
            self.vertical_container.mount(self.horizontal_container)
            self.horizontal_container.mount(self.slider_progress)
            self.horizontal_container.mount(self.time_display)
            self.update_components = False

    def render(self):
        """Render the progress bar with time information."""
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
            self.update_components = True
            pb_p.label = "pause"
            pb_s.disabled = False
            self.is_paused = False
            self.visu = True
            self.task_visu = asyncio.create_task(self.parallel_task())
            self.task_running = True

        elif "pause" in pb_p.label:
            pygame.mixer.music.pause()
            self.is_paused = True
            pb_p.label = "resume"
            self.task_running = False

        elif "resume" in pb_p.label:
            pygame.mixer.music.unpause()
            self.is_paused = False
            pb_p.label = "pause"
            self.task_running = True

    def remove_widgets(self):
        self.slider_progress.remove()
        self.time_display.remove()
        for widget in self.vertical_container.walk_children():
            widget.remove()
        self.vertical_container.remove()

    def stop_audio(self):
        pb_p = self.app.query_one("#button-play")
        pb_s = self.app.query_one("#button-stop")

        pygame.mixer.music.stop()
        pygame.event.clear()

        self.stop_progress_timer()
        self.reset_progress_bar()

        self.remove_widgets()
        self.update_components = True

        pb_p.disabled = False
        pb_p.label = "play"
        pb_s.disabled = True
        self.is_paused = False
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


def graph_frames_from_audio(data, step, width, divisor):
    """
    Interpolates values in data list by taking an average of step values.
    After processing width * step values will yield a list of width
    interpolated values.
    Once the data array has been processed yields final list of the remaining
    values if there are any.

    :param data: array of numbers representing audio data
    :param step: number of values to use for interpolation
    :param width: width of frame, number of interpolated values
    :param divisor: divide each value with this number
    :return: generator yielding a current frame
    """
    point = 0
    current_sum = 0
    current_frame = []
    for x in data:
        current_sum += int((abs(x) // divisor))
        point += 1
        if point == step:
            current_frame.append(math.ceil(current_sum / point))
            point = 0
            current_sum = 0
        if len(current_frame) == width:
            yield current_frame
            current_frame = []
    if current_frame:
        yield current_frame
    elif current_sum:
        yield [current_sum / point]


def calc_data_for_visualization(
    data: List[float],
    frame_rate: int,
    max_amp: float,
    width: int,
    fps: int,
    height: int,
):
    """
    Calculates all the data we need to visualize audio stream
    """
    length = len(data)
    point_interval = frame_rate // (width * fps)  # interval used for interpolation
    if point_interval == 0:
        return
    frame_mod = length % (point_interval * width)
    last_frame_length = (
        frame_rate / (length % (point_interval * width)) if frame_mod != 0 else 1
    )
    interval = 1.0 / fps
    divisor = max_amp / height
    return length, point_interval, last_frame_length, interval, divisor


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
