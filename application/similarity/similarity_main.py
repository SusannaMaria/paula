import curses
import json
import logging
import os
import sqlite3
import subprocess
from collections import defaultdict
from multiprocessing import Lock, Pool, Value
from pathlib import Path

import networkx as nx
import numpy as np
from annoy import AnnoyIndex
from colorama import Fore, Style, init
from database.database_helper import (
    close_connection,
    close_cursor,
    commit,
    create_cursor,
    execute_query,
    get_track_by_id,
)
from pyvis.network import Network
from scipy.spatial.distance import cosine
from search.search_main import create_search_query
from similarity.html_utils import inject_context_menu
from similarity.similarity_feedback import display_tracks_and_collect_feedback
from similarity.train_weights import train_feature_weights
from utils.config_loader import load_config, update_weight_config

init(autoreset=True)

# Define a global shared counter
shared_counter = None
counter_lock = None

logger = logging.getLogger(__name__)


def init_worker(counter, lock):
    """Initialize the shared counter for each worker."""
    global shared_counter
    global counter_lock
    shared_counter = counter
    counter_lock = lock


def group_similar_tracks_by_artist_or_album(cursor, similarity_threshold=0.8):
    """
    Groups similar tracks by artist or album based on similarity scores.

    Args:
        db_path (str): Path to the SQLite database.
        similarity_threshold (float): Minimum similarity score to consider.

    Returns:
        dict: Grouped data by artist and album.
    """
    query = """
    SELECT
        s.track_id_1,
        t1.title AS track_1_title,
        a1.name AS artist_1,
        al1.name AS album_1,
        s.track_id_2,
        t2.title AS track_2_title,
        a2.name AS artist_2,
        al2.name AS album_2,
        s.similarity_score
    FROM
        track_similarity s
    JOIN tracks t1 ON s.track_id_1 = t1.track_id
    JOIN artists a1 ON t1.artist_id = a1.artist_id
    JOIN albums al1 ON t1.album_id = al1.album_id
    JOIN tracks t2 ON s.track_id_2 = t2.track_id
    JOIN artists a2 ON t2.artist_id = a2.artist_id
    JOIN albums al2 ON t2.album_id = al2.album_id
    WHERE s.similarity_score > ?
    ORDER BY s.similarity_score DESC;
    """

    execute_query(cursor, query, (similarity_threshold,))
    results = cursor.fetchall()

    # Group by artist and album
    grouped_by_artist = defaultdict(list)
    grouped_by_album = defaultdict(list)

    for row in results:
        artist_1 = row["artist_1"]
        album_1 = row["album_1"]

        artist_2 = row["artist_2"]
        album_2 = row["album_2"]

        # Add to artist groups
        grouped_by_artist[artist_1].append(
            {
                "track_title": row["track_1_title"],
                "similar_track_title": row["track_2_title"],
                "similar_artist": artist_2,
                "similar_album": album_2,
                "similarity_score": row["similarity_score"],
            }
        )

        # Add to album groups
        grouped_by_album[album_1].append(
            {
                "track_title": row["track_1_title"],
                "similar_track_title": row["track_2_title"],
                "similar_artist": artist_2,
                "similar_album": album_2,
                "similarity_score": row["similarity_score"],
            }
        )

    return {"by_artist": grouped_by_artist, "by_album": grouped_by_album}


def precompute_features(cursor):
    """
    Precompute and store normalized features for all tracks in the database.
    """
    config = load_config()
    features = config["features"]

    min_max_query = "SELECT "
    min_max_query_select = []
    for feature_name, feature_details in features.items():
        # weight = feature_details["weight"]
        min_max_query_select.append(f"MIN({feature_name}), MAX({feature_name})")

    min_max_query += ", ".join(min_max_query_select)
    min_max_query += " FROM track_features;"

    feature_query = "SELECT track_id"
    for feature_name, feature_details in features.items():
        # weight = feature_details["weight"]
        feature_query += f", {feature_name}"

    feature_query += " FROM track_features"

    # Fetch min and max values for normalization
    min_max = execute_query(cursor, min_max_query, fetch_one=True, fetch_all=False)
    min_vals = min_max[::2]
    max_vals = min_max[1::2]

    # Fetch features for all tracks
    tracks = execute_query(cursor, feature_query, fetch_one=False, fetch_all=True)

    logger.info("Update normalized_features")
    # Normalize and store features
    for track in tracks:
        track_id = track[0]
        features = track[1:]
        normalized_features_vals = normalize_features(features, min_vals, max_vals)

        execute_query(
            cursor,
            "UPDATE track_features SET normalized_features = ? WHERE track_id = ?;",
            (json.dumps(normalized_features_vals), track_id),
        )
    commit()


