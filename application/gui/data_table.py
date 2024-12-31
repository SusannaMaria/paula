import sqlite3
import time

from database.database_helper import close_cursor, create_cursor, execute_query
from textual import on
from textual.coordinate import Coordinate
from textual.events import MouseDown
from textual.message import Message
from textual.widgets import DataTable
from updater.updater_main import get_audio_path_from_track_id

from gui.log_controller import LogController


class TrackTableWidget(DataTable):
    """A widget to display tracks of a selected album."""

    def __init__(self, log_controller: LogController, **kwargs):
        super().__init__(**kwargs)
        self.add_column("Track Number", width=10)
        self.add_column("Title", width=40)
        self.log_controller = log_controller
        self.cursor_type = "row"
        self.last_click_time = 0  # Track the time of the last mouse click
        self.double_click_threshold = 0.3

        # Broadcast the message to all widgets

    class PositionChanged(Message):
        def __init__(self, value: str) -> None:
            self.value = value  # The value to communicate
            super().__init__()

    def on_position_changed(self, value: int):
        self.cursor_coordinate = Coordinate(value, 0)

    def on_mouse_down(self, event: MouseDown):
        """Handle mouse events and detect double-clicks."""

        current_time = time.time()
        time_since_last_click = current_time - self.last_click_time

        if event.button == 1:
            # if time_since_last_click <= self.double_click_threshold:
            # Detected a double-click
            cursor_row = self.cursor_row
            # row_data = self.get_row_at(cursor_row)
            # row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
            # row_key.value
            self.post_message(self.PositionChanged(cursor_row))
            self.last_click_time = current_time

    def populate_tracks(self, cursor, album_id: int):
        """Populate the table with tracks for the given album."""
        self.clear()  # Clear existing tracks

        self.log_controller.write(f"Populating tracks for album ID: {album_id}")

        tracks = execute_query(
            cursor,
            "SELECT track_id, track_number, title FROM tracks WHERE album_id = ? ORDER BY CAST(SUBSTR(track_number, 1, INSTR(track_number, '/') - 1) AS INTEGER);",
            (album_id,),
            fetch_one=False,
            fetch_all=True,
        )
        playlist = []
        for track_id, track_number, title in tracks:
            self.add_row(
                str(track_number),
                title.replace("[", r"\["),
                key=f"{track_id}",
            )
            path = get_audio_path_from_track_id(cursor, track_id)
            playlist.append(path)

        if len(playlist) > 0:
            audio_player = self.app.query_one("#audio-player")
            audio_player.add_playlist(playlist)


class PlaylistWidget(DataTable):
    """A widget to display the playlist."""

    def __init__(self, log_controller: LogController, **kwargs):
        super().__init__(**kwargs)
        self.add_column("ID", width=5)
        self.add_column("Title", width=30)
        self.add_column("Artist", width=30)
        self.add_column("Album", width=30)
        self.log_controller = log_controller

    def clear_table(self):
        self.clear()

    def add_track(self, track_id: int, title: str, artist: str, album: str):
        """Add a track to the playlist."""
        self.add_row(str(track_id), title, artist, album)
