# Training function to adjust weights
import curses
import json

import numpy as np
from database.database_helper import execute_query
from utils.config_loader import load_config


def map_rating_to_similarity(similarity, rating, adjustment_factor=0.2):
    """
    Adjust the target similarity based on rating.

    :param similarity: Original similarity (e.g., negative Euclidean distance).
    :param rating: User-provided rating (1 to 5).
    :param adjustment_factor: Small factor to adjust similarity.
    :return: Adjusted target similarity.
    """
    # Calculate the adjustment (rating - 3 determines direction and magnitude)
    adjustment = (rating - 3) * adjustment_factor

    # Adjust the target similarity
    target_similarity = similarity + adjustment

    return target_similarity


def train_feature_weights(
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
