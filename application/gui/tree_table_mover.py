from database.database_helper import get_tracks_by_id
from textual.containers import Container, Horizontal
from textual.widgets import Button
from updater.updater_main import get_audio_path_from_track_id


class TreeTableMoverWidget(Container):

    def __init__(self, cursor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor = cursor
        self.horizontal_container_button = Horizontal(
            classes="horizontal_container_top", id="horizontal_tree_table_button"
        )
        self.button_add_playlist = Button(
            "add to playlist", id="button-add-playlist", classes="tree_table_button"
        )

    async def on_mount(self, event):
        self.mount(self.horizontal_container_button)
        self.horizontal_container_button.mount(self.button_add_playlist)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "button-add-playlist":
            music_panel = self.app.query_one("#music_panel")
            playlist_table = self.app.query_one("#playlist_table")
            node_selected = music_panel.node_selected

            if hasattr(node_selected, "artist_id"):
                id = node_selected.artist_id
                type_of = "artist_id"
            elif hasattr(node_selected, "album_id"):
                id = node_selected.album_id
                type_of = "album_id"
            elif hasattr(node_selected, "track_id"):
                id = node_selected.track_id
                type_of = "track_id"
            else:
                return
            print()

        tracks = get_tracks_by_id(self.cursor, id, type_of)

        playlist_table.clear_table()

        for (
            track_id,
            track_number,
            track_title,
            length,
            year,
            path,
            album_id,
            album_title,
            release_date,
            artist_id,
            artist_name,
        ) in tracks:
            path = get_audio_path_from_track_id(self.cursor, track_id)
            playlist_table.add_track(
                str(track_id),
                track_number,
                track_title,
                length,
                artist_name,
                album_title,
                release_date,
                path,
            )
        playlist_table.insert_tracks_finished()
