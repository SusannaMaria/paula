from database.database_helper import close_cursor, create_cursor, execute_query
from updater.updater_main import get_audio_path_from_track_id
from gui.log_controller import LogController
from textual.widgets import DataTable

import sqlite3


class TrackTableWidget(DataTable):
    """A widget to display tracks of a selected album."""

    def __init__(self, log_controller: LogController, **kwargs):
        super().__init__(**kwargs)
        self.add_column("Track Number", width=10)
        self.add_column("Title", width=40)
        self.log_controller = log_controller

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
            self.add_row(str(track_number), title.replace("[", r"\["))
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
