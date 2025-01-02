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

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import (
    Input,
    TabbedContent,
    TabPane,
    Tabs,
    Tree,
)

from gui.genre_slider import GenreSliders
from gui.log_controller import LogController


class MusicDatabaseWidget(Container):
    """A widget to display the music database as a tree structure with a search bar."""

    def __init__(
        self,
        cursor,
        on_album_selected=None,
        log_controller: LogController = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cursor = cursor
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
                root_tree = Tree("Music Database", id="music_tree")
                root_tree.root.expand()
                root_tree.focus()
                yield root_tree  # Assign the Tree an ID
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

        # Retrieve artists and albums
        self.cursor.execute("SELECT artist_id, name FROM artists")
        artists = self.cursor.fetchall()

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
            self.cursor.execute(
                "SELECT album_id, name FROM albums WHERE artist_id = ?", (artist_id,)
            )
            albums = self.cursor.fetchall()
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
