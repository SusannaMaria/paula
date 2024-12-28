import logging
import sys
from time import sleep
from gui.events import CustomClickEvent
from gui.genre_slider import GenreSliders
from database.database_helper import (
    close_connection,
    create_cursor,
    get_cover_by_album_id,
    get_track_by_id,
    get_tracks_between_by_genre,
)
from textual.widgets import Footer
from textual.app import App, ComposeResult
from textual.widgets import (
    Tree,
    Input,
    DataTable,
    Static,
    Log,
    Button,
    Tabs,
    Tab,
    TabbedContent,
    TabPane,
    Label,
    Placeholder,
)
from textual.containers import Container, Vertical, Horizontal
import sqlite3
from textual_image.widget import HalfcellImage, SixelImage, TGPImage, UnicodeImage
from textual_image.widget import Image as AutoImage

from typing import Iterable

from textual.app import App, SystemCommand
from textual.screen import Screen, ModalScreen
from textual.message import Message
from textual.widget import Widget
from textual.containers import Grid
from textual.binding import Binding
from textual import events
from textual.css.scalar import Scalar

# data = [random.expovariate(1 / 3) for _ in range(1000)]
# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

RENDERING_METHODS = {
    "auto": AutoImage,
    "tgp": TGPImage,
    "sixel": SixelImage,
    "halfcell": HalfcellImage,
    "unicode": UnicodeImage,
}

NAMES = [
    "Artists",
    "Genres",
]

TEST_IMAGE = r"/mnt/c/temp/cover_d.jpg"


class LogController:
    """Centralized log controller to manage log messages."""

    def __init__(self) -> None:
        self.messages = []
        self.log_widget = None

    def set_log_widget(self, log_widget: Widget) -> None:
        """Set the active log widget to update."""
        self.log_widget = log_widget
        self.refresh_log_widget()

    def write(self, message: str) -> None:
        """Add a message to the log and update the widget."""
        self.messages.append(message)
        if self.log_widget:
            self.log_widget.write(message)

    def refresh_log_widget(self) -> None:
        """Refresh the current log widget with all messages."""
        if self.log_widget:
            self.log_widget.clear()
            for message in self.messages:
                self.log_widget.write(f"{message}\n")


class DashboardScreen(Screen):

    BINDINGS = [
        ("d", "switch_mode('dashboard')", "Dashboard"),
        ("s", "switch_mode('settings')", "Settings"),
        ("h", "switch_mode('help')", "Help"),
        ("q", "request_quit", "Quit the app"),
        ("l", "show_log", "Show the log"),
    ]

    # MODES = {
    #     "dashboard": DashboardScreen,
    #     "settings": SettingsScreen,
    #     "help": HelpScreen,
    #     "logscreen": LogScreen,
    # }

    def __init__(self, log_controller: LogController) -> None:
        super().__init__()
        self.log_controller = log_controller
        self.image_container = Container()
        self.image_container.visible = False
        self.update_image(TEST_IMAGE)

    def update_image(self, image_path):
        self.image_container.visible = True
        # Remove the old image widget (if any) and add a new one
        for widget in self.image_container.walk_children():
            widget.remove()
        Image = RENDERING_METHODS["auto"]
        image_widget = Image(image_path)
        image_widget.styles.width = Scalar.parse("25")
        image_widget.styles.height = Scalar.parse("14")
        if self.image_container.is_mounted:
            self.image_container.mount(image_widget)

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
        # Handle the custom event

        self.log_controller.write(
            f"{event.description} - {event.genre} - {event.lower} - {event.upper}"
        )
        cursor = create_cursor()
        tracks = get_tracks_between_by_genre(
            cursor, event.genre, event.lower, event.upper
        )

        plt = self.query_one("#playlist_table")
        plt.clear_table()
        for track in tracks:
            track_row = get_track_by_id(cursor, track)

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
                database_path="database/paula.sqlite",
                on_album_selected=self.show_album_tracks,
                id="music_panel",
                log_controller=self.log_controller,
            )
            yield music_db
            with Vertical(id="tracklist"):
                with Horizontal(id="media_controls"):
                    yield Input(placeholder="Search Tracks ...", id="search_bar_tracks")
                    yield Button("PLAY", classes="red", id="red_button")
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
                yield Container(self.image_container)
        yield Footer()

    def show_album_tracks(self, album_id: int):
        global TEST_IMAGE
        """Show tracks for the selected album."""
        self.track_table.populate_tracks(
            album_id, database_path="database/paula.sqlite"
        )
        database_path = "database/paula.sqlite"
        connection = sqlite3.connect(database_path)
        cursor = connection.cursor()
        cover_path = get_cover_by_album_id(cursor, album_id)
        if cover_path:
            self.update_image(cover_path)
        connection.close()


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


