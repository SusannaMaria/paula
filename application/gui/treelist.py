import logging
from time import sleep
from textual.app import App, ComposeResult
from textual.widgets import Tree, Input, DataTable, Static
from textual.containers import Container, Vertical, Horizontal
import sqlite3
from textual_image.widget import HalfcellImage, SixelImage, TGPImage, UnicodeImage
from textual_image.widget import Image as AutoImage


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

TEST_IMAGE = r"/mnt/c/temp/cover_d.jpg"


class MusicDatabaseWidget(Container):
    """A widget to display the music database as a tree structure with a search bar."""

    def __init__(self, database_path: str, on_album_selected=None, **kwargs):
        super().__init__(**kwargs)
        self.database_path = database_path
        self.on_album_selected = on_album_selected  # Callback for album selection
        self.original_data = {}  # Store metadata for filtering

    def compose(self) -> ComposeResult:
        """Compose the widget with a search bar and a Tree."""
        yield Input(placeholder="Search Artists or Albums ...", id="search_bar")
        yield Tree("Music Database", id="music_tree")  # Assign the Tree an ID

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
                logging.debug(f"Album Node Added: {album_label} (ID: {album_id})")
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
                            logging.debug(f"Filtered Album Node Added: {data['label']}")
                else:
                    node = tree.root.add(
                        data["label"], allow_expand=data["allow_expand"]
                    )
                    self.get_children_nodes(node, data["artist_id"])

                    if "album_id" in data:
                        node.album_id = data["album_id"]
                        logging.debug(f"Filtered Album Node Added: {data['label']}")

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection in the tree."""
        node = event.node
        logging.debug(f"Node Selected: {node.label}")
        if hasattr(node, "album_id") and self.on_album_selected:
            logging.debug(f"Album Selected: {node.album_id}")
            self.on_album_selected(node.album_id)


class TrackTableWidget(DataTable):
    """A widget to display tracks of a selected album."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_column("Track Number", width=10)
        self.add_column("Title", width=40)

    def populate_tracks(self, album_id: int, database_path: str):
        """Populate the table with tracks for the given album."""
        self.clear()  # Clear existing tracks
        logging.debug(f"Populating tracks for album ID: {album_id}")
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_column("Title", width=30)
        self.add_column("Artist", width=30)
        self.add_column("Album", width=30)

    def add_track(self, track_id: int, title: str, artist: str, album: str):
        """Add a track to the playlist."""
        self.add_row(str(track_id), title, artist, album)


class MusicDatabaseApp(App):
    """Textual App to display the MusicDatabaseWidget."""

    CSS = """
    #track_table {
        height: 50%;
    }
    #image_widget {
        width: 15%;
        height: 30%
    }
    #playlist_table {
        height: 50%;
    }
    """

    def on_album_selected(self, album_id: int):
        """Handle album selection event."""
        # Fetch the album cover path from the database (replace this with actual logic)
        image_path = "/mnt/c/temp/cover.jpg"

        old_widget = self.query_one("#image_widget")
        logging.info(old_widget)

        Image = RENDERING_METHODS["auto"]
        new_image_widget = Image(image_path, id="image_widget")
        yield new_image_widget

        # if old_widget:
        # old_widget = new_image_widget

        # container = self.query_one(Horizontal)

        # container.replace(new_image_widget)

        # logging.info(f"Updating image to: {image_path}")

    def compose(self) -> ComposeResult:
        """Compose the UI with a horizontal layout."""
        with Horizontal():
            music_db = MusicDatabaseWidget(
                database_path="database/paula.sqlite",
                on_album_selected=self.show_album_tracks,
                id="music_panel",
            )
            yield music_db
            with Vertical():
                track_table = TrackTableWidget(id="track_table")
                yield track_table

                playlist = PlaylistWidget(id="playlist_table")
                self.track_table = track_table  # Store reference for updates
                yield playlist
            Image = RENDERING_METHODS["auto"]
            self.image_widget = Image(TEST_IMAGE, id="image_widget")
            yield self.image_widget

    def show_album_tracks(self, album_id: int):
        global TEST_IMAGE
        """Show tracks for the selected album."""
        self.track_table.populate_tracks(
            album_id, database_path="database/paula.sqlite"
        )
        image_path = "/mnt/c/temp/cover.jpg"

        image_widget = self.query_one("#image_widget")
        image_widget.image = image_path


if __name__ == "__main__":
    MusicDatabaseApp().run()