# Function to map similarity score to edge properties
def get_edge_properties(similarity):
    color_scale = int(255 * similarity)  # Scale color from 0-255
    color = f"rgb({255 - color_scale}, {color_scale}, 200)"  # Red to Green gradient
    width = max(1, similarity * 4)  # Scale width (min 1px, max 10px)
    opacity = 0.3 + 0.7 * similarity  # Scale opacity (min 0.3, max 1)
    return color, width, opacity


def process_batch(batch_ids, track_features, track_ids, threshold):
    """
    Compute similarity for a batch of tracks and return the top 100 similarities.

    Args:
        batch_ids (list): List of `track_id_1` values in the batch.
        track_features (dict): Dictionary of track_id -> feature vector.
        track_ids (list): List of all track IDs.
        threshold (float): Minimum similarity score to store.

    Returns:
        list: List of tuples (track_id_1, track_id_2, similarity_score).
    """
    similarities = []
    for track_id_1 in batch_ids:
        track_similarities = []

        for track_id_2 in track_ids:
            if track_id_1 >= track_id_2:
                continue

            # Compute similarity
            similarity_score = 1 - cosine(
                track_features[track_id_1], track_features[track_id_2]
            )

            if similarity_score >= threshold and track_id_1 != track_id_2:
                track_similarities.append((track_id_1, track_id_2, similarity_score))

        # Sort and keep only the top 100 similarities
        top_similarities = sorted(track_similarities, key=lambda x: x[2], reverse=True)[
            :100
        ]
        similarities.extend(top_similarities)

    # Update progress counter
    with counter_lock:
        shared_counter.value += 1
        print(
            f"Progress: {shared_counter.value} batches completed by process {os.getpid()}"
        )

    return similarities


def compute_similarity_parallel(
    db_path, track_features, batch_size=100, top_n=100, threshold=0.8, num_workers=4
):
    """
    Compute similarities in parallel and store only the top 100 similarities for each track.

    Args:
        db_path (str): Path to the SQLite database.
        track_features (dict): Dictionary of track_id -> feature vector.
        batch_size (int): Number of tracks to process in each batch.
        threshold (float): Minimum similarity score to consider.
        num_workers (int): Number of parallel workers.
    """
    track_ids = list(track_features.keys())

    # Split track_ids into batches
    batches = [
        track_ids[i : i + batch_size] for i in range(0, len(track_ids), batch_size)
    ]

    # Shared counter and lock
    counter = Value("i", 0)  # Shared counter initialized to 0
    lock = Lock()

    all_similarities = []

    with Pool(num_workers, initializer=init_worker, initargs=(counter, lock)) as pool:
        results = pool.starmap(
            query_annoy_for_tracks,
            [(batch, top_n, threshold) for batch in batches],
        )
        for batch_similarities in results:
            all_similarities.extend(batch_similarities)

    # Write results to the database
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    try:
        cursor.executemany(
            "INSERT INTO track_similarity (track_id_1, track_id_2, similarity_score) VALUES (?, ?, ?);",
            all_similarities,
        )
        connection.commit()
    finally:
        connection.close()


def query_annoy_for_tracks(batch_ids, top_n=100, threshold=0.8):
    """
    Query Annoy index for a batch of track IDs.

    Args:
        batch_ids (list): List of track IDs to process.
        top_n (int): Number of most similar tracks to retrieve.
        threshold (float): Minimum similarity score to consider.

    Returns:
        list: List of tuples (track_id_1, track_id_2, similarity_score).
    """
    config = load_config()
    index_path = config["annoy_index"]["path"]
    num_trees = config["annoy_index"]["num_trees"]

    # Define the number of features (dimension)
    feature_dim = config["annoy_index"][
        "feature_dim"
    ]  # Replace with the actual number of features

    index = AnnoyIndex(
        feature_dim, metric="euclidean"
    )  # Adjust dimension to match your index
    index.load(index_path)

    results = []
    for track_id_1 in batch_ids:
        # Get top N similar tracks
        track_ids, distances = index.get_nns_by_item(
            track_id_1, n=top_n, include_distances=True
        )

        # Convert distances to similarity scores and filter by threshold
        for track_id_2, distance in zip(track_ids, distances):
            similarity_score = 1 - distance  # Convert distance to similarity
            if similarity_score >= threshold and track_id_1 != track_id_2:
                results.append((track_id_1, track_id_2, similarity_score))

    # Update progress counter
    with counter_lock:
        shared_counter.value += 1
        logger.info(
            f"Progress: {shared_counter.value} batches completed by process {os.getpid()}"
        )
    return results


