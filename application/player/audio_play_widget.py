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

import ctypes
import io
from ctypes import POINTER, cast
from pathlib import Path

import mutagen
import pygame
from comtypes import CLSCTX_ALL
from gui.image_button import CustomButton
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from pydub import AudioSegment
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Button, Static
from textual_slider import Slider

from player.device import set_sounddevice

# Constants
DEVICE_SPEAKERS = 0  # Master audio device
VOLUME_MIN = 0
VOLUME_MAX = 65535
winmm = ctypes.WinDLL("winmm.dll")


def set_system_volume(level: float):
    """
    Set the system audio volume.

    :param level: Volume level as a float between 0.0 (mute) and 1.0 (max volume)
    """
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(level, None)


def get_system_volume():
    """
    Get the current system audio volume as a float between 0.0 and 1.0.

    :return: Current system volume as a float
    """
    # Get the default audio output device
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    # Get the volume level as a scalar (0.0 to 1.0)
    current_volume = volume.GetMasterVolumeLevelScalar()
    return current_volume


class AudioPlayerWidget(Container):
    """Custom ProgressBar to display time information."""

    MUSIC_END_EVENT = pygame.USEREVENT + 1

    class PositionChanged(Message):
        def __init__(self, value: str) -> None:
            self.value = value  # The value to communicate
            super().__init__()

    def __init__(self, cursor, playlist_provider, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_sounddevice()
        self.cursor = cursor
        self.is_paused = False
        self.song_length = 0  # Length of the song in seconds
        self.timer: Timer | None = None
        self.elapsed_time = 0
        self.time_display = Static("0:00 / 0:00", id="time-display")
        self.slider_progress = Slider(min=0, max=100, value=0, id="slider-progress")

        self.update_components = True
        self.task_ref = None
        self.vertical_container = Vertical()
        self.horizontal_container_button = Horizontal(
            classes="horizontal_container_top", id="horizontal_container_button"
        )
        self.horizontal_container_slider = Horizontal(
            classes="horizontal_container_top", id="horizontal_container_slider"
        )
        self.button_play = Button.success(
            "play", id="button-play", classes="audio_button"
        )
        self.button_stop = Button.error(
            "stop", id="button-stop", classes="audio_button"
        )
        self.button_back = Button.warning(
            "|<", id="button-back", classes="audio_button"
        )
        self.button_forward = Button.warning(
            ">|", id="button-forward", classes="audio_button"
        )

        self.button_stop.disabled = True
        self.button_play.disabled = True
        self.button_forward.disabled = True
        self.button_back.disabled = True
        self.playlist = []
        self.current_song = -1
        self.block_update = False
        self.playlist_provider = playlist_provider
        self.current_song_id = -1

    def on_new_playlist(self, value):
        playlist_provider = self.app.query_one(self.playlist_provider)
        self.playlist = []
        for audio_file in playlist_provider.get_playlist():
            self.add_audio_file(audio_file)

    def add_audio_file(self, audio_file=None, position="end"):
        if audio_file:
            audio_file_path = Path(audio_file[1])
            if audio_file_path.exists():
                if "end" in position:
                    self.playlist.append(audio_file)
                elif "top" in position:
                    self.playlist.insert(0, audio_file)
        if len(self.playlist) > 0 and not pygame.mixer.music.get_busy():
            self.button_play.disabled = False
            self.button_forward.disabled = False
            if self.current_song == -1:
                self.current_song = 0
                self.current_song_id = self.playlist[self.current_song][0]

    def update_time(self, current_seconds, total_seconds):
        """Update the time display."""
        current_time = f"{int(current_seconds // 60)}:{int(current_seconds % 60):02}"
        total_time = f"{int(total_seconds // 60)}:{int(total_seconds % 60):02}"
        self.time_display.update(
            f"{current_time}\n[{total_time}]\n{self.current_song+1}/{len(self.playlist)}"
        )

        if self.update_components:
            self.vertical_container.mount(self.horizontal_container_slider)
            self.horizontal_container_slider.mount(self.slider_progress)
            self.horizontal_container_slider.mount(self.time_display)
            self.update_components = False

    async def on_mount(self, event):
        self.mount(self.vertical_container)
        self.vertical_container.mount(self.horizontal_container_button)
        self.horizontal_container_button.mount(self.button_play)
        self.horizontal_container_button.mount(self.button_stop)
        self.horizontal_container_button.mount(self.button_back)
        self.horizontal_container_button.mount(self.button_forward)

    def render(self):
        """Render the progress bar with time information."""
        super().render()
        return ""

    def play_audio(self, action=None):

        pb_p = self.button_play
        pb_s = self.button_stop
        # if "play" in pb_p.get_mode():
        if "play" in pb_p.label:
            # Start playback if not playing
            pygame.mixer.music.set_endevent(self.MUSIC_END_EVENT)

            if str(self.playlist[self.current_song][1]).lower().endswith(".m4a"):
                audio = AudioSegment.from_file(
                    self.playlist[self.current_song][1], format="m4a"
                )
                mp3_data = io.BytesIO()
                audio.export(mp3_data, format="mp3")
                mp3_data.seek(0)  # Rewind the BytesIO stream
                pygame.mixer.music.load(mp3_data, "mp3")
            else:
                pygame.mixer.music.load(self.playlist[self.current_song][1])
            pygame.mixer.music.play()
            self.song_length = self.get_song_length()
            self.start_progress_timer()
            self.update_components = True
            # pb_p.set_mode_idx("pause")
            pb_p.label = "pause"
            pb_s.disabled = False
            self.is_paused = False

        # elif "pause" in pb_p.get_mode():
        elif "pause" in pb_p.label:
            pygame.mixer.music.pause()
            self.is_paused = True
            # pb_p.set_mode_idx("resume")
            pb_p.label = "resume"

        # elif "resume" in pb_p.get_mode():
        elif "resume" in pb_p.label:
            pygame.mixer.music.unpause()
            self.is_paused = False
            # pb_p.set_mode_idx("pause")
            pb_p.label = "pause"

    def remove_widgets(self):
        for widget in self.horizontal_container_slider.walk_children():
            widget.remove()
        self.horizontal_container_slider.remove()

    def stop_audio(self, remove_progress=True):
        pb_p = self.button_play
        pb_s = self.button_stop
        pygame.mixer.music.stop()
        pygame.event.clear()

        self.stop_progress_timer()
        self.reset_progress_bar()
        if remove_progress:
            self.remove_widgets()
        self.update_components = True

        pb_p.disabled = False
        # pb_p.set_mode_idx("play")
        pb_p.label = "play"
        pb_s.disabled = True
        self.is_paused = False
        self.slider_progress.value = 0

    def get_song_length(self):
        """Get the song length in seconds."""
        audio = mutagen.File(self.playlist[self.current_song][1])
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

            if abs(self.elapsed_time - new_pos_seconds) > 2:

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
                self.current_song += 1
                if len(self.playlist) > self.current_song:
                    self.post_message(self.PositionChanged(self.current_song))
                    self.stop_audio(remove_progress=False)
                    self.stop_progress_timer()

                    self.play_audio()
                else:
                    self.stop_audio(remove_progress=True)
                    self.stop_progress_timer()

    def on_position_changed(self, value: int):
        if int(value) >= 0 and int(value) < len(self.playlist):
            self.current_song = value
            if pygame.mixer.music.get_busy() or self.is_paused:
                self.stop_audio(remove_progress=False)
                self.stop_progress_timer()
                self.play_audio()
            else:
                self.play_audio()
        if self.current_song == 0:
            self.button_back.disabled = True

        elif self.current_song >= len(self.playlist) - 1:
            self.button_forward.disabled = True
        if self.current_song > 0 and self.current_song < len(self.playlist):
            self.button_back.disabled = False
        if self.current_song >= 0 and self.current_song < len(self.playlist) - 1:
            self.button_forward.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "button-play":
            self.play_audio()
        elif button_id == "button-stop":
            self.stop_audio()
        elif button_id == "button-back":
            self.current_song -= 1
            if self.current_song <= 0:
                self.current_song = 0
                self.button_back.disabled = True
            self.button_forward.disabled = False
            self.post_message(self.PositionChanged(self.current_song))
            if pygame.mixer.music.get_busy():
                self.stop_audio(remove_progress=False)
                self.stop_progress_timer()
                self.play_audio()
            if self.is_paused:
                self.stop_audio(remove_progress=False)
                self.stop_progress_timer()
        elif button_id == "button-forward":
            self.current_song += 1
            if self.current_song >= len(self.playlist) - 1:
                self.current_song = len(self.playlist) - 1
                self.button_forward.disabled = True
            self.button_back.disabled = False
            self.post_message(self.PositionChanged(self.current_song))
            if pygame.mixer.music.get_busy():
                self.stop_audio(remove_progress=False)
                self.stop_progress_timer()
                self.play_audio()
            if self.is_paused:
                self.stop_audio(remove_progress=False)
                self.stop_progress_timer()


class AudioPlayerApp(App):

    def __init__(self):
        super().__init__()
        self.apw = AudioPlayerWidget(id="progress", cursor=None)

    def add_song(self, audio_file):
        self.apw.add_audio_file(audio_file=audio_file)

    def compose(self) -> ComposeResult:
        yield Static("Audio Player", id="title")
        yield self.apw


if __name__ == "__main__":
    pygame.init()
    audio_file_path = "c:/temp/test.flac"  # Replace with the path to your audio file
    app = AudioPlayerApp()
    app.add_song(audio_file_path)
    app.run()
