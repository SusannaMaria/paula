import json
import logging
from pathlib import Path
import sqlite3
import numpy as np
import os
from search.search_main import create_search_query
from config_loader import load_config
from database.database_helper import (
    close_connection,
    close_cursor,
    commit,
    create_cursor,
    execute_query,
    get_track_by_id,
)
from annoy import AnnoyIndex
import numpy as np
from scipy.spatial.distance import cosine
from collections import defaultdict
from multiprocessing import Pool, Value, Lock
from colorama import Fore, Style, init
import subprocess

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
    min_max_query = """
    SELECT
        MIN(danceability), MAX(danceability),
        MIN(bpm), MAX(bpm),
        MIN(average_loudness), MAX(average_loudness),
        MIN(mood_happy), MAX(mood_happy),
        MIN(mood_party), MAX(mood_party),
        MIN(genre_rock), MAX(genre_rock),
        MIN(genre_pop), MAX(genre_pop),
        MIN(genre_jazz), MAX(genre_jazz),
        MIN(genre_electronic), MAX(genre_electronic),
        MIN(dynamic_complexity), MAX(dynamic_complexity),
        MIN(voice_instrumental), MAX(voice_instrumental)
    FROM track_features;
    """

    feature_query = """
    SELECT track_id, danceability, bpm, average_loudness, mood_happy, mood_party,
           genre_rock, genre_pop, genre_jazz, genre_electronic, dynamic_complexity,voice_instrumental
    FROM track_features;
    """

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
    )


def build_ann_index(cursor):
    """
    Build an Annoy index for fast similarity searches.
    """
    config = load_config()
    index_path = config["annoy_index"]["path"]
    num_trees = config["annoy_index"]["num_trees"]

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
    for track_id, features_json in features:
        features = json.loads(features_json)
        index.add_item(track_id, features)

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


def open_in_foobar2000(playlist_path):
    """
    Open the generated M3U playlist in Foobar2000.

    Args:
        playlist_path (str): Full path to the playlist file.
    """
    try:
        playlist_path = (
            str(playlist_path)
            .replace("/mnt/", "")
            .replace("/", "\\")
            .replace("\\", ":\\", 1)
        )
        subprocess.run(
            ["cmd.exe", "/c", f'start foobar2000 "{playlist_path}"'],
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


def run_similarity(do_normalize, input_query):
    config = load_config()
    temp_dir = Path(config["temp_dir"])

    cursor = create_cursor(asrow=True)
    if do_normalize:
        precompute_features(cursor)
        build_ann_index(cursor)
        compute_similarity_batch(cursor)
    else:
        sql_query, params = create_search_query(input_query)
        tracks = execute_query(
            cursor, sql_query, params=params, fetch_one=False, fetch_all=True
        )
        file_paths = []
        for track in tracks:
            features_json = execute_query(
                cursor,
                f"SELECT track_id, normalized_features FROM track_features WHERE track_id={track[0]};",
                fetch_one=True,
                fetch_all=False,
            )
            track_features = json.loads(features_json[1])
            similar_tracks = search_similar_tracks(track[0], track_features, 10)

            main_track = get_track_by_id(cursor, track[0])
            file_paths.append(main_track["title_path"])

            print_track(main_track, print_path=False)
            for sim_track in similar_tracks:
                sim_track_result = get_track_by_id(cursor, sim_track[0])

                print_track(sim_track_result, print_path=False, is_similary=True)
                file_paths.append(sim_track_result["title_path"])

        playlist_path = temp_dir / "paula_playlist.m3u"
        create_m3u_playlist(file_paths, playlist_path)
        open_in_foobar2000(playlist_path)
        close_cursor(cursor)
        close_connection()
