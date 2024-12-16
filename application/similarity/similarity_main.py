import json
import sqlite3
import numpy as np
from search.search_main import create_search_query
from config_loader import load_config
from database.database_helper import (
    commit,
    create_cursor,
    execute_query,
    get_track_by_id,
)
from annoy import AnnoyIndex


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
    cursor = create_cursor()
    if do_normalize:
        precompute_features(cursor)
        build_ann_index(cursor)
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
