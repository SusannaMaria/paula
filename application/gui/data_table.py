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

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from textual.app import ComposeResult
from textual.containers import Grid
from textual.coordinate import Coordinate
from textual.events import Key, MouseDown
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
)

from application.database.database_helper import execute_query
from application.gui.log_controller import LogController
from application.gui.screen_update import ScreenUpdate
from application.similarity.similarity_main import build_ann_index
from application.similarity.train_weights import (
    TrainScreen,
    get_feature_vector,
    map_rating_to_similarity,
)
from application.updater.updater_main import get_audio_path_from_track_id
from application.utils.config_loader import load_config, update_weight_config


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
            ("Title", 20),
            ("Length", 5),
            ("Album", 20),
            ("Artist", 20),
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
        self.input = Input(placeholder="Edit value here")
        self.in_training = False
        self.selected_cell = None
        self.cel_rate_coordinate = None
        self.new_weights = None

    async def action_select_cell(self, cell):
        self.selected_cell = cell
        self.input.value = cell.value
        self.input.visible = True
        self.input.focus()

    async def on_data_table_cell_selected(self, event: DataTable.CellSelected):
        await self.action_select_cell(event)

    async def on_key(self, event: Key):
        if event.key == "enter" and self.input.visible:
            # Update the DataTable with the new value
            row, column = self.selected_cell.coordinate
            self.table.update_cell(row, column, self.input.value)
            self.input.visible = False

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
        similarity: str = None,
    ):
        track_num, total_tracks = track_number.split("/")
        track_number = f"{int(track_num):02}/{total_tracks}"  # Add leading zero

        if release_date:
            release_date = str(release_date).rstrip("-")
        """Add a track to the playlist."""
        if similarity is None:
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
        else:
            self.add_row(
                str(track_id),
                track_number,
                title,
                length,
                album,
                artist,
                release_date,
                similarity,
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
        if not self.in_training:
            self.post_message(self.PositionChanged(event.cursor_row))
        else:
            self.cel_rate_coordinate = Coordinate(column=8, row=event.cursor_row)
            rate_cell_value = self.get_cell_at(self.cel_rate_coordinate)
            index = int(rate_cell_value) + 3
            self.app.query_one("#optionlist_rate").highlighted = index

    def update_rating(self, value):
        if self.cel_rate_coordinate:
            self.update_cell_at(self.cel_rate_coordinate, str(value))

    def on_mouse_down(self, event: MouseDown):
        """Handle mouse events and detect double-clicks."""
        if not self.in_training:
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

    def do_training(self):
        self.in_training = True
        self.add_column("Rate", width=5, key="rate", default="0")
        self.header.append(("Rate", 5))
        self.app.query_one("#optionlist_rate").disabled = False

    def stop_training(self, do_training):
        if do_training:
            origin_track = -1
            self.in_training = False
            # TODO: {23329: -1, 33902: 3, 10102: 3, 2961: 3, 33415: 3, 10112: 3, 23979: 3, 32719: 3, 6080: 3, 13971: 3, 22358: 3}
            training_data = {}

            for row_index in range(self.row_count):
                track_id = self.get_cell_at(Coordinate(column=0, row=row_index))
                delta = self.get_cell_at(Coordinate(column=7, row=row_index))
                if delta == 0.0:
                    origin_track = track_id
                    rate = -1
                else:
                    rate = self.get_cell_at(Coordinate(column=8, row=row_index))
                training_data[track_id] = rate
            self.app.query_one("#optionlist_rate").disabled = True
            self.remove_column("rate")
            del self.header[-1]
            train_screen = TrainScreen()
            self.app.push_screen(train_screen)
            worker = TrainFeatureWeightsWorker(train_screen)
            worker.init_training(self.cursor, training_data, origin_track)

            with ThreadPoolExecutor(max_workers=1) as executor:
                future1 = executor.submit(
                    worker.train_feature_weights,
                    self.similar_tracks,
                    training_data,
                    origin_track,
                    initial_learning_rate=0.01,
                    max_epochs=400,
                    patience=10,
                )
                result1 = future1.result()
                if worker.new_weights:
                    update_weight_config(worker.new_weights)
                    build_ann_index(self.cursor, worker.new_weights)
                    train_screen.update_pretty_config()


class TrainFeatureWeightsWorker:
    def __init__(self, screen: TrainScreen):
        self.screen = screen
        self.new_weights = None

    def init_training(self, cursor, feedback, origin_track):
        feedback_vectors = {}
        origin_vector = get_feature_vector(cursor, origin_track)
        feedback_vectors[origin_track] = origin_vector
        for idx, (track_id, rating) in enumerate(feedback.items()):
            track_vector = get_feature_vector(cursor, track_id)
            feedback_vectors[track_id] = track_vector
        self.feedback_vectors = feedback_vectors
        self.new_weights = None

    def train_feature_weights(
        self,
        similar_tracks,
        feedback,
        origin_track,
        initial_learning_rate=0.01,
        max_epochs=200,
        patience=10,
    ):
        config = load_config()
        similar_tracks_similarity = [x[1] for x in similar_tracks]
        weights = [details["weight"] for feature, details in config["features"].items()]
        origin_vector = self.feedback_vectors[origin_track]

        # Display header
        best_loss = float("inf")
        epochs_without_improvement = 0
        learning_rate = initial_learning_rate
        self.screen.post_message(
            ScreenUpdate(
                total=max_epochs,
                loss=best_loss,
                progress=0,
                status="Training Phase: Press 'q' to quit at any time.",
            )
        )

        feedback_str = "Training completed! Press any key to exit."

        for epoch in range(max_epochs):
            total_loss = 0
            for idx, (track_id, rating) in enumerate(feedback.items()):
                if track_id == origin_track or rating == -1:
                    continue  # Skip the origin track or invalid ratings

                # Get the track feature vector
                track_vector = self.feedback_vectors[track_id]

                # Map rating to target similarity (-1 to 1)
                target_similarity = map_rating_to_similarity(
                    similar_tracks_similarity[idx - 1], rating
                )

                # Calculate weighted distance (Euclidean)
                origin_vector = np.array(
                    origin_vector
                )  # Ensure origin_vector is a NumPy array
                track_vector = np.array(track_vector)

                weighted_diff = weights * (origin_vector - track_vector)

                predicted_similarity = np.sqrt(
                    np.sum(weighted_diff**2)
                )  # Negative distance for similarity

                # Compute error (difference between feedback rating and predicted similarity)
                error = target_similarity - predicted_similarity

                # Update weights (gradient descent)
                gradient = -2 * error * (origin_vector - track_vector)
                weights -= learning_rate * gradient

                # Clip weights to prevent negative values
                weights = np.clip(weights, 0.0, 2.0)

                # Accumulate loss for monitoring
                total_loss += error**2

            # Check for early stopping
            if total_loss < best_loss:
                best_loss = total_loss
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1

            # Monitor loss at each epoch
            if epoch % 10 == 0:
                self.screen.post_message(ScreenUpdate(loss=total_loss, progress=epoch))

            # Stop training if no improvement for `patience` epochs
            if epochs_without_improvement >= patience:
                feedback_str = f"Stopping early at epoch {epoch}. No improvement in loss. Press any key to exit."
                break

            # Optionally decay learning rate if improvement slows
            if epochs_without_improvement > patience // 2:
                learning_rate *= 0.5  # Reduce learning rate
                self.screen.post_message(
                    ScreenUpdate(
                        status=f"Reducing learning rate to {learning_rate:.6f}"
                    )
                )

        self.screen.post_message(
            ScreenUpdate(
                status=feedback_str,
            )
        )
        self.new_weights = weights.tolist()
