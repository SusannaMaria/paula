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

import curses
import json

import numpy as np
from database.database_helper import execute_query
from gui.screen_update import ScreenUpdate
from textual.app import ComposeResult
from textual.color import Gradient
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Label, Pretty, ProgressBar
from utils.config_loader import load_config


class TrainScreen(Screen):

    BINDINGS = [
        ("q", "do_close", "Close the logging"),
    ]
    GRADIENT = Gradient.from_colors(
        "#881177",
        "#aa3355",
        "#cc6666",
        "#ee9944",
        "#eedd00",
        "#99dd55",
        "#44dd88",
        "#22ccbb",
        "#00bbcc",
        "#0099cc",
        "#3366bb",
        "#663399",
    )

    def on_screen_update(self, message: ScreenUpdate):
        if message.loss and message.progress:
            self.progress_info.update(
                f"Epoch {message.progress}, Loss: {message.loss:.4f}"
            )

        if message.total:
            self.progressbar.update(total=message.total)
        if message.progress:
            self.progressbar.update(progress=message.progress)
        if message.status:
            self.status.update(message.status)

    def action_do_close(self) -> None:
        self.app.pop_screen()

    def __init__(self) -> None:
        super().__init__()
        self.headline = Label("Headline", id="headline_training")
        self.progressbar = ProgressBar(id="progress_training", gradient=self.GRADIENT)
        self.progress_info = Label("Progress_info", id="progress_info")
        self.status = Label("Status", id="status_training")
        config = load_config()
        self.feature_config = Pretty(config["features"])
        # weights = [details["weight"] for feature, details in config["features"].items()]

    def update_pretty_config(self):
        config = load_config()
        self.feature_config.update(config["features"])

    def compose(self) -> ComposeResult:
        with Vertical():
            yield self.headline
            yield self.progressbar
            yield self.progress_info
            yield self.status
            yield self.feature_config


def map_rating_to_similarity(similarity, rating, adjustment_factor=0.2):
    """
    Adjust the target similarity based on rating.

    :param similarity: Original similarity (e.g., negative Euclidean distance).
    :param rating: User-provided rating (1 to 5).
    :param adjustment_factor: Small factor to adjust similarity.
    :return: Adjusted target similarity.
    """
    # Calculate the adjustment (rating - 3 determines direction and magnitude)
    adjustment = float(rating) * adjustment_factor

    # Adjust the target similarity
    target_similarity = similarity + adjustment

    return target_similarity


def train_feature_weights_curses(
    stdscr,
    cursor,
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
    origin_vector = get_feature_vector(cursor, origin_track)

    curses.start_color()
    curses.curs_set(0)  # Enable cursor
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)  # Red text
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Green text
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Yellow text
    curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Blue text
    stdscr.clear()

    # Display header
    stdscr.addstr(0, 0, "Training Phase: Press 'q' to quit at any time.", curses.A_BOLD)

    best_loss = float("inf")
    epochs_without_improvement = 0
    learning_rate = initial_learning_rate
    feedback_str = "Training completed! Press any key to exit."
    for epoch in range(max_epochs):
        total_loss = 0
        for idx, (track_id, rating) in enumerate(feedback.items()):
            if track_id == origin_track or rating == -1:
                continue  # Skip the origin track or invalid ratings

            # Get the track feature vector
            track_vector = get_feature_vector(cursor, track_id)

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
            stdscr.addstr(2 + epoch % 10, 0, f"Epoch {epoch}, Loss: {total_loss:.4f}")
            stdscr.refresh()

        # Stop training if no improvement for `patience` epochs
        if epochs_without_improvement >= patience:
            feedback_str = f"Stopping early at epoch {epoch}. No improvement in loss. Press any key to exit."
            break

        # Optionally decay learning rate if improvement slows
        if epochs_without_improvement > patience // 2:
            learning_rate *= 0.5  # Reduce learning rate
            stdscr.addstr(
                2 + 11 + 1, 0, f"Reducing learning rate to {learning_rate:.6f}"
            )
            stdscr.refresh()

    stdscr.addstr(2 + 11 + 1, 0, feedback_str)
    stdscr.refresh()
    stdscr.getch()

    return weights.tolist()


def get_feature_vector(cursor, track_id):
    features_json = execute_query(
        cursor,
        f"SELECT track_id, normalized_features FROM track_features WHERE track_id={track_id};",
        fetch_one=True,
        fetch_all=False,
    )
    feature_vector = json.loads(features_json[1])
    return feature_vector