def similarity_tracks(cursor, track_id1, track_id2):
    similarity_query = """SELECT similarity_score
            FROM track_similarity
            WHERE (track_id_1 = ? AND track_id_2 = ?)
            OR (track_id_1 = ? AND track_id_2 = ?)"""

    similarity = execute_query(
        cursor,
        similarity_query,
        (track_id1, track_id2, track_id2, track_id1),
        fetch_one=True,
        fetch_all=False,
    )
    if similarity and "similarity_score" in similarity:
        return similarity["similarity_score"]
    else:
        return 0.0


def compute_similarity_batch(cursor, batch_size=1000, threshold=0.8):
    """
    Compute pairwise similarity for tracks in batches and store results above the threshold.

    Args:
        db_path (str): Path to the SQLite database.
        batch_size (int): Number of tracks to process in each batch.
        threshold (float): Minimum similarity score to store.

    """
    # Fetch all track feature vectors
    execute_query(cursor, "SELECT track_id, normalized_features FROM track_features;")
    all_tracks = cursor.fetchall()

    # Convert to a dictionary
    track_features = {
        row["track_id"]: np.array(eval(row["normalized_features"]))
        for row in all_tracks
    }

    execute_query(cursor, "DELETE FROM track_similarity")
    commit()
    close_cursor(cursor)
    close_connection()

    config = load_config()
    db_config = config["database"]

    compute_similarity_parallel(
        db_path=db_config["path"],
        track_features=track_features,
        batch_size=100,  # Process 100 tracks per batch
        threshold=0.8,
        num_workers=4,  # Use 4 parallel processes
        top_n=500,
    )


def build_ann_index(cursor, feature_weights):
    """
    Build an Annoy index for fast similarity searches.
    """
    config = load_config()
    index_path = config["annoy_index"]["path"]
    num_trees = config["annoy_index"]["num_trees"]
    features_config = config["features"]

    # Define the number of features (dimension)
    feature_dim = config["annoy_index"][
        "feature_dim"
    ]  # Replace with the actual number of features
    index = AnnoyIndex(feature_dim, metric="euclidean")

    features = execute_query(
        cursor,
        "SELECT track_id, normalized_features FROM track_features;",
        fetch_one=False,
        fetch_all=True,
    )
    logger.info("Add features to index")

    # Process each track's features
    for track_id, features_json in features:
        features = json.loads(features_json)

        # Apply weights to the features
        weighted_features = [w * f for w, f in zip(feature_weights, features)]
        # Add the weighted features to the index
        index.add_item(track_id, weighted_features)

    # Build the index with the specified number of trees
    logger.info("Build feature index")
    index.build(num_trees)
    logger.info("Save feature index")
    index.save(index_path)


def normalize_features(features, min_vals, max_vals):
    """
    Normalize features using min-max scaling.

    Args:
        features (list): Raw feature vector.
        min_vals (list): Minimum values for each feature.
        max_vals (list): Maximum values for each feature.

    Returns:
        list: Normalized feature vector.
    """
    return [
        (f - min_v) / (max_v - min_v) if max_v != min_v else 0.0
        for f, min_v, max_v in zip(features, min_vals, max_vals)
    ]


def search_similar_tracks(query_track_id, track_features, num_results=5):
    """
    Search for the most similar tracks using the Annoy index.
    """
    config = load_config()
    index_path = config["annoy_index"]["path"]
    feature_dim = config["annoy_index"]["feature_dim"]

    index = AnnoyIndex(feature_dim, metric="euclidean")
    index.load(index_path)
    _num = num_results + 1
    similar_tracks = index.get_nns_by_vector(
        track_features, _num, include_distances=True
    )

    # Post-process to exclude the input track ID
    track_ids, distances = similar_tracks
    filtered_similar_tracks = [
        (other_track_id, distance)
        for other_track_id, distance in zip(track_ids, distances)
        if other_track_id != query_track_id
    ]

    return filtered_similar_tracks


