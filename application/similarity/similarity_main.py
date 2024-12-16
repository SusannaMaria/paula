import json
import sqlite3
import numpy as np
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
        similarity s
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

    # Process in batches
    track_ids = list(track_features.keys())
    for i in range(0, len(track_ids), batch_size):
        batch_ids = track_ids[i : i + batch_size]

        for track_id_1 in batch_ids:
            for track_id_2 in track_ids:
                if track_id_1 >= track_id_2:
                    continue

                # Compute similarity
                similarity_score = 1 - cosine(
                    track_features[track_id_1], track_features[track_id_2]
                )
                if similarity_score >= threshold and track_id_1 != track_id_2:
                    cursor.execute(
                        "INSERT INTO track_similarity (track_id_1, track_id_2, similarity_score) VALUES (?, ?, ?);",
                        (track_id_1, track_id_2, similarity_score),
                    )
        commit()


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
    for track_id, features_json in features:
        features = json.loads(features_json)
        index.add_item(track_id, features)

    # Build the index with the specified number of trees
    index.build(num_trees)
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


def search_similar_tracks(track_features, num_results=5):
    """
    Search for the most similar tracks using the Annoy index.
    """
    config = load_config()
    index_path = config["annoy_index"]["path"]
    feature_dim = config["annoy_index"]["feature_dim"]

    index = AnnoyIndex(feature_dim, metric="euclidean")
    index.load(index_path)
    similar_tracks = index.get_nns_by_vector(
        track_features, num_results, include_distances=True
    )
    return similar_tracks


def run_similarity(do_normalize, input_query):
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
        for track in tracks:
            features_json = execute_query(
                cursor,
                f"SELECT track_id, normalized_features FROM track_features WHERE track_id={track[0]};",
                fetch_one=True,
                fetch_all=False,
            )
            track_features = json.loads(features_json[1])
            similar_tracks = search_similar_tracks(track_features)
            print(f"{get_track_by_id(cursor, track[0])}")
            for sim_track in similar_tracks[0]:
                print(f"-->{get_track_by_id(cursor, sim_track)}")
    close_cursor(cursor)
    close_connection()