class MusicDatabaseWidget(Container):
    """A widget to display the music database as a tree structure with a search bar."""

    def __init__(
        self,
        database_path: str,
        on_album_selected=None,
        log_controller: LogController = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.database_path = database_path
        self.on_album_selected = on_album_selected  # Callback for album selection
        self.original_data = {}  # Store metadata for filtering
        self.log_controller = log_controller

    def compose(self) -> ComposeResult:
        """Compose the widget with a search bar and a Tree."""
        # yield Tabs(
        #     Tab(NAMES[0], id="tree_artists_tab"), Tab(NAMES[1], id="tree_genres_tab")
        # )
        with TabbedContent(initial="tree_artists_tab"):
            with TabPane("Artists->Albums", id="tree_artists_tab"):
                yield Input(placeholder="Search Artists or Albums ...", id="search_bar")
                yield Tree("Music Database", id="music_tree")  # Assign the Tree an ID
            with TabPane("Genres->Artists", id="tree_genres_artists_tab"):
                yield GenreSliders(id="genre_slider")
                yield Tree("Genre Tree", id="genre_tree")

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Handle TabActivated message sent by Tabs."""

        if event.tab.id == "tree_artists_tab":
            self.log_controller.write("Artist Tab")
        elif event.tab.id == "tree_genres_tab":
            self.log_controller.write("Genres Tab")

    def on_mount(self) -> None:
        """Populate the tree and store the original data for filtering."""
        tree = self.query(Tree).first()  # Get the first Tree widget
        self.populate_tree(tree)

    def populate_tree(self, tree: Tree) -> None:
        """Populate the tree with database content and store metadata."""
        self.clear_tree(tree.root)  # Clear the tree before repopulating

        # Connect to the SQLite database
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        # Retrieve artists and albums
        cursor.execute("SELECT artist_id, name FROM artists")
        artists = cursor.fetchall()

        self.original_data = {}  # Reset metadata storage

        for artist_id, artist_name in artists:
            artist_label = f"🎤 {artist_name}"
            artist_node = tree.root.add(artist_label, allow_expand=True)
            self.original_data[artist_name.lower()] = {
                "label": artist_label,
                "allow_expand": True,
                "children": [],
                "artist_id": artist_id,
            }
            parent_name = artist_name.lower()
            # Fetch albums for the artist
            cursor.execute(
                "SELECT album_id, name FROM albums WHERE artist_id = ?", (artist_id,)
            )
            albums = cursor.fetchall()
            if not albums:
                artist_node.allow_expand = False
            for album_id, album_title in albums:
                album_label = f"📀 {album_title}"
                album_node = artist_node.add(album_label, allow_expand=False)
                album_node.album_id = album_id  # Store album_id in the node
                # log = self.query_one("#logview")

                self.log_controller.write(
                    f"Album Node Added: {album_label} (ID: {album_id})"
                )

                node_data = {
                    "label": album_label,
                    "allow_expand": False,
                    "album_id": album_id,
                    "parent": artist_id,
                }
                self.original_data[album_title.lower()] = node_data

        connection.close()

    def clear_tree(self, node):
        """Clear all children of a tree node."""
        while node.children:
            node.children[0].remove()

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Handle changes in the search bar."""
        tree = self.query(Tree).first()  # Get the first Tree widget
        self.filter_tree(tree, event.value)

    def get_parent_node(self, tree, child):
        for key, data in self.original_data.items():
            if "artist_id" in data and data["artist_id"] == child:
                artist_node = tree.root.add(data["label"], allow_expand=True)
                return artist_node
        return None

    def get_children_nodes(self, tree, parent):
        for key, data in self.original_data.items():
            if "parent" in data and data["parent"] == parent:
                node = tree.add(data["label"], allow_expand=True)
                node.album_id = data["album_id"]

    def filter_tree(self, tree: Tree, query: str) -> None:
        """Filter the tree based on the search query."""
        query = query.lower()
        self.clear_tree(tree.root)  # Clear the tree
        if len(query) == 0:
            self.on_mount()

        for key, data in self.original_data.items():

            if query in key and len(query) > 2:
                print(data)
                if "parent" in data and data["parent"] > 0:
                    artistnode = self.get_parent_node(tree, data["parent"])
                    if artistnode:
                        node = artistnode.add(
                            data["label"], allow_expand=data["allow_expand"]
                        )
                        if node and "album_id" in data:
                            node.album_id = data["album_id"]

                            self.log_controller.write(
                                f"Filtered Album Node Added: {data['label']}"
                            )
                else:
                    node = tree.root.add(
                        data["label"], allow_expand=data["allow_expand"]
                    )
                    self.get_children_nodes(node, data["artist_id"])

                    if "album_id" in data:
                        node.album_id = data["album_id"]

                        self.log_controller.write(
                            f"Filtered Album Node Added: {data['label']}"
                        )

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection in the tree."""
        node = event.node
        logging.debug(f"Node Selected: {node.label}")
        if hasattr(node, "album_id") and self.on_album_selected:

            self.log_controller.write(f"Album Selected: {node.album_id}")
            self.on_album_selected(node.album_id)


class TrackTableWidget(DataTable):
    """A widget to display tracks of a selected album."""

    def __init__(self, log_controller: LogController, **kwargs):
        super().__init__(**kwargs)
        self.add_column("Track Number", width=10)
        self.add_column("Title", width=40)
        self.log_controller = log_controller

    def populate_tracks(self, album_id: int, database_path: str):
        """Populate the table with tracks for the given album."""
        self.clear()  # Clear existing tracks

        self.log_controller.write(f"Populating tracks for album ID: {album_id}")
        connection = sqlite3.connect(database_path)
        cursor = connection.cursor()

        cursor.execute(
            "SELECT track_number, title FROM tracks WHERE album_id = ? ORDER BY CAST(SUBSTR(track_number, 1, INSTR(track_number, '/') - 1) AS INTEGER);",
            (album_id,),
        )
        tracks = cursor.fetchall()
        connection.close()

        for track_number, title in tracks:
            self.add_row(str(track_number), title.replace("[", r"\["))


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


class MusicDatabaseApp(App):
    """Textual App to display the MusicDatabaseWidget."""

    CSS_PATH = "treelist.tcss"

    def on_mount(self) -> None:
        self.log_controller = LogController()

        # Start with the Main Screen
        self.push_screen(DashboardScreen(self.log_controller))


if __name__ == "__main__":
    MusicDatabaseApp().run()