def open_in_player(playlist_path):
    """
    Open the generated M3U playlist in Foobar2000.

    Args:
        playlist_path (str): Full path to the playlist file.
    """
    config = load_config()
    player = Path(config["player"])
    try:
        playlist_path = (
            str(playlist_path)
            .replace("/mnt/", "")
            .replace("/", "\\")
            .replace("\\", ":\\", 1)
        )
        subprocess.run(
            ["cmd.exe", "/c", f'start {player} "{playlist_path}"'],
            check=True,
            stdout=subprocess.DEVNULL,  # Suppress standard output
            stderr=subprocess.DEVNULL,  # Suppress standard error
        )
        logger.info(f"Playlist opened in Foobar2000: {playlist_path}")
    except subprocess.CalledProcessError as e:
        logger.info(f"Failed to open playlist in Foobar2000: {e}")


def create_m3u_playlist(file_paths, playlist_path):
    """
    Create an M3U playlist file from a list of file paths.

    Args:
        file_paths (list): List of file paths to songs.
        playlist_path (str): Path to save the playlist file.
    """
    with open(playlist_path, "w", encoding="utf-8") as playlist:
        # Write M3U header
        playlist.write("#EXTM3U\n")

        for path in file_paths:
            # You can add song duration and title if available
            if path.startswith("/mnt/"):
                path = (
                    path.replace("/mnt/", "").replace("/", "\\").replace("\\", ":\\", 1)
                )
            playlist.write(f"{path}\n")

    logger.info(f"Playlist saved to {playlist_path}")


def print_track(track, print_path=False, is_similary=False):
    prefix = ""
    path_str = ""

    if is_similary:
        prefix = "-> "

    if print_path:
        path_str = (
            f' | {Style.BRIGHT + Fore.RED}"{track["title_path"]}"{Style.RESET_ALL}'
        )

    print(
        f'{prefix}{Style.BRIGHT + Fore.YELLOW}"{track["track_title"]}"{Style.RESET_ALL} '
        f'from {Style.BRIGHT + Fore.GREEN}"{track["artist_name"]}"{Style.RESET_ALL} '
        f'out of {Style.BRIGHT + Fore.CYAN}"{track["album_name"]}"{Style.RESET_ALL}{path_str}'
    )


def getnode(net, track, distance, from_node_id, is_similary=False):

    if is_similary:
        col = "#ff5733"
    else:
        col = "#ADD8E6"

    net.add_node(
        track["track_id"],
        label=track["track_title"],
        shape="dot",
        size=15,
        color=col,
        title=(
            track["track_title"][:17] + "..."
            if len(track["track_title"]) > 20
            else track["track_title"]
        ),
    )
    if from_node_id != track["track_id"]:
        net.add_edge(
            from_node_id, track["track_id"], weight=distance, width=5, color="#aaaaaa"
        )


def network_similarity(net, similar_tracks):

    config = load_config()
    index_path = config["annoy_index"]["path"]
    num_trees = config["annoy_index"]["num_trees"]

    # Define the number of features (dimension)
    feature_dim = config["annoy_index"]["feature_dim"]

    index = AnnoyIndex(
        feature_dim, metric="euclidean"
    )  # Adjust dimension to match your index
    index.load(index_path)

    for i in range(len(similar_tracks)):
        for j in range(
            i + 1, len(similar_tracks)
        ):  # Ensure no duplicates or self-pairs
            similarity = 1 - index.get_distance(
                similar_tracks[i][0], similar_tracks[j][0]
            )

            color, width_edge, opacity = get_edge_properties(similarity)

            if similarity > 0.6:
                net.add_edge(
                    similar_tracks[i][0],
                    similar_tracks[j][0],
                    weight=similarity,
                    width=width_edge,
                    opacity=opacity,
                    color=color,
                )


def run_similarity(do_normalize, input_query, do_train):
    config = load_config()
    temp_dir = Path(config["temp_dir"])
    net = Network(height="750px", width="100%", notebook=False)
    cursor = create_cursor(asrow=True)
    max_recursion_level = 1
    if do_normalize:
        precompute_features(cursor)
        feature_weights = [
            details["weight"] for feature, details in config["features"].items()
        ]
        build_ann_index(cursor, feature_weights)
        # compute_similarity_batch(cursor)
    else:
        sql_query, params = create_search_query(input_query)
        tracks = execute_query(
            cursor, sql_query, params=params, fetch_one=False, fetch_all=True
        )
        file_paths = []
        origin_track = None
        for track in tracks:
            track_similarity_processing(
                net,
                cursor,
                file_paths,
                track[0],
                current_depth=0,
                max_depth=max_recursion_level,
            )
            origin_track = track[0]

        ####################
        playlist_path = temp_dir / "paula_playlist.m3u"
        create_m3u_playlist(file_paths, playlist_path)
        open_in_player(playlist_path)
        if do_train:
            prepare_feedback(cursor, origin_track)

        close_cursor(cursor)
        close_connection()

        # # Customize appearance
        # net.repulsion(
        #     node_distance=120, central_gravity=0.33, spring_length=100, damping=0.95
        # )
        # # Save and open the interactive HTML file
        # html_content = net.generate_html()

        # # Inject the context menu script into the generated HTML
        # modified_html = inject_context_menu(html_content)

        # # Save the modified HTML
        # with open("track_similarity_graph.html", "w", encoding="utf-8") as f:
        #     f.write(modified_html)


