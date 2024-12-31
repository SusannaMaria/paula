import logging
import sqlite3
from typing import Iterable

from database.database_helper import (
    close_connection,
    create_cursor,
    get_cover_by_album_id,
    get_track_by_id,
    get_tracks_between_by_genre,
)
from player.audio_play_widget import AudioPlayerWidget
from textual import on
from textual.app import ComposeResult, SystemCommand
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.css.scalar import Scalar
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Label,
    Log,
    Placeholder,
)
from textual_image.widget import HalfcellImage, SixelImage, TGPImage, UnicodeImage
from textual_image.widget import Image as AutoImage

from gui.data_table import PlaylistWidget, TrackTableWidget
from gui.events import CustomClickEvent
from gui.log_controller import LogController
from gui.music_database_widget import MusicDatabaseWidget

TEST_IMAGE = r"c:/temp/cover_d.jpg"

RENDERING_METHODS = {
    "auto": AutoImage,
    "tgp": TGPImage,
    "sixel": SixelImage,
    "halfcell": HalfcellImage,
    "unicode": UnicodeImage,
}


class SettingsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Placeholder("Settings Screen")
        yield Footer()


class HelpScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Placeholder("Help Screen")
        yield Footer()


class LogScreen(Screen):
    """Screen to display the log."""

    BINDINGS = [
        ("q", "do_close", "Close the logging"),
    ]

    def action_do_close(self) -> None:
        self.app.pop_screen()
        self.log_controller.set_log_widget(None)  # Detach the widget

    def __init__(self, log_controller: LogController) -> None:
        super().__init__()
        self.log_controller = log_controller

    def compose(self) -> ComposeResult:
        log_widget = Log(classes="log-widget")
        self.log_controller.set_log_widget(log_widget)  # Set the log widget
        yield Container(log_widget)
        yield Footer()


class QuitScreen(ModalScreen[bool]):
    """Screen with a dialog to quit."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to quit?", id="question"),
            Button("Quit", variant="error", id="quit"),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.dismiss(True)
        else:
            self.dismiss(False)


class PaulaScreen(Screen):

    BINDINGS = [
        ("d", "switch_mode('dashboard')", "Dashboard"),
        ("s", "switch_mode('settings')", "Settings"),
        ("h", "switch_mode('help')", "Help"),
        ("q", "request_quit", "Quit the app"),
        ("l", "show_log", "Show the log"),
    ]

    def __init__(self, log_controller: LogController) -> None:
        super().__init__()
        self.cursor = create_cursor()
        self.log_controller = log_controller
        self.audio_player = AudioPlayerWidget(cursor=self.cursor, id="audio-player")

    def update_image(self, image_path):
        image_widget = self.query_one("#cover-image")
        image_widget.image = image_path

    def action_show_log(self) -> None:
        """Action to display the quit dialog."""
        self.app.push_screen(LogScreen(self.log_controller))

    def action_request_quit(self) -> None:
        """Action to display the quit dialog."""

        def check_quit(quit: bool | None) -> None:
            """Called when QuitScreen is dismissed."""
            if quit:
                self.app.exit()

        self.app.push_screen(QuitScreen(), check_quit)

    def on_custom_click_event(self, event: CustomClickEvent) -> None:

        self.log_controller.write(
            f"{event.description} - {event.genre} - {event.lower} - {event.upper}"
        )
        tracks = get_tracks_between_by_genre(
            self.cursor, event.genre, event.lower, event.upper
        )

        plt = self.query_one("#playlist_table")
        plt.clear_table()
        for track in tracks:
            track_row = get_track_by_id(self.cursor, track)

            plt.add_track(
                track_row[0],
                track_row[1],
                track_row[2],
                track_row[3],
            )

        self.log_controller.write(f"{len(tracks)}")
        close_connection()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand("Bell", "Ring the bell", self.bell)

    def on_album_selected(self, album_id: int):
        """Handle album selection event."""
        # Fetch the album cover path from the database (replace this with actual logic)
        image_path = "/mnt/c/temp/cover.jpg"

        old_widget = self.query_one("#image_widget")
        logging.info(old_widget)

        Image = RENDERING_METHODS["halfcell"]
        new_image_widget = Image(image_path, id="image_widget")
        yield new_image_widget

    def compose(self) -> ComposeResult:
        """Compose the UI with a horizontal layout."""

        with Horizontal():
            music_db = MusicDatabaseWidget(
                cursor=self.cursor,
                on_album_selected=self.show_album_tracks,
                id="music_panel",
                log_controller=self.log_controller,
            )
            yield music_db
            with Vertical(id="tracklist"):
                yield self.audio_player
                track_table = TrackTableWidget(
                    id="track_table", log_controller=self.log_controller
                )
                yield track_table

                playlist = PlaylistWidget(
                    id="playlist_table", log_controller=self.log_controller
                )
                self.track_table = track_table  # Store reference for updates
                yield playlist

            with Vertical(id="metadata"):
                Image = RENDERING_METHODS["auto"]
                image_widget = Image(TEST_IMAGE, id="cover-image")
                image_widget.styles.width = Scalar.parse("26")
                image_widget.styles.height = Scalar.parse("14")
                image_widget.styles.align = ("right", "top")
                image_widget.styles.padding = 0
                image_widget.styles.margin = 0
                # yield Container(self.image_container)
                yield image_widget
        yield Footer()

    def show_album_tracks(self, album_id: int):
        global TEST_IMAGE
        """Show tracks for the selected album."""
        self.track_table.populate_tracks(self.cursor, album_id)
        cover_path = get_cover_by_album_id(self.cursor, album_id)
        if cover_path:
            self.update_image(cover_path)

    @on(AudioPlayerWidget.PositionChanged)
    def on_audio_player_postion_changed(
        self, message: AudioPlayerWidget.PositionChanged
    ) -> None:
        # Broadcast the message to all widgets
        self.query_one(TrackTableWidget).on_position_changed(message.value)

    @on(TrackTableWidget.PositionChanged)
    def on_track_table_postion_changed(
        self, message: TrackTableWidget.PositionChanged
    ) -> None:
        # Broadcast the message to all widgets
        self.query_one(AudioPlayerWidget).on_position_changed(message.value)
