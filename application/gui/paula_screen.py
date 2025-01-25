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

import logging
from typing import Iterable

from database.database_helper import (
    close_connection,
    create_cursor,
    get_cover_by_album_id,
    get_track_by_id,
    get_tracks_between_by_genre,
)
from player.audio_play_widget import (
    AudioPlayerWidget,
    get_system_volume,
    set_system_volume,
)
from textual import on
from textual.app import ComposeResult, RenderableType, SystemCommand
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Label,
    Log,
    OptionList,
    Placeholder,
    Static,
)
from textual_image.widget import HalfcellImage, SixelImage, TGPImage, UnicodeImage
from textual_image.widget import Image as AutoImage
from textual_slider import Slider

from gui.data_table import PlaylistWidget, TrackTableWidget
from gui.events import CustomClickEvent
from gui.log_controller import LogController
from gui.music_database_widget import MusicDatabaseWidget
from gui.tree_table_mover import TreeTableMoverWidget

TEST_IMAGE = "_data/paula_logo.png"

RENDERING_METHODS = {
    "auto": AutoImage,
    "tgp": TGPImage,
    "sixel": SixelImage,
    "halfcell": HalfcellImage,
    "unicode": UnicodeImage,
}

MANUAL_REFRESH = [
    "#border_top_volume",
    "#border_bottom_volume",
    "#border_top_audioplayer",
    "#border_bottom_audioplayer",
]


class SettingsScreen(Screen):
    BINDINGS = [
        ("q", "do_close", "Close the Help"),
    ]

    def action_do_close(self) -> None:
        self.app.pop_screen()

    def compose(self) -> ComposeResult:
        yield Grid(
            Static(
                "Grid cell 1\n\nrow-span: 3;\ncolumn-span: 2;", id="static_settings_1"
            ),
            Static("Grid cell 2", classes="static_settings", id="static2"),
            Static("Grid cell 3", classes="static_settings", id="static3"),
            Static("Grid cell 4", classes="static_settings", id="static4"),
            Static("Grid cell 5", classes="static_settings", id="static5"),
            Static("Grid cell 6", classes="static_settings", id="static6"),
            Static("Grid cell 7", classes="static_settings", id="static7"),
            classes="settings_grid",
        )