def track_similarity_processing(
    net, cursor, file_paths, track, current_depth, max_depth, do_m3u=True
):
    if current_depth >= max_depth:
        logger.debug(
            f"Max recursion depth {max_depth} reached at depth {current_depth}"
        )
        return

    features_json = execute_query(
        cursor,
        f"SELECT track_id, normalized_features FROM track_features WHERE track_id={track};",
        fetch_one=True,
        fetch_all=False,
    )
    track_features = json.loads(features_json[1])
    similar_tracks = search_similar_tracks(track, track_features, 10)

    main_track = get_track_by_id(cursor, track)
    if do_m3u:
        file_paths.append(main_track["title_path"])
    getnode(net, main_track, 1.0, main_track["track_id"], is_similary=False)

    print_track(main_track, print_path=False)
    for sim_track in similar_tracks:
        sim_track_result = get_track_by_id(cursor, sim_track[0])

        print_track(sim_track_result, print_path=False, is_similary=True)
        if do_m3u:
            file_paths.append(sim_track_result["title_path"])
        getnode(
            net,
            sim_track_result,
            sim_track[1],
            main_track["track_id"],
            is_similary=True,
        )
        track_similarity_processing(
            net,
            cursor,
            file_paths,
            sim_track[0],
            current_depth + 1,
            max_depth,
            do_m3u=False,
        )
    network_similarity(net, similar_tracks)


def prepare_feedback(cursor, origin_track_id):
    features_json = execute_query(
        cursor,
        f"SELECT track_id, normalized_features FROM track_features WHERE track_id={origin_track_id};",
        fetch_one=True,
        fetch_all=False,
    )
    track_features = json.loads(features_json[1])
    # origin_track = get_track_by_id(cursor, origin_track_id)

    similar_tracks = search_similar_tracks(origin_track_id, track_features, 10)

    similar_tracks_ids = [x[0] for x in similar_tracks]
    track_feedback = display_tracks_and_collect_feedback(
        cursor, origin_track_id, similar_tracks_ids
    )

    if len(track_feedback) == 11:
        trained_weights = curses.wrapper(
            train_feature_weights,
            cursor,
            similar_tracks,
            track_feedback,
            origin_track_id,
            initial_learning_rate=0.001,
            max_epochs=200,
            patience=10,
        )

        confirmation = curses.wrapper(display_weights_and_confirm, trained_weights)

        if confirmation:
            update_weight_config(trained_weights)
            build_ann_index(cursor, trained_weights)

        return confirmation
    return False


def display_weights_and_confirm(stdscr, trained_weights):
    """
    Display old and new weights in curses and ask for user confirmation.

    :param stdscr: The curses screen object.
    :param old_weights: List of old weights.
    :param new_weights: List of new weights.
    :param feature_names: List of feature names.
    :return: True if user confirms update, False otherwise.
    """
    config = load_config()
    feature_config = config["features"]
    feature_names = list(feature_config.keys())

    curses.curs_set(0)  # Hide cursor
    stdscr.clear()

    # Display header
    stdscr.addstr(0, 0, "Weight Updates (Old -> New):", curses.A_BOLD)

    # Display old and new weights

    for idx, feature in enumerate(feature_names):
        stdscr.addstr(
            2 + idx,
            0,
            f'{feature}: {feature_config[feature]["weight"]} -> {trained_weights[idx]}',
        )

    # Ask for confirmation
    stdscr.addstr(
        2 + len(feature_names) + 1,
        0,
        "Do you want to update the weights with the new values and rebuild the Annoy Index? (y/n): ",
    )
    stdscr.refresh()

    # Wait for user input
    while True:
        key = stdscr.getch()
        if key in [ord("y"), ord("Y")]:
            return True  # User confirmed
        elif key in [ord("n"), ord("N")]:
            return False  # User canceled
