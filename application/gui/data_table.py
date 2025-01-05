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

import time

from database.database_helper import execute_query
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
        self.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):

        self.post_message(self.PositionChanged(event.cursor_row))

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

    class PositionChanged(Message):
        def __init__(self, value: str) -> None:
            self.value = value  # The value to communicate
            super().__init__()

    class PlaylistChanged(Message):
        def __init__(self, value: str) -> None:
            self.value = value  # The value to communicate
            super().__init__()

    def __init__(self, cursor, log_controller: LogController, **kwargs):
        super().__init__(**kwargs)
        self.cursor = cursor
        self.header = [
            ("ID", 5),
            ("Tracknumber", 5),
            ("Title", 40),
            ("Length", 5),
            ("Album", 40),
            ("Artist", 40),
            ("Date", 10),
        ]
        for col in self.header:
            self.add_column(col[0], key=col[0].lower(), width=col[1])
        self.log_controller = log_controller
        self.current_sorts: set = set()
        self.cursor_type = "row"
        self.last_click_time = 0  # Track the time of the last mouse click
        self.double_click_threshold = 0.3
        self.playlist = []

    def clear_table(self):
        self.clear()
        self.playlist = []

    def add_track(
        self,
        track_id: int,
        track_number: str,
        title: str,
        length: str,
        artist: str,
        album: str,
        release_date: str,
        path: str,
    ):
        if release_date:
            release_date = str(release_date).rstrip("-")
        """Add a track to the playlist."""
        self.add_row(
            str(track_id),
            track_number,
            title,
            length,
            album,
            artist,
            release_date,
            key=f"{track_id}",
        )

    def insert_tracks_finished(self):
        self.post_message(self.PlaylistChanged("new"))

    def sort_reverse(self, sort_type: str):
        """Determine if `sort_type` is ascending or descending."""
        reverse = sort_type in self.current_sorts
        if reverse:
            self.current_sorts.remove(sort_type)
        else:
            self.current_sorts.add(sort_type)
        return reverse

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected):

        col = event.column_index
        key = self.header[col][0].lower()

        self.sort(
            key,
            reverse=self.sort_reverse(key),
        )
        self.post_message(self.PlaylistChanged("sorted"))

    def on_position_changed(self, value: int):
        self.cursor_coordinate = Coordinate(value, 0)
        self.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):

        self.post_message(self.PositionChanged(event.cursor_row))

    def on_mouse_down(self, event: MouseDown):
        """Handle mouse events and detect double-clicks."""

        current_time = time.time()
        time_since_last_click = current_time - self.last_click_time

        if event.button == 1:
            if time_since_last_click <= self.double_click_threshold:
                cursor_row = self.cursor_row
                self.post_message(self.PositionChanged(cursor_row))
            self.last_click_time = current_time

    def get_playlist(self):
        playlist = []

        for row in self.rows:
            path = get_audio_path_from_track_id(self.cursor, row.value)
            playlist.append((row.value, path))
        return playlist

    def is_in_playlist(self, id):
        for row in self.rows:
            if row.value == id:
                return True
        return False
