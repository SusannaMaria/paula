from database.database_helper import get_tracks_by_id
from similarity.similarity_main import get_similar_tracks_by_id
from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label
from updater.updater_main import get_audio_path_from_track_id


class TrainingConfirmScreen(ModalScreen[bool]):
    """Screen with a dialog to quit."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to train with ratings?", id="question"),
            Button("OK", variant="error", id="okay"),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "okay":
            self.dismiss(True)
        else:
            self.dismiss(False)


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
        self.button_get_similar_tracks = Button(
            "get similar tracks",
            id="button-get-similar-tracks",
            classes="tree_table_button",
        )
        self.button_train_similarity = Button(
            "train similarity",
            id="button-train-similarity",
            classes="tree_table_button",
            disabled=True,
        )
        self.cursor = cursor

    async def on_mount(self, event):
        self.mount(self.horizontal_container_button)
        self.horizontal_container_button.mount(self.button_add_playlist)
        self.horizontal_container_button.mount(self.button_get_similar_tracks)
        self.horizontal_container_button.mount(self.button_train_similarity)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        music_panel = self.app.query_one("#music_panel")
        playlist_table = self.app.query_one("#playlist_table")
        node_selected = music_panel.node_selected
        if button_id == "button-add-playlist":

            if hasattr(node_selected, "track_id"):
                id = node_selected.track_id
                type_of = "track_id"
            elif hasattr(node_selected, "artist_id"):
                id = node_selected.artist_id
                type_of = "artist_id"
            elif hasattr(node_selected, "album_id"):
                id = node_selected.album_id
                type_of = "album_id"
            else:
                return

            tracks = get_tracks_by_id(self.cursor, id, type_of)

            for col in playlist_table.columns:
                if "delta" in col.value:
                    playlist_table.remove_column("delta")
                    del playlist_table.header[-1]
                    break

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

        if button_id == "button-get-similar-tracks":
            if not hasattr(node_selected, "track_id"):
                self.app.notify("Please select a track!", severity="error", timeout=2)
                return
            elif hasattr(node_selected, "track_id"):
                id = node_selected.track_id
                type_of = "track_id"
            else:
                return

            colfound = False
            for col in playlist_table.columns:
                if "delta" in col.value:
                    colfound = True
            if not colfound:
                playlist_table.add_column("Delta", width=5, key="delta")
                playlist_table.header.append(("Delta", 5))
            playlist_table.clear_table()
            similar_tracks = get_similar_tracks_by_id(self.cursor, id)
            similar_tracks.insert(0, (id, 0.0))
            playlist_table.similar_tracks = similar_tracks
            for sim_tracks in similar_tracks:
                track = get_tracks_by_id(self.cursor, sim_tracks[0], "track_id")[0]
                path = get_audio_path_from_track_id(self.cursor, track[0])
                playlist_table.add_track(
                    str(track[0]),  # track_id
                    track[1],  # track_number
                    track[2],  # track_title
                    track[3],  # length
                    track[10],  # artist_name
                    track[7],  # album_title
                    track[8],  # release_date
                    path,
                    sim_tracks[1],
                )
            playlist_table.insert_tracks_finished()
            self.button_train_similarity.disabled = False
        if button_id == "button-train-similarity":
            btn = self.app.query_one("#button-train-similarity")
            if "train similarity" in btn.label:
                btn.label = "stop training"
                playlist_table.do_training()
            elif "stop training" in btn.label:
                btn.label = "train similarity"

                def check_training(okay: bool | None) -> None:
                    """Called when QuitScreen is dismissed."""
                    playlist_table.stop_training(okay)

                self.app.push_screen(TrainingConfirmScreen(), check_training)