class HelpScreen(Screen):
    BINDINGS = [
        ("q", "do_close", "Close the Help"),
    ]

    def action_do_close(self) -> None:
        self.app.pop_screen()

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
        ("s", "show_settings", "Settings"),
        ("h", "show_help", "Help"),
        ("q", "request_quit", "Quit the app"),
        ("l", "show_log", "Show the log"),
    ]
    RATING_INFO = """Rate the results from
similarity database
🟢 The higher the value,
the higher the track fit.
🟡 0 means that the track
fits so far.
🔴 The lower the value,
the less the track fit.
"""

    def __init__(self, log_controller: LogController) -> None:
        super().__init__()
        self.cursor = create_cursor()
        self.log_controller = log_controller
        self.audio_player = AudioPlayerWidget(
            cursor=self.cursor, playlist_provider="#playlist_table", id="audio-player"
        )
        self.slider_volume = Slider(min=0, max=100, value=0, id="slider-volume")
        current_volume = get_system_volume()
        self.slider_volume.value = int(current_volume * 100)

    def update_image(self, image_path):
        image_widget = self.query_one("#cover-image")
        image_widget.image = image_path

    def action_show_help(self) -> None:
        """Action to display the help dialog."""
        self.app.push_screen(HelpScreen(self.log_controller))

    def action_show_settings(self) -> None:
        """Action to display the settings dialog."""
        self.app.push_screen(SettingsScreen(self.log_controller))

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
                track_row[4],
                track_row[5],
                track_row[6],
                track_row[7],
            )
        plt.insert_tracks_finished()
        self.log_controller.write(f"{len(tracks)}")
        # close_connection()

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
                tree_table_mover = TreeTableMoverWidget(
                    cursor=self.cursor, id="tree_table_mover"
                )
                yield tree_table_mover
                track_table = TrackTableWidget(
                    id="track_table", log_controller=self.log_controller
                )
                yield track_table

                playlist = PlaylistWidget(
                    id="playlist_table",
                    cursor=self.cursor,
                    log_controller=self.log_controller,
                )
                self.track_table = track_table  # Store reference for updates
                yield playlist

            with Vertical(id="metadata"):
                Image = RENDERING_METHODS["auto"]
                image_widget = Image(TEST_IMAGE, id="cover-image")
                image_widget.styles.width = "100%"
                image_widget.styles.height = "35%"
                image_widget.styles.align = ("right", "top")
                image_widget.styles.padding = 0
                image_widget.styles.margin = 0
                # yield Container(self.image_container)
                yield image_widget
                meta_label = Label(self.show_song_metadata(1), id="meta-label")
                meta_label.border_title = "meta data"
                yield meta_label
                yield BorderLabel(
                    "Volume", classes="grey-label", id="border_top_volume", type="top"
                )
                yield self.slider_volume
                yield BorderLabel(
                    "",
                    classes="grey-label",
                    id="border_bottom_volume",
                    type="bottom",
                )
                yield BorderLabel(
                    "Audioplayer",
                    classes="grey-label",
                    id="border_top_audioplayer",
                    type="top",
                )
                yield self.audio_player
                yield BorderLabel(
                    "",
                    classes="grey-label",
                    id="border_bottom_audioplayer",
                    type="bottom",
                )
                yield BorderLabel(
                    "Rate",
                    classes="grey-label",
                    id="border_top_optionlist_rate",
                    type="top",
                )
                with Horizontal(id="train_screen_horizontal"):
                    optionlist_rate = OptionList(
                        "+3",
                        "+2",
                        "+1",
                        "0",
                        "-1",
                        "-2",
                        "-3",
                        id="optionlist_rate",
                        disabled=True,
                    )
                    optionlist_rate.highlighted = 3
                    yield optionlist_rate
                    yield Label(self.RATING_INFO, id="optionlist_rate_info")
                yield BorderLabel(
                    "",
                    classes="grey-label",
                    id="border_bottom_optionlist_rate",
                    type="bottom",
                )
        yield Footer()

    def on_option_list_option_selected(self):
        if self.app.query_one("#playlist_table").in_training:
            sel_value = int(self.app.query_one("#optionlist_rate").highlighted)
            value = 3 - sel_value
            self.app.query_one("#playlist_table").update_rating(value)

    def show_song_metadata(self, track_id):
        meta = ""
        meta += f"Date: {1}\n"
        meta += f"Genre: {1}\n"
        return meta

    def show_album_tracks(self, album_id: int):
        global TEST_IMAGE
        """Show tracks for the selected album."""
        self.track_table.populate_tracks(self.cursor, album_id)
        cover_path = get_cover_by_album_id(self.cursor, album_id)
        if cover_path:
            self.update_image(cover_path)

    @on(Slider.Changed, "#slider-volume")
    def on_slider_volume_changed(self, event: Slider.Changed) -> None:
        percentage = event.value / 100
        set_system_volume(percentage)

    @on(AudioPlayerWidget.PositionChanged)
    def on_audio_player_postion_changed(
        self, message: AudioPlayerWidget.PositionChanged
    ) -> None:
        # Broadcast the message to all widgets
        self.query_one(PlaylistWidget).on_position_changed(message.value)

    @on(TrackTableWidget.PositionChanged)
    def on_track_table_postion_changed(
        self, message: TrackTableWidget.PositionChanged
    ) -> None:
        # Broadcast the message to all widgets
        self.query_one(AudioPlayerWidget).on_position_changed(message.value)

    @on(PlaylistWidget.PositionChanged)
    def on_track_table_postion_changed(
        self, message: PlaylistWidget.PositionChanged
    ) -> None:
        # Broadcast the message to all widgets
        self.query_one(AudioPlayerWidget).on_position_changed(message.value)

    @on(PlaylistWidget.PlaylistChanged)
    def on_track_table_playlist_changed(
        self, message: PlaylistWidget.PlaylistChanged
    ) -> None:
        # Broadcast the message to all widgets
        self.query_one(AudioPlayerWidget).on_new_playlist(message.value)

    def _on_resize(self, event):
        super()._on_resize(event)
        for id in MANUAL_REFRESH:
            self.query_one(id, BorderLabel).refresh()
        self.query_one("#metadata", Vertical).refresh()


class BorderLabel(Label):

    def __init__(self, label, id, classes, type="top") -> None:
        super().__init__()
        self.label = label
        self.id = id
        self.classes = classes
        self.type = type

    def render(self) -> RenderableType:
        line = "\u2500"
        if "top" in self.type:
            count = self.parent.size[0] - len(self.label) - 5
            return "\u250C" + line + " " + self.label + " " + (count * line) + "\u2510"
        else:
            count = self.parent.size[0] - 2
            return "\u2514" + (count * line) + "\u2518"
